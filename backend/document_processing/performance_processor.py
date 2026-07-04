"""
performance_processor.py
==========================
PerformanceProcessor — domain processor for `performance_review`,
`self_assessment`, and `manager_evaluation` documents.

Owns BusinessDomain.PERFORMANCE.

Per the frozen architecture these three document types are
ENTITY_EVIDENCE, not Employee imports: this processor extracts durable
evidence artifacts for later association with an Employee and review
period (a future milestone's responsibility, owned by other
developers). It does not associate anything to an Employee, does not
create or modify Goals, and does not decide a rating — those remain
owned by hr_agent.py's existing performance_review workflow
(retrieve_employee_data, retrieve_goal_data, evaluate_performance,
generate_rating, generate_improvement_plan), which this evidence is
meant to *complement*, not replace or bypass. This processor does not
integrate with that workflow itself.

The three document types carry genuinely different semantics, so each
gets its own internal Pydantic extraction model and is routed to its
own extraction method rather than being flattened into one generic
shape:

    performance_review  -> a completed review record (rating, summary,
                            strengths/weaknesses as already assessed)
    self_assessment     -> the employee's own self-reported view
    manager_evaluation  -> the manager's independent assessment/comments

The complete extracted document content is passed to the LLM for all
three document types; this processor performs no truncation. An
extremely large document that exceeds the shared LLM's context window
will surface as a real extraction failure rather than a silently
partial result.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, ValidationError

from backend.agent_nodes.llm import llm
from backend.document_processing._processor_utils import (
    calculate_field_completeness,
    parse_llm_json,
)
from backend.document_processing.base_processor import (
    BaseProcessor,
    OutputValidationError,
)
from backend.document_processing.document_models import (
    BusinessDomain,
    DocumentMetadata,
    ProcessingResult,
)

_PERFORMANCE_REVIEW_CONFIDENCE_WEIGHTS = {
    "review_period": 0.10,
    "overall_rating": 0.15,
    "strengths": 0.30,
    "weaknesses": 0.25,
    "goals_referenced": 0.20,
}

_SELF_ASSESSMENT_CONFIDENCE_WEIGHTS = {
    "review_period": 0.10,
    "self_reported_achievements": 0.40,
    "self_identified_strengths": 0.25,
    "self_identified_growth_areas": 0.25,
}

_MANAGER_EVALUATION_CONFIDENCE_WEIGHTS = {
    "review_period": 0.10,
    "manager_comments": 0.25,
    "strengths": 0.25,
    "concerns": 0.25,
    "recommended_rating": 0.15,
}


# ==============================================================
# INTERNAL EXTRACTION MODELS
# ==============================================================

class _ExtractedPerformanceReview(BaseModel):
    """
    Internal contract for a completed performance_review document.

    Shaped to complement hr_agent.PerformanceEvaluation
    (strengths/weaknesses/summary) and the rating produced by
    generate_rating, without duplicating or overriding either — this is
    evidence *from the document*, associated later, not a substitute
    for the workflow's own evaluation.
    """

    review_period: str | None = None
    overall_rating: float | None = None
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    goals_referenced: list[str] = Field(default_factory=list)
    summary: str | None = None


class _ExtractedSelfAssessment(BaseModel):
    """Internal contract for a self_assessment document — the
    employee's own reported achievements and growth areas."""

    review_period: str | None = None
    self_reported_achievements: list[str] = Field(default_factory=list)
    self_identified_strengths: list[str] = Field(default_factory=list)
    self_identified_growth_areas: list[str] = Field(default_factory=list)
    summary: str | None = None


class _ExtractedManagerEvaluation(BaseModel):
    """Internal contract for a manager_evaluation document — the
    manager's independent comments and assessment, complementing
    PerformanceReviewParams.manager_comments."""

    review_period: str | None = None
    manager_comments: str | None = None
    strengths: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    recommended_rating: float | None = None
    summary: str | None = None


# ==============================================================
# PROMPTS
# ==============================================================

_REVIEW_PROMPT_TEMPLATE = """
You are an HR documentation assistant. Read the performance review
document below and extract structured evidence.

Document Content:
{content}

Return ONLY a JSON object, no extra text, no markdown fences, in exactly
this shape:

{{
  "review_period": "<review cycle, e.g. 'Q2 2026', or null>",
  "overall_rating": <numeric rating given in the document, or null>,
  "strengths": ["<strength 1>", "<strength 2>"],
  "weaknesses": ["<weakness 1>", "<weakness 2>"],
  "goals_referenced": ["<goal mentioned 1>", "<goal mentioned 2>"],
  "summary": "<2-3 sentence summary of key achievements, concerns, and themes>"
}}

Use null or an empty list where the document does not cover a field.
"""

