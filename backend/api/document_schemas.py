"""
document_schemas.py
====================
API request / response contracts for the Document Upload & AI Document
Ingestion subsystem.

This module contains ONLY schemas that describe the shape of data
crossing the HTTP boundary. Shared domain models used internally across
the ingestion subsystem (DocumentStatus, ReviewDecision, DocumentMetadata,
ClassificationResult, ProcessingResult, ImportDraft) live in
backend/document_processing/document_models.py and are imported here
rather than redefined, keeping the dependency direction:

    api  ->  document_processing

Note on uploads
----------------
There is no DocumentUploadRequest model. The upload endpoint accepts a
multipart request via FastAPI's `UploadFile` and `Form(...)` /
`File(...)` parameters directly in the route signature — a Pydantic
model would not add value for a multipart body and is intentionally
not introduced here.

Design principles (mirrors business_schemas.py)
------------------------------------------------
Request schemas  — ConfigDict(extra="forbid")
    Strict: unknown fields in the JSON body cause an immediate 422.

Response schemas — ConfigDict(extra="ignore")
    Lenient: fields present in stored documents but not modelled here
    are silently dropped, so the API can evolve without breaking
    existing callers.

Schema index
------------
  Upload / Status : DocumentUploadResponse, DocumentStatusResponse
  Review          : DocumentReviewRequest, DocumentReviewResponse
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.document_processing.document_models import (
    BusinessDomain,
    ClassificationResult,
    DocumentOutcome,
    DocumentStatus,
    DraftOperation,
    ProcessingResult,
    ReviewDecision,
)
from backend.document_processing.document_registry import FileFormat


# ==============================================================
# UPLOAD / STATUS
# ==============================================================

class DocumentUploadResponse(BaseModel):
    """Returned after upload and classification complete successfully."""

    model_config = ConfigDict(extra="ignore")

    document_id: str = Field(
        description="Server-generated identifier for the stored document."
    )
    original_filename: str
    status: DocumentStatus = Field(
        default=DocumentStatus.CLASSIFIED,
        description=(
            "Lifecycle status after successful upload, extraction, "
            "classification, and declared-type verification."
        ),
    )
    uploaded_at: str = Field(
        description="ISO 8601 UTC timestamp of when the upload was stored."
    )
    message: str = Field(
        default="Document uploaded successfully.",
        description="Human-readable confirmation message.",
    )


class DocumentStatusResponse(BaseModel):
    """Narrow read model for polling a document's current pipeline status."""

    model_config = ConfigDict(extra="ignore")

    document_id: str
    status: DocumentStatus
    created_at: str | None = Field(
        default=None,
        description="ISO 8601 UTC timestamp of when the document was uploaded.",
    )
    updated_at: str = Field(
        description="ISO 8601 UTC timestamp of the most recent status change."
    )
    error_message: str | None = Field(
        default=None,
        description="Populated only when status == FAILED.",
    )


# ==============================================================
# REVIEW
# ==============================================================

class DocumentReviewRequest(BaseModel):
    """Payload submitted to approve or reject an ImportDraft."""

    model_config = ConfigDict(extra="forbid")

    decision: ReviewDecision = Field(
        description="Reviewer's decision on this draft."
    )
    reviewer_notes: str | None = Field(
        default=None,
        max_length=2000,
        description="Optional free-text notes explaining the decision.",
    )



class DocumentReviewResponse(BaseModel):
    """Returned after a review decision has been recorded against a draft."""

    model_config = ConfigDict(extra="ignore")

    draft_id: str
    document_id: str
    decision: ReviewDecision
    status: DocumentStatus = Field(
        description="Resulting draft status: APPROVED or REJECTED."
    )
    reviewed_by: str
    reviewed_at: str = Field(
        description="ISO 8601 UTC timestamp of when the review was recorded."
    )
    message: str = Field(
        default="Review recorded successfully.",
        description="Human-readable confirmation message.",
    )


# ==============================================================
# DOCUMENT TYPES  (M7)
# ==============================================================

class DocumentTypeInfo(BaseModel):
    """One DOCUMENT_TYPE_REGISTRY entry, shaped for the upload form."""

    model_config = ConfigDict(extra="ignore")

    document_type: str
    business_domain: BusinessDomain
    outcome: DocumentOutcome
    target_business_entity: str | None = None
    required_target_context_fields: list[str] = Field(default_factory=list)
    review_required: bool
    supported_formats: list[FileFormat]


class DocumentTypeListResponse(BaseModel):
    """Response for GET /documents/types."""

    model_config = ConfigDict(extra="ignore")

    total: int
    items: list[DocumentTypeInfo]


# ==============================================================
# PROCESSING  (M7)
# ==============================================================

class DocumentProcessResponse(BaseModel):
    """Returned by POST /documents/{document_id}/process."""

    model_config = ConfigDict(extra="ignore")

    document_id: str
    status: DocumentStatus
    draft_id: str | None = Field(
        default=None,
        description="Set only when processing produced an ImportDraft.",
    )
    message: str


# ==============================================================
# LIST / DETAIL  (M7)
# ==============================================================

class DocumentListItem(BaseModel):
    """One row in GET /documents. Narrower than the detail view."""

    model_config = ConfigDict(extra="ignore")

    document_id: str
    original_filename: str
    content_type: str
    size_bytes: int
    uploaded_by: str
    uploaded_at: str
    status: DocumentStatus
    expected_document_type: str | None = None
    document_type: str | None = None
    business_domain: BusinessDomain | None = None
    outcome: DocumentOutcome | None = None
    target_business_entity: str | None = None
    updated_at: str | None = None


