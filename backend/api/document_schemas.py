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
    DocumentStatus,
    ReviewDecision,
)


# ==============================================================
# UPLOAD / STATUS
# ==============================================================

class DocumentUploadResponse(BaseModel):
    """Returned immediately after a document has been accepted and stored."""

    model_config = ConfigDict(extra="ignore")

    document_id: str = Field(
        description="Server-generated identifier for the stored document."
    )
    original_filename: str
    status: DocumentStatus = Field(
        default=DocumentStatus.UPLOADED,
        description="Always UPLOADED at this point in the lifecycle.",
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
    """
    Payload submitted by a human reviewer to approve or reject an
    ImportDraft.

    edited_data allows the reviewer to correct extracted fields before
    approval without requiring re-processing; when omitted, the
    draft's existing extracted_data is used as-is.
    """

    model_config = ConfigDict(extra="forbid")

    decision: ReviewDecision = Field(
        description="Reviewer's decision on this draft."
    )
    reviewer_notes: str | None = Field(
        default=None,
        max_length=2000,
        description="Optional free-text notes explaining the decision.",
    )
    edited_data: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Optional corrections to extracted_data made by the reviewer "
            "prior to approval. Omit to accept the extracted data as-is."
        ),
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