_SELF_ASSESSMENT_PROMPT_TEMPLATE = """
You are an HR documentation assistant. Read the employee self-assessment
below and extract structured evidence.

Document Content:
{content}

Return ONLY a JSON object, no extra text, no markdown fences, in exactly
this shape:

{{
  "review_period": "<review cycle, e.g. 'Q2 2026', or null>",
  "self_reported_achievements": ["<achievement 1>", "<achievement 2>"],
  "self_identified_strengths": ["<strength 1>", "<strength 2>"],
  "self_identified_growth_areas": ["<growth area 1>", "<growth area 2>"],
  "summary": "<2-3 sentence summary of the employee's self-reported achievements, concerns, and themes>"
}}

Use null or an empty list where the document does not cover a field.
"""

_MANAGER_EVAL_PROMPT_TEMPLATE = """
You are an HR documentation assistant. Read the manager evaluation
document below and extract structured evidence.

Document Content:
{content}

Return ONLY a JSON object, no extra text, no markdown fences, in exactly
this shape:

{{
  "review_period": "<review cycle, e.g. 'Q2 2026', or null>",
  "manager_comments": "<the manager's overall comments, or null>",
  "strengths": ["<strength 1>", "<strength 2>"],
  "concerns": ["<concern 1>", "<concern 2>"],
  "recommended_rating": <numeric rating recommended by the manager, or null>,
  "summary": "<2-3 sentence summary of key achievements, concerns, and themes>"
}}

Use null or an empty list where the document does not cover a field.
"""


