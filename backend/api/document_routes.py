"""
document_routes.py
===================
FastAPI APIRouter exposing the Document Upload & AI Document Ingestion
subsystem (Milestones 1-6.6) over HTTP (Milestone 7).

Registered in main.py under the '/documents' prefix:

    app.include_router(
        document_router,
        prefix="/documents",
        tags=["documents"],
    )

This router is API integration only. It never redesigns the processing
pipeline, never runs classifiers/processors directly, and never writes
to business collections directly — every mutation is delegated to the
existing M1-M6.6 services:

    DocumentService              — upload / classify
    DocumentProcessingService    — explicit one-time processing
    ImportDraftService           — reviewed-data edits, approve/reject
    BusinessImportService        — approved draft -> business entity
    DocumentLifecycleService     — conditional admin deletion (M7)

Route ordering
--------------
Static-path routes (/types, /upload, /eligible, /drafts, /drafts/...)
are declared before the dynamic /{document_id} routes so FastAPI never
lets a document_id path parameter capture a static segment.

Error contract  (mirrors business_routes.py / routes.py exactly)
------------------------------------------------------------------
All error responses share the same JSON envelope:
    {
        "error": {
            "code":    "<SCREAMING_SNAKE_CASE>",
            "message": "<human-readable string>",
            "field":   "<dotted.field.name> | null",
            "details": null
        }
    }
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)

from backend.auth.dependencies import require_permission
from backend.auth.permissions import Permission

from backend.database.document_repository import DocumentRepository
from backend.database.import_draft_repository import ImportDraftRepository

from backend.document_processing.document_models import (
    BusinessDomain,
    DocumentOutcome,
    DocumentStatus,
    DraftOperation,
    ReviewDecision,
)
from backend.document_processing.document_registry import (
    DOCUMENT_TYPE_REGISTRY,
    get_document_type_config,
)

from backend.services.document_service import DocumentService, DocumentServiceError
from backend.services.document_processing_service import (
    DocumentProcessingError,
    DocumentProcessingService,
)
from backend.services.import_draft_service import (
    DraftValidationError,
    ImportDraftService,
    ImportDraftServiceError,
)
from backend.services.business_import_service import (
    BusinessImportError,
    BusinessImportService,
)
from backend.services.document_lifecycle_service import (
    DocumentLifecycleError,
    DocumentLifecycleNotFoundError,
    DocumentLifecycleService,
    DocumentNotDeletableError,
)
from backend.services.review_contract_service import (
    get_field_requirements,
    resolve_operation,
)

# NOTE (deviation — see final report item 7): the milestone brief names
# this module "backend/workflow_document_resolution.py", but the actual
# codebase (per routes.py: `from backend.execution.workflow_document_resolution
# import build_shortlisted_resume_summaries`) locates it at
# backend/execution/workflow_document_resolution.py. Importing the real
# path so the eligibility rules used here are byte-for-byte the same
# constants the workflow executor validates against.
from backend.execution.workflow_document_resolution import (
    MARKET_RESEARCH_ALLOWED_TYPES,
    PERFORMANCE_REPORT_HR_ALLOWED_TYPES,
    PERFORMANCE_REPORT_SALES_ALLOWED_TYPES,
)

from backend.api.document_schemas import (
    DocumentDetailResponse,
    DocumentListItem,
    DocumentListResponse,
    DocumentProcessResponse,
    DocumentReviewRequest,
    DocumentReviewResponse,
    DocumentStatusResponse,
    DocumentTypeInfo,
    DocumentTypeListResponse,
    DocumentUploadResponse,
    DraftImportResponse,
    DraftRequirementsResponse,
    DraftReviewedDataUpdateRequest,
    EligibleDocumentItem,
    EligibleDocumentsResponse,
    FieldRequirement,
    ImportDraftListResponse,
    ImportDraftResponse,
)

logger = logging.getLogger(__name__)

document_router = APIRouter()

# ---------------------------------------------------------------------------
# Service / repository singletons.
# Collection resolution inside repositories is lazy — no DB call happens
# at import time, mirroring business_routes.py / routes.py.
# ---------------------------------------------------------------------------

_document_repo = DocumentRepository()
_import_draft_repo = ImportDraftRepository()

_document_service = DocumentService()
_processing_service = DocumentProcessingService()
_import_draft_service = ImportDraftService()
_business_import_service = BusinessImportService()
_lifecycle_service = DocumentLifecycleService()

_ELIGIBLE_SLOT_TYPES: dict[str, set[str]] = {
    "market_research": MARKET_RESEARCH_ALLOWED_TYPES,
    "performance_report.hr": PERFORMANCE_REPORT_HR_ALLOWED_TYPES,
    "performance_report.sales": PERFORMANCE_REPORT_SALES_ALLOWED_TYPES,
}


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def error_response(
    status_code: int,
    code: str,
    message: str,
    field: str | None = None,
    details: dict[str, Any] | None = None,
) -> HTTPException:
    """
    Build a structured HTTPException matching the project error contract.

    Intentionally duplicated from routes.py / business_routes.py to keep
    this router fully self-contained (same convention already used
    between those two).

    `details` defaults to None, preserving the existing envelope for
    every pre-existing caller. It is populated only where a caller has
    genuinely structured extra information to convey (e.g. field-level
    draft validation errors).
    """
    return HTTPException(
        status_code=status_code,
        detail={
            "error": {
                "code": code,
                "message": message,
                "field": field,
                "details": details,
            }
        },
    )


def _actor_identity(current_user: dict[str, Any]) -> str:
    """
    Resolve a stable identity string for the authenticated user, for use
    as `uploaded_by` / `reviewed_by`. Never accepted from the client.

    UserRepository's exact document shape wasn't available to inspect
    (see final report item 7); this checks the fields already relied on
    elsewhere in the codebase (business_routes.py / ownership.py) in
    order of preference, falling back to role if nothing more specific
    is present rather than raising.
    """
    return (
        current_user.get("user_id")
        or current_user.get("email")
        or current_user.get("full_name")
        or current_user.get("employee_id")
        or current_user.get("role")
        or "unknown"
    )


def _metadata_of(document: dict) -> dict:
    return document.get("metadata") or {}


def _to_list_item(document: dict) -> DocumentListItem:
    metadata = _metadata_of(document)
    return DocumentListItem(
        document_id=document["document_id"],
        original_filename=metadata.get("original_filename"),
        content_type=metadata.get("content_type"),
        size_bytes=metadata.get("size_bytes"),
        uploaded_by=metadata.get("uploaded_by"),
        uploaded_at=metadata.get("uploaded_at"),
        status=DocumentStatus(metadata["status"]),
        expected_document_type=metadata.get("expected_document_type"),
        document_type=metadata.get("document_type"),
        business_domain=metadata.get("business_domain"),
        outcome=metadata.get("outcome"),
        target_business_entity=metadata.get("target_business_entity"),
        updated_at=document.get("updated_at"),
    )


def _to_detail_response(document: dict) -> DocumentDetailResponse:
    metadata = _metadata_of(document)
    return DocumentDetailResponse(
        document_id=document["document_id"],
        original_filename=metadata.get("original_filename"),
        content_type=metadata.get("content_type"),
        size_bytes=metadata.get("size_bytes"),
        uploaded_by=metadata.get("uploaded_by"),
        uploaded_at=metadata.get("uploaded_at"),
        updated_at=document.get("updated_at"),
        status=DocumentStatus(metadata["status"]),
        expected_document_type=metadata.get("expected_document_type"),
        document_type=metadata.get("document_type"),
        business_domain=metadata.get("business_domain"),
        outcome=metadata.get("outcome"),
        target_business_entity=metadata.get("target_business_entity"),
        target_context=metadata.get("target_context") or {},
        classification=document.get("classification"),
        processing_result=document.get("processing_result"),
        processing_history=document.get("processing_history") or [],
        error_message=document.get("error_message"),
    )


def _to_eligible_item(document: dict) -> EligibleDocumentItem:
    metadata = _metadata_of(document)
    processing_result = document.get("processing_result") or {}
    return EligibleDocumentItem(
        document_id=document["document_id"],
        original_filename=metadata.get("original_filename"),
        document_type=metadata.get("document_type"),
        status=DocumentStatus(metadata["status"]),
        uploaded_at=metadata.get("uploaded_at"),
        ai_summary=processing_result.get("ai_summary"),
    )


# ---------------------------------------------------------------------------
# Error mapping
# ---------------------------------------------------------------------------

def _map_document_service_error(exc: DocumentServiceError) -> HTTPException:
    reason = exc.reason
    if "Declared document type mismatch" in reason:
        return error_response(
            status.HTTP_409_CONFLICT,
            "DECLARED_TYPE_MISMATCH",
            reason,
            "expected_document_type",
        )
    logger.error(
        "Document service error (document_id=%s): %s",
        exc.document_id,
        reason,
    )
    return error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "INTERNAL_SERVER_ERROR",
        "Document upload failed due to an internal processing error.",
    )


def _map_processing_error(exc: DocumentProcessingError) -> HTTPException:
    reason = exc.reason
    lowered = reason.lower()
    if "not found" in lowered:
        return error_response(
            status.HTTP_404_NOT_FOUND, "DOCUMENT_NOT_FOUND", reason, "document_id"
        )
    if (
        "cannot process document" in lowered
        or "manual intervention is required" in lowered
        or "integrity/idempotency violation" in lowered
        or "invalid lifecycle status" in lowered
        or "failed to synchronize" in lowered
    ):
        return error_response(status.HTTP_409_CONFLICT, "PROCESSING_CONFLICT", reason)
    logger.error(
        "Document processing error (document_id=%s): %s", exc.document_id, reason
    )
    return error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR, "INTERNAL_SERVER_ERROR", reason
    )


def _map_import_draft_error(
    exc: ImportDraftServiceError, not_found_field: str = "draft_id"
) -> HTTPException:
    reason = exc.reason
    lowered = reason.lower()
    if "not found" in lowered:
        return error_response(
            status.HTTP_404_NOT_FOUND, "DRAFT_NOT_FOUND", reason, not_found_field
        )
    if "invalid reviewed product state" in lowered or "final reviewed" in lowered:
        return error_response(status.HTTP_422_UNPROCESSABLE_ENTITY, "VALIDATION_ERROR", reason)
    if (
        "pending review" in lowered
        or "conflicting lifecycle status" in lowered
        or "cannot change draft" in lowered
        or "cannot synchronize document" in lowered
        or "cannot complete" in lowered
        or "missing its canonical product_name" in lowered
        or "unsupported editable operation" in lowered
        or "cannot use enrich_entity" in lowered
        or "requires an explicit target product" in lowered
        or "only valid for evidence drafts" in lowered
    ):
        return error_response(status.HTTP_409_CONFLICT, "DRAFT_CONFLICT", reason)
    logger.error("Import draft service error (draft_id=%s): %s", exc.draft_id, reason)
    return error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR, "INTERNAL_SERVER_ERROR", reason
    )


def _map_business_import_error(exc: BusinessImportError) -> HTTPException:
    reason = exc.reason
    lowered = reason.lower()
    if "not found" in lowered and "final reviewed" not in lowered:
        return error_response(
            status.HTTP_404_NOT_FOUND, "DRAFT_NOT_FOUND", reason, "draft_id"
        )
    if "is invalid" in lowered and "final reviewed" in lowered:
        return error_response(status.HTTP_422_UNPROCESSABLE_ENTITY, "VALIDATION_ERROR", reason)
    if (
        "requires an approved draft" in lowered
        or "identity conflict" in lowered
        or "cannot complete" in lowered
        or "unsupported target business entity" in lowered
        or "unsupported draft operation" in lowered
        or "is supported only for product drafts" in lowered
        or "requires an explicit target product" in lowered
        or "requires employee_name and review_period" in lowered
        or "target product" in lowered
    ):
        return error_response(status.HTTP_409_CONFLICT, "IMPORT_CONFLICT", reason)
    logger.error("Business import error (draft_id=%s): %s", exc.draft_id, reason)
    return error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR, "INTERNAL_SERVER_ERROR", reason
    )


# ===========================================================================
# 1. DOCUMENT TYPES
# ===========================================================================

@document_router.get(
    "/types",
    response_model=DocumentTypeListResponse,
    summary="List supported document types",
    description=(
        "Return every document type in DOCUMENT_TYPE_REGISTRY, including "
        "the business domain, downstream outcome, target business entity, "
        "whether human review is required, and supported file formats — "
        "everything the frontend upload form needs. The registry is the "
        "single source of truth; this endpoint never duplicates it."
    ),
)
async def list_document_types_route(
    _: dict = Depends(require_permission(Permission.DOCUMENTS_READ)),
) -> DocumentTypeListResponse:
    items = [
        DocumentTypeInfo(
            document_type=key,
            business_domain=config.business_domain,
            outcome=config.outcome,
            target_business_entity=config.target_business_entity,
            required_target_context_fields=config.required_target_context_fields,
            review_required=config.review_required,
            supported_formats=config.supported_formats,
        )
        for key, config in sorted(DOCUMENT_TYPE_REGISTRY.items())
    ]
    return DocumentTypeListResponse(total=len(items), items=items)


# ===========================================================================
# 2. UPLOAD
# ===========================================================================

@document_router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a document and verify its declared type",
    description=(
        "Store the uploaded file, extract its text, independently classify "
        "it, and verify the classification against `expected_document_type`. "
        "This does NOT process or import the document — call POST "
        "/documents/{document_id}/process explicitly afterward. Usable "
        "directly from Swagger UI with a local file."
    ),
)
async def upload_document_route(
    file: UploadFile = File(..., description="The file to upload."),
    expected_document_type: str = Form(
        ..., description="Declared document type key, e.g. 'resume'."
    ),
    target_context: str | None = Form(
        default=None,
        description=(
            "Optional JSON object (as a string) providing target context, "
            "e.g. '{\"employee_name\": \"Alice\", \"review_period\": \"Q2\"}'."
        ),
    ),
    current_user: dict = Depends(require_permission(Permission.DOCUMENTS_UPLOAD)),
) -> DocumentUploadResponse:
    try:
        type_config = get_document_type_config(expected_document_type)
    except ValueError as exc:
        raise error_response(
            status.HTTP_400_BAD_REQUEST,
            "INVALID_DOCUMENT_TYPE",
            str(exc),
            "expected_document_type",
        )

    parsed_context: dict[str, Any] = {}
    if target_context:
        try:
            parsed = json.loads(target_context)
        except json.JSONDecodeError as exc:
            raise error_response(
                status.HTTP_400_BAD_REQUEST,
                "INVALID_TARGET_CONTEXT",
                f"target_context is not valid JSON: {exc}",
                "target_context",
            )
        if not isinstance(parsed, dict):
            raise error_response(
                status.HTTP_400_BAD_REQUEST,
                "INVALID_TARGET_CONTEXT",
                "target_context must be a JSON object.",
                "target_context",
            )
        parsed_context = parsed

    required_context_fields = set(type_config.required_target_context_fields)
    provided_context_fields = set(parsed_context)

    missing_context_fields = sorted(
        field
        for field in required_context_fields
        if (
            field not in parsed_context
            or not isinstance(parsed_context[field], str)
            or not parsed_context[field].strip()
        )
    )

    if missing_context_fields:
        raise error_response(
            status.HTTP_400_BAD_REQUEST,
            "INVALID_TARGET_CONTEXT",
            (
                "Missing or invalid required target_context fields: "
                f"{missing_context_fields}."
            ),
            "target_context",
            details={"required_fields": sorted(required_context_fields)},
        )
    
    unexpected_context_fields = sorted(
        provided_context_fields - required_context_fields
    )

    if unexpected_context_fields:
        raise error_response(
            status.HTTP_400_BAD_REQUEST,
            "INVALID_TARGET_CONTEXT",
            (
                "Unexpected target_context fields: "
                f"{unexpected_context_fields}."
            ),
            "target_context",
            details={"allowed_fields": sorted(required_context_fields)},
        )

    original_filename = file.filename or ""
    extension = (
        original_filename.rsplit(".", 1)[-1].lower()
        if "." in original_filename
        else ""
    )
    supported = {fmt.value for fmt in type_config.supported_formats}
    if extension not in supported:
        raise error_response(
            status.HTTP_400_BAD_REQUEST,
            "UNSUPPORTED_FILE_FORMAT",
            (
                f"File extension '.{extension}' is not supported for "
                f"document type '{expected_document_type}'. Supported "
                f"formats: {sorted(supported)}."
            ),
            "file",
        )

    content = await file.read()
    if not content:
        raise error_response(
            status.HTTP_400_BAD_REQUEST, "EMPTY_FILE", "Uploaded file is empty.", "file"
        )

    uploaded_by = _actor_identity(current_user)

    try:
        document = _document_service.upload_document(
            content=content,
            original_filename=original_filename,
            content_type=file.content_type or "application/octet-stream",
            uploaded_by=uploaded_by,
            expected_document_type=expected_document_type,
            target_context=parsed_context,
        )
    except DocumentServiceError as exc:
        raise _map_document_service_error(exc)

    metadata = _metadata_of(document)
    return DocumentUploadResponse(
        document_id=document["document_id"],
        original_filename=metadata.get("original_filename"),
        status=DocumentStatus(metadata["status"]),
        uploaded_at=metadata.get("uploaded_at"),
        message="Document uploaded and classified successfully.",
    )


# ===========================================================================
# 5. WORKFLOW SELECTOR  (registered before /{document_id} — static path)
# ===========================================================================

@document_router.get(
    "/eligible",
    response_model=EligibleDocumentsResponse,
    summary="List documents eligible for a workflow-source selection slot",
    description=(
        "Return lightweight selector data for one workflow input slot — "
        "market_research, performance_report.hr, or performance_report.sales "
        "— so the frontend never has to load every processed document and "
        "reproduce M6.6 eligibility rules itself. Only PROCESSED documents "
        "of the slot's allowed document_type(s) are returned."
    ),
)
async def list_eligible_documents_route(
    workflow_slot: str = Query(
        ...,
        description=(
            "One of: 'market_research', 'performance_report.hr', "
            "'performance_report.sales'."
        ),
    ),
    _: dict = Depends(require_permission(Permission.DOCUMENTS_READ)),
) -> EligibleDocumentsResponse:
    allowed_types = _ELIGIBLE_SLOT_TYPES.get(workflow_slot)
    if allowed_types is None:
        raise error_response(
            status.HTTP_400_BAD_REQUEST,
            "INVALID_WORKFLOW_SLOT",
            (
                f"Unknown workflow_slot '{workflow_slot}'. Supported: "
                f"{sorted(_ELIGIBLE_SLOT_TYPES)}."
            ),
            "workflow_slot",
        )

    try:
        raw_items: list[dict] = []
        for document_type in sorted(allowed_types):
            raw_items.extend(
                _document_repo.search_documents(
                    document_type=document_type,
                    processing_status=DocumentStatus.PROCESSED,
                )
            )
    except RuntimeError as exc:
        logger.error("list_eligible_documents route error: %s", exc)
        raise error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "INTERNAL_SERVER_ERROR", str(exc)
        )

    items = [_to_eligible_item(d) for d in raw_items]
    return EligibleDocumentsResponse(
        workflow_slot=workflow_slot, total=len(items), items=items
    )


# ===========================================================================
# 6. DRAFT REVIEW AND IMPORT  (static /drafts... paths, before /{document_id})
# ===========================================================================

@document_router.get(
    "/drafts",
    response_model=ImportDraftListResponse,
    summary="List import drafts",
    description=(
        "Return import drafts, optionally filtered by document ID, review "
        "status, operation, and target business entity."
    ),
)
async def list_drafts_route(
    status_filter: DocumentStatus | None = Query(default=None, alias="status"),
    document_id: str | None = Query(default=None),
    operation: DraftOperation | None = Query(default=None),
    target_business_entity: str | None = Query(default=None),
    _: dict = Depends(require_permission(Permission.DOCUMENTS_REVIEW)),
) -> ImportDraftListResponse:
    try:
        drafts = _import_draft_repo.list_drafts(
            status=status_filter, document_id=document_id
        )
    except RuntimeError as exc:
        logger.error("list_drafts route error: %s", exc)
        raise error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "INTERNAL_SERVER_ERROR", str(exc)
        )

    # ImportDraftRepository.list_drafts() does not natively filter on
    # operation / target_business_entity; drafts are a low-volume,
    # human-review collection, so filtering the already-fetched (and
    # status/document_id-narrowed) result set here is not "loading all
    # records to fake pagination" — no pagination is requested for drafts.
    if operation is not None:
        drafts = [d for d in drafts if d.get("operation") == operation.value]
    if target_business_entity is not None:
        drafts = [
            d
            for d in drafts
            if d.get("target_business_entity") == target_business_entity
        ]

    return ImportDraftListResponse(
        total=len(drafts), items=[ImportDraftResponse(**d) for d in drafts]
    )


@document_router.get(
    "/drafts/{draft_id}",
    response_model=ImportDraftResponse,
    summary="Get one import draft",
    description="Return the full record for one ImportDraft by draft_id.",
)
async def get_draft_route(
    draft_id: str,
    _: dict = Depends(require_permission(Permission.DOCUMENTS_REVIEW)),
) -> ImportDraftResponse:
    try:
        draft = _import_draft_repo.get_import_draft(draft_id)
    except ValueError as exc:
        raise error_response(
            status.HTTP_404_NOT_FOUND, "DRAFT_NOT_FOUND", str(exc), "draft_id"
        )
    except RuntimeError as exc:
        logger.error("get_draft('%s') route error: %s", draft_id, exc)
        raise error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "INTERNAL_SERVER_ERROR", str(exc)
        )
    return ImportDraftResponse(**draft)


@document_router.get(
    "/drafts/{draft_id}/requirements",
    response_model=DraftRequirementsResponse,
    summary="Get review-form field requirements for a draft",
    description=(
        "Load the draft, resolve its real business contract (by "
        "target_business_entity + operation), and return frontend-"
        "friendly field requirements — label, field type, input type, "
        "required flag, order, and constraints — derived directly from "
        "the same Pydantic business schema used for final validation. "
        "Read-only: never mutates the draft. `fields` is empty when the "
        "draft's combination has no schema-based business contract "
        "(e.g. ATTACH_EVIDENCE evidence drafts)."
    ),
)
async def get_draft_requirements_route(
    draft_id: str,
    _: dict = Depends(require_permission(Permission.DOCUMENTS_REVIEW)),
) -> DraftRequirementsResponse:
    try:
        draft = _import_draft_repo.get_import_draft(draft_id)
    except ValueError as exc:
        raise error_response(
            status.HTTP_404_NOT_FOUND, "DRAFT_NOT_FOUND", str(exc), "draft_id"
        )
    except RuntimeError as exc:
        logger.error(
            "get_draft_requirements('%s') route error: %s", draft_id, exc
        )
        raise error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "INTERNAL_SERVER_ERROR", str(exc)
        )

    operation = resolve_operation(
        draft.get("operation", DraftOperation.CREATE_ENTITY.value)
    )
    resolved_fields = get_field_requirements(
        draft["target_business_entity"], operation
    ) or []

    return DraftRequirementsResponse(
        draft_id=draft["draft_id"],
        target_business_entity=draft["target_business_entity"],
        operation=operation,
        fields=[
            FieldRequirement(
                field_name=item.field_name,
                label=item.label,
                field_type=item.field_type,
                input_type=item.input_type,
                required=item.required,
                order=item.order,
                constraints=item.constraints,
            )
            for item in resolved_fields
        ],
    )


@document_router.patch(
    "/drafts/{draft_id}",
    response_model=ImportDraftResponse,
    summary="Update a draft's reviewed data",
    description=(
        "Correct or complete extracted_data while the draft is still "
        "PENDING_REVIEW. All patch/merge semantics — including the M6.5 "
        "ENRICH_ENTITY partial-patch behavior — are delegated entirely to "
        "ImportDraftService; this route performs no merging itself."
    ),
)
async def update_draft_route(
    draft_id: str,
    body: DraftReviewedDataUpdateRequest,
    _: dict = Depends(require_permission(Permission.DOCUMENTS_REVIEW)),
) -> ImportDraftResponse:
    try:
        draft = _import_draft_service.update_reviewed_data(
            draft_id, body.extracted_data
        )
    except ImportDraftServiceError as exc:
        raise _map_import_draft_error(exc)
    return ImportDraftResponse(**draft)


@document_router.post(
    "/drafts/{draft_id}/review",
    response_model=DocumentReviewResponse,
    summary="Approve or reject an import draft",
    description=(
        "Record a human review decision (approved/rejected) against a "
        "PENDING_REVIEW draft and synchronize the originating document's "
        "lifecycle status. Approval does NOT automatically import the "
        "draft — call POST /documents/drafts/{draft_id}/import afterward."
    ),
)
async def review_draft_route(
    draft_id: str,
    body: DocumentReviewRequest,
    current_user: dict = Depends(require_permission(Permission.DOCUMENTS_REVIEW)),
) -> DocumentReviewResponse:

    reviewer = _actor_identity(current_user)

    try:
        if body.decision == ReviewDecision.APPROVED:
            result = _import_draft_service.approve(
                draft_id, reviewer, body.reviewer_notes
            )
        else:
            result = _import_draft_service.reject(
                draft_id, reviewer, body.reviewer_notes
            )
    except DraftValidationError as exc:
        raise error_response(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "DRAFT_VALIDATION_ERROR",
            "Reviewed data is invalid.",
            details={"errors": exc.errors},
        )
    except ImportDraftServiceError as exc:
        raise _map_import_draft_error(exc)

    draft = result["draft"]
    return DocumentReviewResponse(
        draft_id=draft["draft_id"],
        document_id=draft["document_id"],
        decision=body.decision,
        status=DocumentStatus(result["status"]),
        reviewed_by=draft.get("reviewed_by") or reviewer,
        reviewed_at=draft.get("updated_at"),
        message=result.get("message", "Review recorded successfully."),
    )


@document_router.post(
    "/drafts/{draft_id}/import",
    response_model=DraftImportResponse,
    summary="Apply an approved draft into a business entity",
    description=(
        "Delegate exclusively to BusinessImportService to create/enrich "
        "the target business entity (or attach Goal evidence) from an "
        "APPROVED draft, then complete the draft/document lifecycle. "
        "Idempotent — reapplying an already-IMPORTED draft returns the "
        "existing entity rather than creating a duplicate."
    ),
)
async def import_draft_route(
    draft_id: str,
    _: dict = Depends(require_permission(Permission.DOCUMENTS_IMPORT)),
) -> DraftImportResponse:
    try:
        result = _business_import_service.import_draft(draft_id)
    except BusinessImportError as exc:
        raise _map_business_import_error(exc)
    return DraftImportResponse(**result)


# ===========================================================================
# 4. DOCUMENT READ APIs — LIST  (static path, before /{document_id})
# ===========================================================================

@document_router.get(
    "",
    response_model=DocumentListResponse,
    summary="List documents",
    description=(
        "Return documents matching the supplied filters (all optional, "
        "combined with AND), sorted most-recent-first. Never includes "
        "extracted text, file bytes, or the Mongo _id."
    ),
)
async def list_documents_route(
    status_filter: DocumentStatus | None = Query(default=None, alias="status"),
    document_type: str | None = Query(default=None),
    business_domain: BusinessDomain | None = Query(default=None),
    outcome: DocumentOutcome | None = Query(default=None),
    uploaded_by: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: dict = Depends(require_permission(Permission.DOCUMENTS_READ)),
) -> DocumentListResponse:
    try:
        raw_items = _document_repo.search_documents(
            document_type=document_type,
            processing_status=status_filter,
            uploaded_by=uploaded_by,
            outcome=outcome,
            business_domain=business_domain,
            limit=limit,
            skip=offset,
        )
        total = _document_repo.count_documents(
            document_type=document_type,
            processing_status=status_filter,
            uploaded_by=uploaded_by,
            outcome=outcome,
            business_domain=business_domain,
        )
    except RuntimeError as exc:
        logger.error("list_documents route error: %s", exc)
        raise error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "INTERNAL_SERVER_ERROR", str(exc)
        )

    return DocumentListResponse(
        total=total, items=[_to_list_item(d) for d in raw_items]
    )


# ===========================================================================
# 4. DOCUMENT READ APIs — DETAIL / STATUS  (dynamic /{document_id} paths)
# ===========================================================================

@document_router.get(
    "/{document_id}",
    response_model=DocumentDetailResponse,
    summary="Get one document's detail",
    description=(
        "Return persisted document detail: identity, filename, uploader, "
        "timestamps, lifecycle status, declared/verified classification, "
        "structured processing result, and error information where "
        "applicable. Never includes the original file bytes or full "
        "extracted text."
    ),
)
async def get_document_detail_route(
    document_id: str,
    _: dict = Depends(require_permission(Permission.DOCUMENTS_READ)),
) -> DocumentDetailResponse:
    try:
        document = _document_repo.get_document(document_id)
    except ValueError as exc:
        raise error_response(
            status.HTTP_404_NOT_FOUND, "DOCUMENT_NOT_FOUND", str(exc), "document_id"
        )
    except RuntimeError as exc:
        logger.error("get_document_detail('%s') route error: %s", document_id, exc)
        raise error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "INTERNAL_SERVER_ERROR", str(exc)
        )
    return _to_detail_response(document)


@document_router.get(
    "/{document_id}/status",
    response_model=DocumentStatusResponse,
    summary="Get one document's lifecycle status",
    description=(
        "Lightweight polling endpoint: current status, error information "
        "if applicable, and relevant lifecycle timestamps."
    ),
)
async def get_document_status_route(
    document_id: str,
    _: dict = Depends(require_permission(Permission.DOCUMENTS_READ)),
) -> DocumentStatusResponse:
    try:
        document = _document_repo.get_document(document_id)
    except ValueError as exc:
        raise error_response(
            status.HTTP_404_NOT_FOUND, "DOCUMENT_NOT_FOUND", str(exc), "document_id"
        )
    except RuntimeError as exc:
        logger.error("get_document_status('%s') route error: %s", document_id, exc)
        raise error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "INTERNAL_SERVER_ERROR", str(exc)
        )

    metadata = _metadata_of(document)
    return DocumentStatusResponse(
        document_id=document["document_id"],
        status=DocumentStatus(metadata["status"]),
        created_at=document.get("created_at"),
        updated_at=document.get("updated_at"),
        error_message=document.get("error_message"),
    )


# ===========================================================================
# 3. PROCESSING
# ===========================================================================

@document_router.post(
    "/{document_id}/process",
    response_model=DocumentProcessResponse,
    summary="Explicitly process a classified document",
    description=(
        "Advance a CLASSIFIED document through its domain processor to a "
        "persisted ProcessingResult, creating a PENDING_REVIEW ImportDraft "
        "for ENTITY_IMPORT/ENTITY_EVIDENCE outcomes. One-time and "
        "stage-aware: safe to call again on an already-processed or "
        "in-review document (returned as a no-op), but never reruns an "
        "uncertain, half-finished extraction. There is no generic "
        "force-reprocess — upload a new document instead."
    ),
)
async def process_document_route(
    document_id: str,
    _: dict = Depends(require_permission(Permission.DOCUMENTS_PROCESS)),
) -> DocumentProcessResponse:
    try:
        result = _processing_service.process_document(document_id)
    except DocumentProcessingError as exc:
        raise _map_processing_error(exc)
    return DocumentProcessResponse(**result)


# ===========================================================================
# 8. CONDITIONAL ADMIN DELETION
# ===========================================================================

@document_router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Conditionally delete a document",
    description=(
        "Delete a document only if no durable entity/import/evidence "
        "lineage would be destroyed (e.g. plain uploads, safe failed "
        "documents, or workflow-source documents with no active lifecycle "
        "dependency). Returns 409 DOCUMENT_NOT_DELETABLE for pending-review "
        "documents, approved/imported drafts, or any document that has "
        "already been imported into a business entity or evidence record. "
        "Never cascades into business collections."
    ),
)
async def delete_document_route(
    document_id: str,
    _: dict = Depends(require_permission(Permission.DOCUMENTS_DELETE)),
) -> Response:
    try:
        _lifecycle_service.delete_document(document_id)
    except DocumentLifecycleNotFoundError:
        raise error_response(
            status.HTTP_404_NOT_FOUND,
            "DOCUMENT_NOT_FOUND",
            f"Document '{document_id}' was not found.",
            "document_id",
        )
    except DocumentNotDeletableError as exc:
        raise error_response(
            status.HTTP_409_CONFLICT,
            "DOCUMENT_NOT_DELETABLE",
            exc.reason,
            "document_id",
        )
    except DocumentLifecycleError:
        logger.exception(
            "Failed to delete document '%s'.",
            document_id,
        )
        raise error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_SERVER_ERROR",
            "Document deletion failed due to an internal error.",
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)
