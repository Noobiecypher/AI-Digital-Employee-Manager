"""
document_models.py
===================
Shared domain models for the Document Upload & AI Document Ingestion
subsystem.

These models are NOT API contracts — they are the internal data shapes
passed between BaseProcessor, DocumentService, DocumentClassifier,
ProcessorRegistry, BusinessImportService, and the repositories. They
live here (inside document_processing/) rather than under api/ so the
dependency direction stays:

    api  ->  document_processing

and never the reverse. The API layer (document_schemas.py) imports
these models rather than redefining them.

Contents
--------
  Domain enums    : BusinessDomain, DocumentOutcome
  Lifecycle enums : DocumentStatus, ReviewDecision
  Metadata        : DocumentMetadata
  Classification  : ClassificationResult
  Processing      : ProcessingResult
  Draft           : ImportDraft
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class BusinessDomain(str, Enum):
    """
    Business domain a document type belongs to.

    Mirrors the domain agents already present in the workflow system
    (recruitment, hr, sales, research) plus the cross-cutting
    performance domain, which owns both employee-performance and
    business-performance document types per the frozen architecture.
    """

    RECRUITMENT = "recruitment"
    HR = "hr"
    SALES = "sales"
    RESEARCH = "research"
    PERFORMANCE = "performance"


class DocumentOutcome(str, Enum):
    """
    Defines how a successfully processed document is used downstream.
    """

    ENTITY_IMPORT = "entity_import"
    ENTITY_EVIDENCE = "entity_evidence"
    WORKFLOW_SOURCE = "workflow_source"


# ==============================================================
# LIFECYCLE ENUMS
# ==============================================================

class DocumentStatus(str, Enum):
    """
    Lifecycle state of an uploaded document as it moves through the
    ingestion pipeline described in the frozen architecture:

        UPLOADED -> CLASSIFIED -> PROCESSING -> PROCESSED
                  -> PENDING_REVIEW -> APPROVED | REJECTED -> IMPORTED

    FAILED can be entered from any in-flight state.
    """

    UPLOADED = "uploaded"
    CLASSIFIED = "classified"
    PROCESSING = "processing"
    PROCESSED = "processed"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    IMPORTED = "imported"
    FAILED = "failed"


class DraftOperation(str, Enum):
    """Human-review operation performed after approval."""

    CREATE_ENTITY = "create_entity"
    ENRICH_ENTITY = "enrich_entity"
    ATTACH_EVIDENCE = "attach_evidence"
    ENTITY_IMPORT = "entity_import"  # legacy alias; behaves as CREATE_ENTITY


class ReviewDecision(str, Enum):
    """Decision a human reviewer makes on a pending ImportDraft."""

    APPROVED = "approved"
    REJECTED = "rejected"


# ==============================================================
# METADATA
# ==============================================================

class DocumentMetadata(BaseModel):
    """
    Canonical descriptor of a stored document.

    This is the envelope passed to the classifier and to domain
    processors as they operate on a document — it carries identity and
    provenance fields set at upload time, plus classification fields
    that start out empty and are populated once DocumentClassifier has
    run (Milestone 2+).
    """

    model_config = ConfigDict(extra="ignore")

    document_id: str
    original_filename: str
    content_type: str
    size_bytes: int
    uploaded_by: str
    uploaded_at: str
    status: DocumentStatus

    expected_document_type: str | None = None
    target_context: dict[str, Any] = Field(default_factory=dict)

    # Populated after classification. Absent (None) beforehand.
    document_type: str | None = Field(
        default=None,
        description="Classified document type, e.g. 'resume'. Set post-classification.",
    )
    business_domain: BusinessDomain | None = Field(
        default=None,
        description="Business domain the document belongs to.",
    )
    outcome: DocumentOutcome | None = Field(
        default=None,
        description="Downstream usage of the processed document.",
    )

    target_business_entity: str | None = Field(
        default=None,
        description=(
            "Business entity targeted by entity-import or entity-evidence "
            "documents. None for workflow-source documents."
        ),
    )


# ==============================================================
# CLASSIFICATION
# ==============================================================

class ClassificationResult(BaseModel):
    """
    Typed output of the document classifier.

    document_type / business_domain / outcome /
    target_business_entity / review_required are expected to be looked up
    from the Document Registry once a document_type has been determined —
    this model just carries the resolved values, it doesn't resolve them
    itself.
    """

    model_config = ConfigDict(extra="ignore")

    document_id: str
    document_type: str = Field(
        description="Resolved document type key, e.g. 'resume'.",
        examples=["resume"],
    )
    business_domain: BusinessDomain = Field(
        description="Business domain associated with document_type.",
    )
    outcome: DocumentOutcome = Field(
        description="Downstream usage of the processed document."
    )

    target_business_entity: str | None = Field(
        default=None,
        description=(
            "Target business entity for entity-import or entity-evidence "
            "documents. None for workflow-source documents."
        ),
    )
    review_required: bool = Field(
        description="Whether a human must review extracted data before import."
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Classifier confidence score for document_type.",
        examples=[0.94],
    )
    classified_at: str = Field(
        description="ISO 8601 UTC timestamp of when classification ran."
    )


# ==============================================================
# PROCESSING
# ==============================================================

class ProcessingResult(BaseModel):
    """
    Typed output every domain processor (RecruitmentProcessor,
    HRProcessor, SalesProcessor, ResearchProcessor, PerformanceProcessor)
    must return from extraction.

    extracted_data is intentionally a generic dict here — each processor
    is free to define its own more specific extraction shape internally
    and populate extracted_data from it. Keeping this contract generic
    avoids coupling the shared model module to every domain's fields.
    """

    model_config = ConfigDict(extra="ignore")

    document_id: str
    document_type: str
    business_domain: BusinessDomain
    processor_name: str = Field(
        description="Name of the processor that produced this result.",
        examples=["RecruitmentProcessor"],
    )
    extracted_data: dict[str, Any] = Field(
        description="Structured data extracted from the document content."
    )
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Optional processor-reported confidence in the extraction.",
    )
    processed_at: str = Field(
        description="ISO 8601 UTC timestamp of when extraction completed."
    )
    ai_summary: str | None = None


# ==============================================================
# DRAFT
# ==============================================================

class ImportDraft(BaseModel):
    """
    Pending record awaiting human review before BusinessImportService
    is allowed to write it into a business collection.

    This is the object persisted by the future import_draft_repository.py
    and is the only artifact BusinessImportService is allowed to consume.
    """

    model_config = ConfigDict(extra="ignore")

    draft_id: str
    document_id: str
    business_domain: BusinessDomain
    target_business_entity: str
    operation: DraftOperation = DraftOperation.CREATE_ENTITY
    target_entity_key: str | None = None
    target_context: dict[str, Any] = Field(default_factory=dict)
    extracted_data: dict[str, Any] = Field(
        description="Extracted data awaiting review, as produced by a ProcessingResult."
    )
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Optional confidence score from the ProcessingResult.",
    )
    source_document_ids: list[str] = Field(
        default_factory=list,
        description="Documents that contributed to this import draft.",
    )
    status: DocumentStatus = Field(
        default=DocumentStatus.PENDING_REVIEW,
        description="One of PENDING_REVIEW, APPROVED, REJECTED, or IMPORTED.",
    )
    created_at: str = Field(
        description="ISO 8601 UTC timestamp of draft creation."
    )
    updated_at: str = Field(
        description="ISO 8601 UTC timestamp of the most recent draft update."
    )
    reviewed_by: str | None = Field(
        default=None,
        description="Identifier of the reviewer, once reviewed.",
    )
    review_notes: str | None = Field(
        default=None,
        max_length=2000,
        description="Optional notes left by the reviewer.",
    )
    ai_summary: str | None = Field(
        default=None,
        description="AI-generated summary carried from the ProcessingResult.",
    )