class PerformanceProcessor(BaseProcessor):
    """Domain processor for BusinessDomain.PERFORMANCE
    (`performance_review`, `self_assessment`, `manager_evaluation`)."""

    _SUPPORTED_TYPES = ("performance_review", "self_assessment", "manager_evaluation")

    def __init__(self) -> None:
        super().__init__(
            processor_name="PerformanceProcessor",
            business_domain=BusinessDomain.PERFORMANCE.value,
        )

    def extract(self, content: str, metadata: DocumentMetadata) -> ProcessingResult:
        document_type = metadata.document_type or "unknown"

        if document_type == "performance_review":
            return self._extract_review(content, metadata)
        if document_type == "self_assessment":
            return self._extract_self_assessment(content, metadata)
        if document_type == "manager_evaluation":
            return self._extract_manager_evaluation(content, metadata)

        raise OutputValidationError(
            processor_name=self.processor_name,
            document_type=document_type,
            reason=(
                f"PerformanceProcessor does not support document_type "
                f"'{document_type}'; supported types are "
                f"{self._SUPPORTED_TYPES}."
            ),
        )

    # ----------------------------------------------------------
    # performance_review
    # ----------------------------------------------------------

    def _extract_review(self, content: str, metadata: DocumentMetadata) -> ProcessingResult:
        document_type = "performance_review"
        prompt = _REVIEW_PROMPT_TEMPLATE.format(content=content)
        raw = self._invoke_and_parse(prompt, document_type)

        try:
            extracted = _ExtractedPerformanceReview(**raw)
        except ValidationError as exc:
            raise OutputValidationError(
                processor_name=self.processor_name,
                document_type=document_type,
                reason=f"Extracted review evidence failed schema validation: {exc}",
            ) from exc

        if not extracted.strengths and not extracted.weaknesses and not extracted.summary:
            raise OutputValidationError(
                processor_name=self.processor_name,
                document_type=document_type,
                reason="No usable performance evidence could be extracted.",
            )
        
        confidence = calculate_field_completeness(
            {
                "review_period": extracted.review_period,
                "overall_rating": extracted.overall_rating,
                "strengths": extracted.strengths,
                "weaknesses": extracted.weaknesses,
                "goals_referenced": extracted.goals_referenced,
            },
            _PERFORMANCE_REVIEW_CONFIDENCE_WEIGHTS,
        )

        extracted_data: dict[str, Any] = {
            "review_period": extracted.review_period,
            "overall_rating": extracted.overall_rating,
            "strengths": extracted.strengths,
            "weaknesses": extracted.weaknesses,
            "goals_referenced": extracted.goals_referenced,
        }

        return self.build_result(
            metadata=metadata,
            extracted_data=extracted_data,
            confidence=confidence,
            ai_summary=extracted.summary or "Performance review evidence processed.",
        )

    # ----------------------------------------------------------
    # self_assessment
    # ----------------------------------------------------------

    def _extract_self_assessment(self, content: str, metadata: DocumentMetadata) -> ProcessingResult:
        document_type = "self_assessment"
        prompt = _SELF_ASSESSMENT_PROMPT_TEMPLATE.format(content=content)
        raw = self._invoke_and_parse(prompt, document_type)

        try:
            extracted = _ExtractedSelfAssessment(**raw)
        except ValidationError as exc:
            raise OutputValidationError(
                processor_name=self.processor_name,
                document_type=document_type,
                reason=f"Extracted self-assessment evidence failed schema validation: {exc}",
            ) from exc

        if (
            not extracted.self_reported_achievements
            and not extracted.self_identified_strengths
            and not extracted.self_identified_growth_areas
            and not extracted.summary
        ):
            raise OutputValidationError(
                processor_name=self.processor_name,
                document_type=document_type,
                reason="No usable self-assessment evidence could be extracted.",
            )
        
        confidence = calculate_field_completeness(
            {
                "review_period": extracted.review_period,
                "self_reported_achievements": extracted.self_reported_achievements,
                "self_identified_strengths": extracted.self_identified_strengths,
                "self_identified_growth_areas": extracted.self_identified_growth_areas,
            },
            _SELF_ASSESSMENT_CONFIDENCE_WEIGHTS,
        )

        extracted_data: dict[str, Any] = {
            "review_period": extracted.review_period,
            "self_reported_achievements": extracted.self_reported_achievements,
            "self_identified_strengths": extracted.self_identified_strengths,
            "self_identified_growth_areas": extracted.self_identified_growth_areas,
        }

        return self.build_result(
            metadata=metadata,
            extracted_data=extracted_data,
            confidence=confidence,
            ai_summary=extracted.summary or "Self-assessment evidence processed.",
        )

    # ----------------------------------------------------------
    # manager_evaluation
    # ----------------------------------------------------------

    def _extract_manager_evaluation(self, content: str, metadata: DocumentMetadata) -> ProcessingResult:
        document_type = "manager_evaluation"
        prompt = _MANAGER_EVAL_PROMPT_TEMPLATE.format(content=content)
        raw = self._invoke_and_parse(prompt, document_type)

        try:
            extracted = _ExtractedManagerEvaluation(**raw)
        except ValidationError as exc:
            raise OutputValidationError(
                processor_name=self.processor_name,
                document_type=document_type,
                reason=f"Extracted manager evaluation evidence failed schema validation: {exc}",
            ) from exc

        if not extracted.manager_comments and not extracted.strengths and not extracted.concerns:
            raise OutputValidationError(
                processor_name=self.processor_name,
                document_type=document_type,
                reason="No usable manager evaluation evidence could be extracted.",
            )
        
        confidence = calculate_field_completeness(
            {
                "review_period": extracted.review_period,
                "manager_comments": extracted.manager_comments,
                "strengths": extracted.strengths,
                "concerns": extracted.concerns,
                "recommended_rating": extracted.recommended_rating,
            },
            _MANAGER_EVALUATION_CONFIDENCE_WEIGHTS,
        )

        extracted_data: dict[str, Any] = {
            "review_period": extracted.review_period,
            "manager_comments": extracted.manager_comments,
            "strengths": extracted.strengths,
            "concerns": extracted.concerns,
            "recommended_rating": extracted.recommended_rating,
        }

        return self.build_result(
            metadata=metadata,
            extracted_data=extracted_data,
            confidence=confidence,
            ai_summary=extracted.summary or "Manager evaluation evidence processed.",
        )

    # ----------------------------------------------------------
    # SHARED HELPER
    # ----------------------------------------------------------

    def _invoke_and_parse(self, prompt: str, document_type: str) -> dict[str, Any]:
        """Call the shared LLM and parse its JSON response, raising a
        standardized OutputValidationError on malformed output."""
        response = llm.invoke(prompt)
        try:
            return parse_llm_json(response.content)
        except ValueError as exc:
            raise OutputValidationError(
                processor_name=self.processor_name,
                document_type=document_type,
                reason=f"LLM did not return valid JSON: {exc}",
            ) from exc