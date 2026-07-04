"""
document_classifier.py
=======================
Document identification for the Document Upload & AI Document Ingestion
subsystem.

DocumentClassifier answers exactly one question: "what type of document
is this, and what downstream configuration does that type resolve to?"
It owns identification only — it does not route to a processor, does
not extract data, and does not touch Mongo or repositories. It does
call the shared LLM (via backend.agent_nodes.llm), but only to
determine document_type and confidence — nothing else.

Responsibilities
-----------------
- Accept document content plus its DocumentMetadata.
- Determine the document_type (via an LLM call — see
  _detect_document_type()).
- Validate the detected document_type against document_registry.
- Build and return a typed ClassificationResult, using document_registry
  as the single source of truth for business_domain, outcome,
  target_business_entity, and review_required.

Explicitly NOT this module's responsibility
--------------------------------------------
- Calling repositories or MongoDB.
- Extracting structured data (BaseProcessor / domain processors).
- Calling processors or performing any routing (processor_registry.py).
- Asking the LLM for business_domain, outcome, target_business_entity,
  or review_required — those come exclusively from document_registry.
- Importing business entities.

Swappable internals, stable interface
---------------------------------------
Document type detection is isolated behind the private
_detect_document_type() method. It is now LLM-based (using the shared
`llm` from backend.agent_nodes.llm — the same instance every workflow
agent uses) rather than keyword matching, but classify()'s signature,
return type, and raised exceptions are unchanged, so no calling code
in DocumentService needed to change.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from backend.agent_nodes.llm import llm
from backend.document_processing.document_models import (
    ClassificationResult,
    DocumentMetadata,
)
from backend.document_processing.document_registry import get_document_type_config


# ==========================================================
# STANDARDIZED CLASSIFICATION EXCEPTION
# ==========================================================

class ClassificationError(Exception):
    """
    Raised when a document's type cannot be determined, or when the
    detected document_type is not present in document_registry.

    Carries document_id and a human-readable reason so the failure can
    be logged and diagnosed without a raw traceback.
    """

    def __init__(self, document_id: str, reason: str) -> None:
        self.document_id = document_id
        self.reason = reason

        super().__init__(
            f"Classification failed for document '{document_id}': {reason}"
        )


# ==========================================================
# LLM-BASED DETECTION — CANDIDATE DOCUMENT TYPES
# ==========================================================
# Internal detail of the current LLM-based implementation only.
# Values must correspond to document_type values registered in
# document_registry.DOCUMENT_TYPE_REGISTRY. This list intentionally
# lives here, not in document_registry, because it is a classification
# prompt detail (which labels the model is allowed to choose from),
# not document configuration. document_registry remains the single
# source of truth for business_domain, outcome,
# target_business_entity, and review_required — the LLM is never
# asked for those.

_SUPPORTED_DOCUMENT_TYPES: tuple[str, ...] = (
    "resume",
    "market_research_report",
    "performance_review",
    "self_assessment",
    "manager_evaluation",
    "sales_performance_report",
    "hr_metrics_report",
    "product_information",
)

_UNSUPPORTED_DOCUMENT_TYPE = "unsupported"

# Minimum confidence (0-100, as returned by the LLM) required to accept
# a document_type. Below this threshold, the document is considered
# unclassifiable.
_MIN_CONFIDENCE = 60

# Matches lines like "Document Type: resume" / "Confidence: 87"
_DOCUMENT_TYPE_LINE_RE = re.compile(r"document\s*type\s*:\s*(\S+)", re.IGNORECASE)
_CONFIDENCE_LINE_RE = re.compile(r"confidence\s*:\s*(\d+(?:\.\d+)?)", re.IGNORECASE)

# How much of the document content to include in the prompt. Long
# documents are truncated so the prompt stays a reasonable size — only
# a representative excerpt is needed to identify the document's type.
_CONTENT_EXCERPT_CHARS = 3000


# ==========================================================
# DOCUMENT CLASSIFIER
# ==========================================================

class DocumentClassifier:
    """
    Determines a document's type and resolves its business context.

    Stateless: classify() depends only on its arguments, never on
    instance state, so a single instance can be reused freely.
    """

    def classify(self, content: str, metadata: DocumentMetadata) -> ClassificationResult:
        """
        Classify a document and resolve its business context.

        Args:
            content:  Raw text content of the document (already
                      extracted from the underlying file by DocumentTextExtractor).
                      
            metadata: DocumentMetadata describing the stored document.

        Returns:
            A ClassificationResult with document_type, business_domain,
            outcome, target_business_entity, and review_required resolved
            from document_registry.
        Raises:
            ClassificationError: If no document_type can be confidently
                                  detected, or the detected document_type
                                  is not registered in document_registry.
        """
        document_type, confidence = self._detect_document_type(content, metadata)

        try:
            config = get_document_type_config(document_type)
        except ValueError as exc:
            raise ClassificationError(
                document_id=metadata.document_id,
                reason=str(exc),
            ) from exc

        return ClassificationResult(
            document_id=metadata.document_id,
            document_type=config.document_type,
            business_domain=config.business_domain,
            outcome=config.outcome,
            target_business_entity=config.target_business_entity,
            review_required=config.review_required,
            confidence=confidence,
            classified_at=datetime.now(timezone.utc).isoformat(),
        )

    # ----------------------------------------------------------
    # INTERNAL DETECTION LOGIC
    # ----------------------------------------------------------
    # LLM-based. Uses the shared `llm` from backend.agent_nodes.llm,
    # invoked the same way every workflow agent does (llm.invoke(prompt)
    # followed by response.content.strip()). Isolated behind this
    # private method so classify()'s public interface never had to
    # change when this replaced the earlier keyword heuristic.

    def _detect_document_type(
        self,
        content: str,
        metadata: DocumentMetadata,
    ) -> tuple[str, float]:
        """
        Determine the most likely document_type via an LLM call.

        Asks the shared LLM to pick a single document_type from the
        known candidate list based on the document's filename and
        content, along with a 0-100 confidence score. The response is
        parsed and normalized to a 0.0-1.0 confidence ratio.

        Args:
            content:  Raw text content of the document.
            metadata: DocumentMetadata, used here for original_filename.

        Returns:
            A tuple of (document_type, confidence).

        Raises:
            ClassificationError: If the LLM response cannot be parsed,
                                  or the resulting confidence is below
                                  _MIN_CONFIDENCE.
        """
        excerpt = content[:_CONTENT_EXCERPT_CHARS]

        prompt = f"""