class DocumentListResponse(BaseModel):
    """Response for GET /documents."""

    model_config = ConfigDict(extra="ignore")

    total: int
    items: list[DocumentListItem]


class DocumentDetailResponse(BaseModel):
    """Response for GET /documents/{document_id}."""

    model_config = ConfigDict(extra="ignore")

    document_id: str
    original_filename: str
    content_type: str
    size_bytes: int
    uploaded_by: str
    uploaded_at: str
    updated_at: str | None = None
    status: DocumentStatus
    expected_document_type: str | None = None
    document_type: str | None = None
    business_domain: BusinessDomain | None = None
    outcome: DocumentOutcome | None = None
    target_business_entity: str | None = None
    target_context: dict[str, Any] = Field(default_factory=dict)
    classification: ClassificationResult | None = Field(
        default=None,
        description="Independent AI classification result, once classified.",
    )
    processing_result: ProcessingResult | None = Field(
        default=None,
        description=(
            "Structured extraction result (ai_summary + extracted_data), "
            "once processed. Never contains the raw extracted document text."
        ),
    )
    processing_history: list[dict[str, Any]] = Field(default_factory=list)
    error_message: str | None = Field(
        default=None,
        description="Populated only when status == FAILED.",
    )


# ==============================================================
# WORKFLOW SELECTOR  (M7)
# ==============================================================

class EligibleDocumentItem(BaseModel):
    """One selectable document for a workflow-source input slot."""

    model_config = ConfigDict(extra="ignore")

    document_id: str
    original_filename: str
    document_type: str | None = None
    status: DocumentStatus
    uploaded_at: str
    ai_summary: str | None = None


class EligibleDocumentsResponse(BaseModel):
    """Response for GET /documents/eligible."""

    model_config = ConfigDict(extra="ignore")

    workflow_slot: str
    total: int
    items: list[EligibleDocumentItem]


# ==============================================================
# DRAFT REVIEW AND IMPORT  (M7)
# ==============================================================

class ImportDraftResponse(BaseModel):
    """Full draft record, for GET /documents/drafts and .../{draft_id}."""

    model_config = ConfigDict(extra="ignore")

    draft_id: str
    document_id: str
    business_domain: BusinessDomain
    target_business_entity: str
    operation: DraftOperation
    target_entity_key: str | None = None
    target_context: dict[str, Any] = Field(default_factory=dict)
    extracted_data: dict[str, Any]
    confidence: float | None = None
    source_document_ids: list[str] = Field(default_factory=list)
    status: DocumentStatus
    created_at: str | None = None
    updated_at: str | None = None
    reviewed_by: str | None = None
    review_notes: str | None = None
    ai_summary: str | None = None


class ImportDraftListResponse(BaseModel):
    """Response for GET /documents/drafts."""

    model_config = ConfigDict(extra="ignore")

    total: int
    items: list[ImportDraftResponse]


class DraftReviewedDataUpdateRequest(BaseModel):
    """Payload for PATCH /documents/drafts/{draft_id}."""

    model_config = ConfigDict(extra="forbid")

    extracted_data: dict[str, Any] = Field(
        description=(
            "Corrected/completed extracted data. For CREATE_ENTITY and "
            "ATTACH_EVIDENCE drafts this replaces extracted_data outright; "
            "for ENRICH_ENTITY drafts this is merged as a partial patch "
            "over the proposed final Product state, per existing M6.5 "
            "semantics preserved by ImportDraftService."
        )
    )


class DraftImportResponse(BaseModel):
    """Returned by POST /documents/drafts/{draft_id}/import."""

    model_config = ConfigDict(extra="ignore")

    draft_id: str
    document_id: str
    target_business_entity: str
    entity: dict[str, Any]
    status: DocumentStatus
    reused_existing_entity: bool
    message: str


# ==============================================================
# DRAFT REVIEW REQUIREMENTS  (M7 hardening)
# ==============================================================

class FieldRequirement(BaseModel):
    """
    One field's frontend review-form requirements.

    Resolved by backend.services.review_contract_service from the real
    business request schema (required/type/constraints) plus a small
    UI-only metadata mapping (label/input_type/order). Never a
    hand-duplicated copy of validation rules.
    """

    model_config = ConfigDict(extra="ignore")

    field_name: str = Field(description="Key expected in extracted_data.")
    label: str = Field(description="Human-readable field label.")
    field_type: str = Field(
        description="Underlying data type, e.g. 'string', 'integer', 'array'."
    )
    input_type: str = Field(
        description="UI-only rendering hint, e.g. 'text', 'number', 'tag_list'."
    )
    required: bool = Field(
        description="Whether the real business schema requires this field."
    )
    order: int = Field(description="Suggested display order, ascending.")
    constraints: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Relevant validation constraints taken directly from the real "
            "business schema (e.g. minLength, maxLength, minimum, maximum, "
            "pattern, default). Empty when the field has none."
        ),
    )


class DraftRequirementsResponse(BaseModel):
    """Response for GET /documents/drafts/{draft_id}/requirements."""

    model_config = ConfigDict(extra="ignore")

    draft_id: str
    target_business_entity: str
    operation: DraftOperation
    fields: list[FieldRequirement] = Field(
        default_factory=list,
        description=(
            "Empty when the draft's (target_business_entity, operation) "
            "combination has no schema-based business contract "
            "(e.g. ATTACH_EVIDENCE evidence drafts)."
        ),
    )