You are a document classification assistant. Determine the type of the
document below.

Filename: {metadata.original_filename}

Document Content:
{excerpt}

Supported document types:
{chr(10).join(f"- {t}" for t in _SUPPORTED_DOCUMENT_TYPES)}

Supported document types and strict classification criteria:

- resume
  A candidate/job-application document describing a person's professional
  background for recruitment purposes. It should contain clear resume-like
  evidence such as work experience, education, skills, contact details,
  professional summary, or a target/applied role.
  Do NOT classify any of the following as a resume:
- employee profiles or internal staff biographies;
- company directory entries or team-member introductions;
- generic biographies or narrative descriptions of a person;
- performance-related descriptions of an existing employee.

 A person having skills, experience, a job title, or employment history is not
 enough to make the document a resume. The document must have a clear
 recruitment, job-application, candidate-profile, or professional-CV purpose.

- product_information
  A document describing a specific commercial product or service that could
  be stored as a product business entity. It should clearly identify the
  offering and provide product-specific business information such as a
  description, customer pain points, target industries/customers, category,
  features, positioning, or pricing.
  Do NOT classify any of the following as product_information:
- recipes, cooking instructions, ingredients lists, food preparation guides,
  or other instructional content;
- general company brochures or company capability descriptions;
- advertisements without a clearly identifiable commercial offering;
- invoices or transaction documents;
- generic descriptions of an organization.

 A physical object, food item, topic, or described "thing" is not automatically
 a product. The document must have a business purpose of describing a specific
 commercial offering for customers, sales, marketing, or product management.

- hr_metrics_report
  A report containing organization-level HR or workforce metrics such as
  employee count, performance ratings, goal completion, satisfaction,
  attrition, training completion, or promotions.

- sales_performance_report
  A report containing sales performance metrics such as revenue, deals won,
  pipeline value, win rate, outreach activity, demos, or related KPIs.

- market_research_report
  A research or analysis document containing substantive market findings,
  competitor analysis, trends, customer insights, market overview, or
  defined research focus areas.
  Do NOT classify vague meeting notes or generic statements about growth,
  competitors, or markets without substantive research findings or analysis.

- performance_review
  A formal employee performance review containing evaluation evidence such
  as ratings, strengths, weaknesses, goals, or review-period assessment.

- self_assessment
  An employee's own first-person assessment of achievements, strengths,
  growth areas, or performance during a review period.

- manager_evaluation
  A manager's evaluation of an employee containing manager feedback,
  strengths, concerns, ratings, recommendations, or review evidence.

If the document does not clearly satisfy the positive criteria for one
supported type, classify it as:

- unsupported

Important rules:
- Match the document's purpose, not isolated words or superficial similarity.
- A person being described is not automatically a resume.
- Something being described is not automatically product information.
- Business-related text is not automatically a supported business document.
- When required evidence for a supported type is absent, choose unsupported.
- When genuinely uncertain between a supported type and unsupported, choose
  unsupported.
- Do not force unrelated, ambiguous, or insufficient content into the closest
  supported type.
- Before selecting product_information, verify that the document describes a
 specific commercial offering intended for customers. If it is primarily
 instructional content, such as a recipe or how-to guide, choose unsupported
 even if it describes ingredients, components, features, or a named item.
-Before selecting resume, verify that the document is actually intended to
 represent a candidate or professional profile for recruitment or job
 application purposes. If it merely describes an existing employee in
 third-person narrative form, choose unsupported even if skills, experience,
 or employment history are mentioned.

Confidence means how certain you are that the document genuinely satisfies
the full criteria for the selected type.

Respond in exactly this format, with no extra text:

Document Type: <supported_document_type_or_unsupported>
Confidence: <0-100>
"""

        response = llm.invoke(prompt)
        raw = response.content.strip()

        document_type_match = _DOCUMENT_TYPE_LINE_RE.search(raw)
        confidence_match = _CONFIDENCE_LINE_RE.search(raw)

        if document_type_match is None or confidence_match is None:
            raise ClassificationError(
                document_id=metadata.document_id,
                reason=(
                    "Unable to parse a document_type and confidence "
                    "from the LLM classification response."
                ),
            )

        document_type = document_type_match.group(1).strip().lower()
        confidence_raw = float(confidence_match.group(1))
        confidence = max(0.0, min(1.0, confidence_raw / 100))

        if document_type == _UNSUPPORTED_DOCUMENT_TYPE:
            raise ClassificationError(
                document_id=metadata.document_id,
                reason="Document does not match any supported document type.",
            )

        if document_type not in _SUPPORTED_DOCUMENT_TYPES:
            raise ClassificationError(
                document_id=metadata.document_id,
                reason=(
                    f"LLM returned an unrecognized document_type "
                    f"'{document_type}'."
                ),
            )

        if confidence_raw < _MIN_CONFIDENCE:
            raise ClassificationError(
                document_id=metadata.document_id,
                reason=(
                    f"Classification confidence ({confidence_raw:.0f}%) "
                    f"is below the required threshold ({_MIN_CONFIDENCE}%)."
                ),
            )

        return document_type, confidence
