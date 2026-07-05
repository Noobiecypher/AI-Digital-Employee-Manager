"""
test_milestone7_document_api.py
===============================
Focused tests for Milestone 7 — Document API Integration.

Suggested location:
    tests/document_processing_tests/test_milestone7_document_api.py

Scope:
- document type discovery;
- multipart upload contract and validation;
- explicit processing delegation;
- document listing/detail/status;
- workflow-selector eligibility;
- draft list/detail/update/review/import delegation;
- conditional deletion HTTP mapping;
- DocumentLifecycleService deletion policy and cleanup ordering;
- RBAC permission behavior through the real FastAPI dependency chain.

No real MongoDB, filesystem storage, or LLM is required.
"""

from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, call

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import document_routes
from backend.auth import dependencies as auth_dependencies
from backend.document_processing.document_models import (
    BusinessDomain,
    DocumentOutcome,
    DocumentStatus,
    DraftOperation,
)
from backend.services.document_lifecycle_service import (
    DocumentLifecycleError,
    DocumentLifecycleNotFoundError,
    DocumentLifecycleService,
    DocumentNotDeletableError,
)
from backend.services.document_processing_service import DocumentProcessingError
from backend.services.document_service import DocumentServiceError
from backend.services.document_storage import DocumentStorageError
from backend.services.import_draft_service import ImportDraftServiceError
from backend.services.business_import_service import BusinessImportError


# ===========================================================================
# APP / AUTH FIXTURES
# ===========================================================================

@pytest.fixture
def active_user():
    return {
        "user_id": "user_1",
        "email": "manager@example.com",
        "full_name": "Manager User",
        "role": "manager",
        "is_active": True,
    }


@pytest.fixture
def app(active_user, monkeypatch):
    test_app = FastAPI()
    test_app.include_router(
        document_routes.document_router,
        prefix="/documents",
    )

    async def override_active_user():
        return deepcopy(active_user)

    test_app.dependency_overrides[
        auth_dependencies.get_current_active_user
    ] = override_active_user

    # Permission closures imported by document_routes call this module-level
    # function at request time, so patching it exercises the real dependency
    # chain without JWT or database access.
    monkeypatch.setattr(
        auth_dependencies,
        "has_permission",
        lambda role, permission: True,
    )

    return test_app


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client


def _error_code(response) -> str:
    return response.json()["detail"]["error"]["code"]


# ===========================================================================
# SHARED RESPONSE FIXTURES
# ===========================================================================

def classified_document(
    *,
    document_id: str = "doc_1",
    document_type: str = "resume",
    business_domain: str = BusinessDomain.RECRUITMENT.value,
    outcome: str = DocumentOutcome.ENTITY_IMPORT.value,
    status: str = DocumentStatus.CLASSIFIED.value,
    uploaded_by: str = "manager@example.com",
) -> dict:
    return {
        "document_id": document_id,
        "metadata": {
            "document_id": document_id,
            "original_filename": "resume.pdf",
            "content_type": "application/pdf",
            "size_bytes": 128,
            "uploaded_by": uploaded_by,
            "uploaded_at": "2026-07-04T00:00:00Z",
            "status": status,
            "expected_document_type": document_type,
            "document_type": document_type,
            "business_domain": business_domain,
            "outcome": outcome,
            "target_business_entity": (
                "candidate"
                if outcome == DocumentOutcome.ENTITY_IMPORT.value
                else None
            ),
            "target_context": {},
        },
        "classification": {
            "document_id": document_id,
            "document_type": document_type,
            "business_domain": business_domain,
            "outcome": outcome,
            "target_business_entity": (
                "candidate"
                if outcome == DocumentOutcome.ENTITY_IMPORT.value
                else None
            ),
            "review_required": outcome != DocumentOutcome.WORKFLOW_SOURCE.value,
            "confidence": 0.95,
            "classified_at": "2026-07-04T00:00:00Z",
        },
        "processing_result": None,
        "processing_history": [],
        "created_at": "2026-07-04T00:00:00Z",
        "updated_at": "2026-07-04T00:00:00Z",
        "error_message": None,
    }


def workflow_source_document(
    document_id: str,
    document_type: str,
    *,
    filename: str | None = None,
) -> dict:
    domain = (
        BusinessDomain.RESEARCH.value
        if document_type == "market_research_report"
        else BusinessDomain.PERFORMANCE.value
    )
    doc = classified_document(
        document_id=document_id,
        document_type=document_type,
        business_domain=domain,
        outcome=DocumentOutcome.WORKFLOW_SOURCE.value,
        status=DocumentStatus.PROCESSED.value,
    )
    doc["metadata"]["original_filename"] = filename or f"{document_id}.pdf"
    doc["processing_result"] = {
        "document_id": document_id,
        "document_type": document_type,
        "business_domain": domain,
        "processor_name": "FakeProcessor",
        "extracted_data": {"finding": "x"},
        "confidence": 0.9,
        "processed_at": "2026-07-04T01:00:00Z",
        "ai_summary": f"Summary for {document_id}",
    }
    return doc


def pending_draft() -> dict:
    return {
        "draft_id": "draft_1",
        "document_id": "doc_1",
        "source_document_ids": ["doc_1"],
        "business_domain": BusinessDomain.RECRUITMENT.value,
        "target_business_entity": "candidate",
        "operation": DraftOperation.CREATE_ENTITY.value,
        "target_entity_key": None,
        "target_context": {},
        "extracted_data": {
            "name": "Alice",
            "role_applied": "Software Engineer",
        },
        "confidence": 0.9,
        "ai_summary": "Candidate summary",
        "status": DocumentStatus.PENDING_REVIEW.value,
        "reviewed_by": None,
        "review_notes": None,
        "created_at": "2026-07-04T00:00:00Z",
        "updated_at": "2026-07-04T00:00:00Z",
    }


# ===========================================================================
# DOCUMENT TYPE DISCOVERY
# ===========================================================================

def test_types_endpoint_is_registry_backed(client):
    response = client.get("/documents/types")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == len(document_routes.DOCUMENT_TYPE_REGISTRY)

    returned = {item["document_type"]: item for item in body["items"]}
    assert set(returned) == set(document_routes.DOCUMENT_TYPE_REGISTRY)

    for key, config in document_routes.DOCUMENT_TYPE_REGISTRY.items():
        assert returned[key]["business_domain"] == config.business_domain.value
        assert returned[key]["outcome"] == config.outcome.value
        assert returned[key]["review_required"] == config.review_required
        assert returned[key]["supported_formats"] == [
            item.value for item in config.supported_formats
        ]


# ===========================================================================
# MULTIPART UPLOAD
# ===========================================================================

def test_upload_accepts_real_multipart_file_and_uses_authenticated_actor(
    client,
    monkeypatch,
):
    service = Mock()
    service.upload_document.return_value = classified_document()
    monkeypatch.setattr(document_routes, "_document_service", service)

    response = client.post(
        "/documents/upload",
        files={
            "file": (
                "resume.pdf",
                b"%PDF-1.4 fake test content",
                "application/pdf",
            )
        },
        data={
            "expected_document_type": "resume",
        },
    )

    assert response.status_code == 201
    assert response.json()["status"] == DocumentStatus.CLASSIFIED.value

    service.upload_document.assert_called_once_with(
        content=b"%PDF-1.4 fake test content",
        original_filename="resume.pdf",
        content_type="application/pdf",
        uploaded_by="user_1",
        expected_document_type="resume",
        target_context={},
    )


@pytest.mark.parametrize(
    "target_context",
    [
        "{not-json",
        '["not", "an", "object"]',
        '"string"',
    ],
)
def test_upload_rejects_invalid_target_context_before_service_call(
    client,
    monkeypatch,
    target_context,
):
    service = Mock()
    monkeypatch.setattr(document_routes, "_document_service", service)

    response = client.post(
        "/documents/upload",
        files={"file": ("resume.pdf", b"content", "application/pdf")},
        data={
            "expected_document_type": "resume",
            "target_context": target_context,
        },
    )

    assert response.status_code == 400
    assert _error_code(response) == "INVALID_TARGET_CONTEXT"
    service.upload_document.assert_not_called()


def test_upload_rejects_unknown_document_type(client, monkeypatch):
    service = Mock()
    monkeypatch.setattr(document_routes, "_document_service", service)

    response = client.post(
        "/documents/upload",
        files={"file": ("resume.pdf", b"content", "application/pdf")},
        data={"expected_document_type": "not_a_real_type"},
    )

    assert response.status_code == 400
    assert _error_code(response) == "INVALID_DOCUMENT_TYPE"
    service.upload_document.assert_not_called()


def test_upload_rejects_format_not_allowed_by_registry(client, monkeypatch):
    service = Mock()
    monkeypatch.setattr(document_routes, "_document_service", service)

    response = client.post(
        "/documents/upload",
        files={"file": ("resume.exe", b"content", "application/octet-stream")},
        data={"expected_document_type": "resume"},
    )

    assert response.status_code == 400
    assert _error_code(response) == "UNSUPPORTED_FILE_FORMAT"
    service.upload_document.assert_not_called()


def test_upload_rejects_empty_file(client, monkeypatch):
    service = Mock()
    monkeypatch.setattr(document_routes, "_document_service", service)

    response = client.post(
        "/documents/upload",
        files={"file": ("resume.pdf", b"", "application/pdf")},
        data={"expected_document_type": "resume"},
    )

    assert response.status_code == 400
    assert _error_code(response) == "EMPTY_FILE"
    service.upload_document.assert_not_called()


def test_upload_declared_type_mismatch_maps_to_conflict(client, monkeypatch):
    service = Mock()
    service.upload_document.side_effect = DocumentServiceError(
        "doc_1",
        "Declared document type mismatch: expected 'resume', actual "
        "'product_information'.",
    )
    monkeypatch.setattr(document_routes, "_document_service", service)

    response = client.post(
        "/documents/upload",
        files={"file": ("resume.pdf", b"content", "application/pdf")},
        data={"expected_document_type": "resume"},
    )

    assert response.status_code == 409


def test_upload_unknown_internal_failure_does_not_expose_raw_reason(
    client,
    monkeypatch,
):
    secret = "classifier provider key leaked in raw exception"
    service = Mock()
    service.upload_document.side_effect = DocumentServiceError("doc_1", secret)
    monkeypatch.setattr(document_routes, "_document_service", service)

    response = client.post(
        "/documents/upload",
        files={"file": ("resume.pdf", b"content", "application/pdf")},
        data={"expected_document_type": "resume"},
    )

    assert response.status_code == 500
    assert _error_code(response) == "INTERNAL_SERVER_ERROR"
    assert secret not in response.text


# ===========================================================================
# EXPLICIT PROCESSING
# ===========================================================================

def test_process_endpoint_delegates_once_and_returns_service_result(
    client,
    monkeypatch,
):
    service = Mock()
    service.process_document.return_value = {
        "document_id": "doc_1",
        "status": DocumentStatus.PROCESSED.value,
        "draft_id": None,
        "message": "Document processed successfully.",
    }
    monkeypatch.setattr(document_routes, "_processing_service", service)

    response = client.post("/documents/doc_1/process")

    assert response.status_code == 200
    assert response.json()["status"] == DocumentStatus.PROCESSED.value
    service.process_document.assert_called_once_with("doc_1")


def test_process_error_is_mapped_without_route_running_processor(
    client,
    monkeypatch,
):
    service = Mock()
    service.process_document.side_effect = DocumentProcessingError(
        "doc_1",
        "Manual intervention is required.",
    )
    monkeypatch.setattr(document_routes, "_processing_service", service)

    response = client.post("/documents/doc_1/process")

    assert response.status_code == 409
    assert _error_code(response) == "PROCESSING_CONFLICT"
    service.process_document.assert_called_once_with("doc_1")


# ===========================================================================
# LIST / DETAIL / STATUS
# ===========================================================================

def test_list_documents_forwards_all_filters_to_search_and_count(
    client,
    monkeypatch,
):
    repo = Mock()
    repo.search_documents.return_value = [classified_document()]
    repo.count_documents.return_value = 1
    monkeypatch.setattr(document_routes, "_document_repo", repo)

    response = client.get(
        "/documents",
        params={
            "status": "classified",
            "document_type": "resume",
            "business_domain": "recruitment",
            "outcome": "entity_import",
            "uploaded_by": "manager@example.com",
            "limit": 25,
            "offset": 5,
        },
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1

    repo.search_documents.assert_called_once_with(
        document_type="resume",
        processing_status=DocumentStatus.CLASSIFIED,
        uploaded_by="manager@example.com",
        outcome=DocumentOutcome.ENTITY_IMPORT,
        business_domain=BusinessDomain.RECRUITMENT,
        limit=25,
        skip=5,
    )
    repo.count_documents.assert_called_once_with(
        document_type="resume",
        processing_status=DocumentStatus.CLASSIFIED,
        uploaded_by="manager@example.com",
        outcome=DocumentOutcome.ENTITY_IMPORT,
        business_domain=BusinessDomain.RECRUITMENT,
    )


def test_list_response_never_exposes_extracted_text_or_mongo_id(
    client,
    monkeypatch,
):
    doc = classified_document()
    doc["_id"] = "mongo-secret"
    doc["extracted_text"] = "full confidential document text"

    repo = Mock()
    repo.search_documents.return_value = [doc]
    repo.count_documents.return_value = 1
    monkeypatch.setattr(document_routes, "_document_repo", repo)

    response = client.get("/documents")

    assert response.status_code == 200
    assert "mongo-secret" not in response.text
    assert "extracted_text" not in response.text
    assert "full confidential document text" not in response.text


def test_detail_excludes_raw_extracted_text_and_file_bytes(
    client,
    monkeypatch,
):
    doc = classified_document()
    doc["extracted_text"] = "raw full text"
    doc["file_bytes"] = b"secret bytes"

    repo = Mock()
    repo.get_document.return_value = doc
    monkeypatch.setattr(document_routes, "_document_repo", repo)

    response = client.get("/documents/doc_1")

    assert response.status_code == 200
    assert response.json()["document_id"] == "doc_1"
    assert "extracted_text" not in response.text
    assert "file_bytes" not in response.text


def test_detail_and_status_missing_document_return_404(client, monkeypatch):
    repo = Mock()
    repo.get_document.side_effect = ValueError("not found")
    monkeypatch.setattr(document_routes, "_document_repo", repo)

    detail = client.get("/documents/missing")
    status_response = client.get("/documents/missing/status")

    assert detail.status_code == 404
    assert status_response.status_code == 404
    assert _error_code(detail) == "DOCUMENT_NOT_FOUND"
    assert _error_code(status_response) == "DOCUMENT_NOT_FOUND"


# ===========================================================================
# WORKFLOW SELECTOR ELIGIBILITY
# ===========================================================================

@pytest.mark.parametrize(
    "slot,document_type",
    [
        ("market_research", "market_research_report"),
        ("performance_report.hr", "hr_metrics_report"),
        ("performance_report.sales", "sales_performance_report"),
    ],
)
def test_eligible_endpoint_uses_exact_m66_slot_type_and_processed_status(
    client,
    monkeypatch,
    slot,
    document_type,
):
    repo = Mock()
    repo.search_documents.return_value = [
        workflow_source_document("doc_1", document_type)
    ]
    monkeypatch.setattr(document_routes, "_document_repo", repo)

    response = client.get("/documents/eligible", params={"workflow_slot": slot})

    assert response.status_code == 200
    assert response.json()["workflow_slot"] == slot
    assert response.json()["items"][0]["document_type"] == document_type

    repo.search_documents.assert_called_once_with(
        document_type=document_type,
        processing_status=DocumentStatus.PROCESSED,
    )


def test_eligible_endpoint_rejects_unknown_slot_without_repository_call(
    client,
    monkeypatch,
):
    repo = Mock()
    monkeypatch.setattr(document_routes, "_document_repo", repo)

    response = client.get(
        "/documents/eligible",
        params={"workflow_slot": "hire_employee"},
    )

    assert response.status_code == 400
    repo.search_documents.assert_not_called()


def test_eligible_response_is_lightweight(client, monkeypatch):
    doc = workflow_source_document(
        "doc_1",
        "market_research_report",
    )
    doc["extracted_text"] = "must never leak"

    repo = Mock()
    repo.search_documents.return_value = [doc]
    monkeypatch.setattr(document_routes, "_document_repo", repo)

    response = client.get(
        "/documents/eligible",
        params={"workflow_slot": "market_research"},
    )

    assert response.status_code == 200
    assert response.json()["items"][0]["ai_summary"] == "Summary for doc_1"
    assert "extracted_text" not in response.text
    assert "must never leak" not in response.text


# ===========================================================================
# DRAFT LIST / DETAIL / UPDATE / REVIEW / IMPORT
# ===========================================================================

def test_draft_list_and_detail_delegate_to_repository(client, monkeypatch):
    repo = Mock()
    repo.list_drafts.return_value = [pending_draft()]
    repo.get_import_draft.return_value = pending_draft()
    monkeypatch.setattr(document_routes, "_import_draft_repo", repo)

    list_response = client.get(
        "/documents/drafts",
        params={
            "status": "pending_review",
            "document_id": "doc_1",
            "limit": 20,
            "offset": 2,
        },
    )
    detail_response = client.get("/documents/drafts/draft_1")

    assert list_response.status_code == 200
    assert detail_response.status_code == 200
    assert detail_response.json()["draft_id"] == "draft_1"


def test_patch_draft_delegates_reviewed_data_to_service(
    client,
    monkeypatch,
):
    service = Mock()
    updated = pending_draft()
    updated["extracted_data"] = {
        "name": "Alice Updated",
        "role_applied": "Software Engineer",
    }
    service.update_reviewed_data.return_value = updated
    monkeypatch.setattr(document_routes, "_import_draft_service", service)

    response = client.patch(
        "/documents/drafts/draft_1",
        json={
            "extracted_data": {
                "name": "Alice Updated",
                "role_applied": "Software Engineer",
            }
        },
    )

    assert response.status_code == 200
    service.update_reviewed_data.assert_called_once_with(
        "draft_1",
        {
            "name": "Alice Updated",
            "role_applied": "Software Engineer",
        },
    )


def test_review_approve_uses_authenticated_reviewer_and_does_not_import(
    client,
    monkeypatch,
):
    draft = pending_draft()
    draft.update(
        {
            "status": DocumentStatus.APPROVED.value,
            "reviewed_by": "user_1",
            "updated_at": "2026-07-04T02:00:00Z",
        }
    )

    review_service = Mock()
    review_service.approve.return_value = {
        "draft": draft,
        "status": DocumentStatus.APPROVED.value,
        "message": "Draft approved.",
    }
    import_service = Mock()

    monkeypatch.setattr(
        document_routes,
        "_import_draft_service",
        review_service,
    )
    monkeypatch.setattr(
        document_routes,
        "_business_import_service",
        import_service,
    )

    response = client.post(
        "/documents/drafts/draft_1/review",
        json={
            "decision": "approved",
            "reviewer_notes": "Looks correct.",
        },
    )

    assert response.status_code == 200
    review_service.approve.assert_called_once_with(
        "draft_1",
        "user_1",
        "Looks correct.",
    )
    import_service.import_draft.assert_not_called()


def test_review_request_rejects_removed_edited_data_field(client):
    response = client.post(
        "/documents/drafts/draft_1/review",
        json={
            "decision": "approved",
            "edited_data": {"name": "should use PATCH"},
        },
    )

    assert response.status_code == 422


def test_import_endpoint_delegates_exclusively_to_business_import_service(
    client,
    monkeypatch,
):
    service = Mock()
    service.import_draft.return_value = {
        "draft_id": "draft_1",
        "document_id": "doc_1",
        "status": DocumentStatus.IMPORTED.value,
        "target_business_entity": "candidate",
        "operation": DraftOperation.CREATE_ENTITY.value,
        "entity": {"candidate_id": "candidate_1"},
        "reused_existing_entity": False,
        "message": "Import completed successfully.",
    }
    monkeypatch.setattr(
        document_routes,
        "_business_import_service",
        service,
    )

    response = client.post("/documents/drafts/draft_1/import")

    assert response.status_code == 200
    service.import_draft.assert_called_once_with("draft_1")


# ===========================================================================
# RBAC THROUGH REAL DEPENDENCY CHAIN
# ===========================================================================

def test_permission_denial_returns_403(app, monkeypatch):
    monkeypatch.setattr(
        auth_dependencies,
        "has_permission",
        lambda role, permission: False,
    )

    with TestClient(app) as denied_client:
        response = denied_client.get("/documents/types")

    assert response.status_code == 403
    assert _error_code(response) == "FORBIDDEN"


# ===========================================================================
# DELETE ROUTE ERROR MAPPING
# ===========================================================================

def test_delete_success_returns_204(client, monkeypatch):
    service = Mock()
    service.delete_document.return_value = {
        "document_id": "doc_1",
        "message": "Document deleted successfully.",
    }
    monkeypatch.setattr(document_routes, "_lifecycle_service", service)

    response = client.delete("/documents/doc_1")

    assert response.status_code == 204
    service.delete_document.assert_called_once_with("doc_1")


def test_delete_missing_document_maps_to_404(client, monkeypatch):
    service = Mock()
    service.delete_document.side_effect = DocumentLifecycleNotFoundError(
        "missing",
        "Document not found.",
    )
    monkeypatch.setattr(document_routes, "_lifecycle_service", service)

    response = client.delete("/documents/missing")

    assert response.status_code == 404
    assert _error_code(response) == "DOCUMENT_NOT_FOUND"


def test_delete_policy_refusal_maps_to_stable_409(client, monkeypatch):
    service = Mock()
    service.delete_document.side_effect = DocumentNotDeletableError(
        "doc_1",
        "Document is imported.",
    )
    monkeypatch.setattr(document_routes, "_lifecycle_service", service)

    response = client.delete("/documents/doc_1")

    assert response.status_code == 409
    assert _error_code(response) == "DOCUMENT_NOT_DELETABLE"


def test_delete_infrastructure_failure_is_sanitized(client, monkeypatch):
    secret = "filesystem path /private/internal/path"
    service = Mock()
    service.delete_document.side_effect = DocumentLifecycleError(
        "doc_1",
        secret,
    )
    monkeypatch.setattr(document_routes, "_lifecycle_service", service)

    response = client.delete("/documents/doc_1")

    assert response.status_code == 500
    assert _error_code(response) == "INTERNAL_SERVER_ERROR"
    assert secret not in response.text


# ===========================================================================
# DOCUMENT LIFECYCLE SERVICE — FAKES
# ===========================================================================

class LifecycleDocumentRepo:
    def __init__(self, document):
        self.document = deepcopy(document)
        self.deleted = []
        self.events = []
        self.get_error = None
        self.delete_error = None

    def get_document(self, document_id):
        if self.get_error:
            raise self.get_error
        return deepcopy(self.document)

    def delete_document(self, document_id):
        self.events.append(("document", document_id))
        if self.delete_error:
            raise self.delete_error
        self.deleted.append(document_id)


class LifecycleDraftRepo:
    def __init__(self, drafts=None):
        self.drafts = deepcopy(drafts or [])
        self.deleted = []
        self.events = []
        self.delete_error = None

    def list_drafts(self, document_id=None):
        return deepcopy(
            [
                draft
                for draft in self.drafts
                if document_id is None
                or draft.get("document_id") == document_id
            ]
        )

    def delete_import_draft(self, draft_id):
        self.events.append(("draft", draft_id))
        if self.delete_error:
            raise self.delete_error
        self.deleted.append(draft_id)


class LifecycleStorage:
    def __init__(self, exists=True):
        self.exists = exists
        self.deleted = []
        self.events = []
        self.error = None

    def file_exists(self, document_id):
        return self.exists

    def delete_file(self, document_id):
        self.events.append(("file", document_id))
        if self.error:
            raise self.error
        self.deleted.append(document_id)


def lifecycle_document(
    status: DocumentStatus,
    *,
    workflow_id: str | None = None,
) -> dict:
    doc = classified_document(status=status.value)
    doc["workflow_id"] = workflow_id
    return doc


def lifecycle_service(document, drafts=None, storage=None):
    docs = LifecycleDocumentRepo(document)
    draft_repo = LifecycleDraftRepo(drafts)
    file_storage = storage or LifecycleStorage()
    service = DocumentLifecycleService(
        document_repository=docs,
        import_draft_repository=draft_repo,
        document_storage=file_storage,
    )
    return service, docs, draft_repo, file_storage


# ===========================================================================
# DOCUMENT LIFECYCLE SERVICE — POLICY
# ===========================================================================

@pytest.mark.parametrize(
    "status",
    [
        DocumentStatus.PROCESSING,
        DocumentStatus.PENDING_REVIEW,
        DocumentStatus.APPROVED,
        DocumentStatus.IMPORTED,
    ],
)
def test_lifecycle_blocks_protected_document_statuses(status):
    service, docs, drafts, storage = lifecycle_service(
        lifecycle_document(status)
    )

    with pytest.raises(DocumentNotDeletableError):
        service.delete_document("doc_1")

    assert docs.deleted == []
    assert drafts.deleted == []
    assert storage.deleted == []


@pytest.mark.parametrize(
    "draft_status",
    [
        DocumentStatus.PENDING_REVIEW,
        DocumentStatus.APPROVED,
        DocumentStatus.IMPORTED,
    ],
)
def test_lifecycle_blocks_durable_draft_even_if_document_status_drifted(
    draft_status,
):
    draft = pending_draft()
    draft["status"] = draft_status.value
    service, docs, _, storage = lifecycle_service(
        lifecycle_document(DocumentStatus.FAILED),
        drafts=[draft],
    )

    with pytest.raises(DocumentNotDeletableError):
        service.delete_document("doc_1")

    assert docs.deleted == []
    assert storage.deleted == []


def test_lifecycle_blocks_explicit_workflow_attachment():
    service, docs, _, storage = lifecycle_service(
        lifecycle_document(
            DocumentStatus.PROCESSED,
            workflow_id="wf_active",
        )
    )

    with pytest.raises(DocumentNotDeletableError):
        service.delete_document("doc_1")

    assert docs.deleted == []
    assert storage.deleted == []


@pytest.mark.parametrize(
    "status",
    [
        DocumentStatus.UPLOADED,
        DocumentStatus.CLASSIFIED,
        DocumentStatus.FAILED,
        DocumentStatus.PROCESSED,
    ],
)
def test_lifecycle_allows_safe_non_durable_documents(status):
    service, docs, _, storage = lifecycle_service(
        lifecycle_document(status)
    )

    result = service.delete_document("doc_1")

    assert result["document_id"] == "doc_1"
    assert docs.deleted == ["doc_1"]
    assert storage.deleted == ["doc_1"]


def test_lifecycle_rejected_draft_cleanup_order_is_draft_file_document():
    rejected = pending_draft()
    rejected["status"] = DocumentStatus.REJECTED.value

    service, docs, drafts, storage = lifecycle_service(
        lifecycle_document(DocumentStatus.REJECTED),
        drafts=[rejected],
    )

    shared_events = []
    docs.events = shared_events
    drafts.events = shared_events
    storage.events = shared_events

    service.delete_document("doc_1")

    assert shared_events == [
        ("draft", "draft_1"),
        ("file", "doc_1"),
        ("document", "doc_1"),
    ]


def test_lifecycle_draft_cleanup_failure_aborts_file_and_document_deletion():
    rejected = pending_draft()
    rejected["status"] = DocumentStatus.REJECTED.value

    service, docs, drafts, storage = lifecycle_service(
        lifecycle_document(DocumentStatus.REJECTED),
        drafts=[rejected],
    )
    drafts.delete_error = RuntimeError("draft DB failed")

    with pytest.raises(DocumentLifecycleError):
        service.delete_document("doc_1")

    assert storage.deleted == []
    assert docs.deleted == []


def test_lifecycle_file_cleanup_failure_aborts_document_record_deletion():
    storage = LifecycleStorage()
    storage.error = DocumentStorageError(
        "doc_1",
        "file delete failed",
    )

    service, docs, _, _ = lifecycle_service(
        lifecycle_document(DocumentStatus.CLASSIFIED),
        storage=storage,
    )

    with pytest.raises(DocumentLifecycleError):
        service.delete_document("doc_1")

    assert docs.deleted == []


def test_lifecycle_missing_document_has_dedicated_exception():
    service, docs, _, _ = lifecycle_service(
        lifecycle_document(DocumentStatus.CLASSIFIED)
    )
    docs.get_error = ValueError("not found")

    with pytest.raises(DocumentLifecycleNotFoundError):
        service.delete_document("missing")


def test_lifecycle_repository_failure_is_not_misclassified_as_not_found():
    service, docs, _, _ = lifecycle_service(
        lifecycle_document(DocumentStatus.CLASSIFIED)
    )
    docs.get_error = RuntimeError("database unavailable")

    with pytest.raises(DocumentLifecycleError) as exc_info:
        service.delete_document("doc_1")

    assert not isinstance(exc_info.value, DocumentLifecycleNotFoundError)


# ===========================================================================
# M7 HARDENING — DRAFT REVIEW REQUIREMENTS & APPROVAL VALIDATION
#
# These tests exercise the new GET .../requirements endpoint and the
# approval-time business-schema validation added to ImportDraftService,
# plus a defense-in-depth check that BusinessImportService still
# validates independently at import time. Requirements/derivation tests
# compare against the real CandidateCreateRequest / ProductCreateRequest
# schemas directly rather than hand-duplicating expected values.
# ===========================================================================

from backend.api.business_schemas import CandidateCreateRequest, ProductCreateRequest
from backend.services.import_draft_service import ImportDraftService
from backend.services.business_import_service import BusinessImportService


def _draft_with(**overrides) -> dict:
    """Local helper: pending_draft() with targeted overrides for M7 tests."""
    draft = pending_draft()
    draft.update(overrides)
    return draft


def _wire_import_draft_service(monkeypatch, draft: dict, document: dict | None = None):
    """
    Wire document_routes._import_draft_service to a REAL ImportDraftService
    backed by Mock repositories, so review-endpoint tests exercise the
    service's actual approval-validation logic (rather than a fully mocked
    service, which would bypass the behavior under test). Returns the
    underlying (draft_repo, document_repo) mocks for call assertions.
    """
    draft_repo = Mock()
    draft_repo.get_import_draft.return_value = draft

    approved = deepcopy(draft)
    approved.update({"status": DocumentStatus.APPROVED.value, "reviewed_by": "user_1"})
    draft_repo.approve_import_draft.return_value = approved

    rejected = deepcopy(draft)
    rejected.update({"status": DocumentStatus.REJECTED.value, "reviewed_by": "user_1"})
    draft_repo.reject_import_draft.return_value = rejected

    document_repo = Mock()
    document_repo.get_document.return_value = document or classified_document(
        status=DocumentStatus.PENDING_REVIEW.value,
    )
    document_repo.update_processing_status.return_value = classified_document(
        status=DocumentStatus.APPROVED.value,
    )

    service = ImportDraftService(
        import_draft_repository=draft_repo,
        document_repository=document_repo,
    )
    monkeypatch.setattr(document_routes, "_import_draft_service", service)
    return draft_repo, document_repo


# ---------------------------------------------------------------------
# 1. Requirements derived from the real Candidate schema
# ---------------------------------------------------------------------

def test_candidate_requirements_are_derived_from_real_business_schema(
    client, monkeypatch
):
    repo = Mock()
    repo.get_import_draft.return_value = pending_draft()
    monkeypatch.setattr(document_routes, "_import_draft_repo", repo)

    response = client.get("/documents/drafts/draft_1/requirements")

    assert response.status_code == 200
    body = response.json()

    schema = CandidateCreateRequest.model_json_schema()
    expected_fields = set(schema["properties"].keys())
    expected_required = set(schema.get("required", []))

    returned_fields = {item["field_name"] for item in body["fields"]}
    assert returned_fields == expected_fields

    for item in body["fields"]:
        assert item["required"] == (item["field_name"] in expected_required)


# ---------------------------------------------------------------------
# 2. Candidate requirements: types, constraints, UI metadata, order
# ---------------------------------------------------------------------

def test_candidate_requirements_expose_types_constraints_and_ui_metadata(
    client, monkeypatch
):
    repo = Mock()
    repo.get_import_draft.return_value = pending_draft()
    monkeypatch.setattr(document_routes, "_import_draft_repo", repo)

    response = client.get("/documents/drafts/draft_1/requirements")
    assert response.status_code == 200
    fields = response.json()["fields"]
    by_name = {item["field_name"]: item for item in fields}

    schema = CandidateCreateRequest.model_json_schema()
    props = schema["properties"]
    required = set(schema.get("required", []))

    # name / role_applied are required per the real schema
    assert "name" in required and "role_applied" in required
    assert by_name["name"]["required"] is True
    assert by_name["role_applied"]["required"] is True

    # derived types
    assert by_name["skills"]["field_type"] == "array"
    assert by_name["experience_years"]["field_type"] == "integer"

    # representative real constraints, read from the schema itself
    assert by_name["name"]["constraints"]["minLength"] == props["name"]["minLength"]
    assert by_name["name"]["constraints"]["maxLength"] == props["name"]["maxLength"]
    assert (
        by_name["experience_years"]["constraints"]["minimum"]
        == props["experience_years"]["minimum"]
    )
    assert (
        by_name["experience_years"]["constraints"]["maximum"]
        == props["experience_years"]["maximum"]
    )

    # UI-only input type
    assert by_name["email"]["input_type"] == "email"

    # configured field order (per review_contract_service's UI metadata)
    ordered_names = [item["field_name"] for item in fields]
    assert ordered_names == [
        "name",
        "role_applied",
        "skills",
        "experience_years",
        "email",
        "phone",
    ]


# ---------------------------------------------------------------------
# 3. Requirements derived from the real Product schema
# ---------------------------------------------------------------------

def test_product_requirements_are_derived_from_real_business_schema(
    client, monkeypatch
):
    repo = Mock()
    repo.get_import_draft.return_value = _draft_with(
        target_business_entity="product",
        extracted_data={"product_name": "HRTech Pro"},
    )
    monkeypatch.setattr(document_routes, "_import_draft_repo", repo)

    response = client.get("/documents/drafts/draft_1/requirements")

    assert response.status_code == 200
    body = response.json()

    schema = ProductCreateRequest.model_json_schema()
    expected_fields = set(schema["properties"].keys())
    expected_required = set(schema.get("required", []))

    returned_fields = {item["field_name"] for item in body["fields"]}
    assert returned_fields == expected_fields

    for item in body["fields"]:
        assert item["required"] == (item["field_name"] in expected_required)


# ---------------------------------------------------------------------
# 4. ATTACH_EVIDENCE is intentionally schema-less
# ---------------------------------------------------------------------

def test_requirements_endpoint_returns_empty_fields_for_attach_evidence(
    client, monkeypatch
):
    repo = Mock()
    repo.get_import_draft.return_value = _draft_with(
        target_business_entity="goal",
        operation=DraftOperation.ATTACH_EVIDENCE.value,
        target_context={"employee_name": "Alice Johnson", "review_period": "Q2 2026"},
        extracted_data={"notes": "freeform evidence"},
    )
    monkeypatch.setattr(document_routes, "_import_draft_repo", repo)

    response = client.get("/documents/drafts/draft_1/requirements")

    assert response.status_code == 200
    assert response.json()["fields"] == []


# ---------------------------------------------------------------------
# 5. Unsupported, non-evidence contract combinations fail closed
# ---------------------------------------------------------------------

def test_requirements_endpoint_rejects_unsupported_contract_combination(
    client, monkeypatch
):
    # candidate + enrich_entity is not registered anywhere (only
    # ("candidate", CREATE_ENTITY), ("product", CREATE_ENTITY), and
    # ("product", ENRICH_ENTITY) are supported), so it must NOT be
    # silently treated as schema-less like ATTACH_EVIDENCE is.
    repo = Mock()
    repo.get_import_draft.return_value = _draft_with(
        target_business_entity="candidate",
        operation=DraftOperation.ENRICH_ENTITY.value,
    )
    monkeypatch.setattr(document_routes, "_import_draft_repo", repo)

    # The route does not catch this ValueError and convert it into an
    # HTTPException (that would be a new error contract for this specific
    # case, which we were told not to add). TestClient's default
    # raise_server_exceptions=True behavior means the unhandled exception
    # propagates to the test, proving this is NOT a successful
    # fields=[] response.
    with pytest.raises(ValueError):
        client.get("/documents/drafts/draft_1/requirements")


# ---------------------------------------------------------------------
# 6. Approval rejects a missing required candidate field
# ---------------------------------------------------------------------

def test_approval_rejects_missing_required_candidate_field_with_field_error(
    client, monkeypatch
):
    invalid_draft = _draft_with(extracted_data={"name": "Alice"})  # missing role_applied
    _wire_import_draft_service(monkeypatch, invalid_draft)

    response = client.post(
        "/documents/drafts/draft_1/review",
        json={"decision": "approved"},
    )

    assert response.status_code == 422
    assert _error_code(response) == "DRAFT_VALIDATION_ERROR"

    errors = response.json()["detail"]["error"]["details"]["errors"]
    assert any(
        err["field"] == "role_applied" and err["type"] == "missing"
        for err in errors
    )


# ---------------------------------------------------------------------
# 7. Failed approval validation mutates nothing
# ---------------------------------------------------------------------

def test_failed_approval_does_not_mutate_draft_or_document(client, monkeypatch):
    invalid_draft = _draft_with(extracted_data={"name": "Alice"})  # missing role_applied
    draft_repo, document_repo = _wire_import_draft_service(monkeypatch, invalid_draft)

    response = client.post(
        "/documents/drafts/draft_1/review",
        json={"decision": "approved"},
    )

    assert response.status_code == 422
    draft_repo.approve_import_draft.assert_not_called()
    document_repo.update_processing_status.assert_not_called()


# ---------------------------------------------------------------------
# 8. Rejection does not run business-data validation
# ---------------------------------------------------------------------

def test_rejection_does_not_validate_incomplete_business_data(client, monkeypatch):
    invalid_draft = _draft_with(extracted_data={"name": "Alice"})  # missing role_applied
    draft_repo, _ = _wire_import_draft_service(monkeypatch, invalid_draft)

    response = client.post(
        "/documents/drafts/draft_1/review",
        json={"decision": "rejected"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == DocumentStatus.REJECTED.value
    draft_repo.reject_import_draft.assert_called_once()


# ---------------------------------------------------------------------
# 9. A genuinely valid candidate draft can be approved
# ---------------------------------------------------------------------

def test_valid_candidate_draft_can_be_approved(client, monkeypatch):
    valid_draft = _draft_with(
        extracted_data={
            "name": "Alice Johnson",
            "role_applied": "Software Engineer",
        }
    )
    draft_repo, document_repo = _wire_import_draft_service(monkeypatch, valid_draft)

    response = client.post(
        "/documents/drafts/draft_1/review",
        json={"decision": "approved", "reviewer_notes": "Looks correct."},
    )

    assert response.status_code == 200
    assert response.json()["status"] == DocumentStatus.APPROVED.value
    draft_repo.approve_import_draft.assert_called_once_with(
        "draft_1", "user_1", "Looks correct."
    )
    document_repo.update_processing_status.assert_called_once()


# ---------------------------------------------------------------------
# 10. ATTACH_EVIDENCE approval skips business schema validation
# ---------------------------------------------------------------------

def test_attach_evidence_approval_skips_business_schema_validation(
    client, monkeypatch
):
    evidence_draft = _draft_with(
        target_business_entity="goal",
        operation=DraftOperation.ATTACH_EVIDENCE.value,
        target_context={"employee_name": "Alice Johnson", "review_period": "Q2 2026"},
        extracted_data={"anything": "freeform evidence, no candidate/product shape"},
    )
    draft_repo, _ = _wire_import_draft_service(monkeypatch, evidence_draft)

    response = client.post(
        "/documents/drafts/draft_1/review",
        json={"decision": "approved"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == DocumentStatus.APPROVED.value
    draft_repo.approve_import_draft.assert_called_once()


# ---------------------------------------------------------------------
# 11. Approval validates the CURRENT persisted draft, not stale data
# ---------------------------------------------------------------------

def test_approval_validation_uses_current_persisted_reviewed_data(
    client, monkeypatch
):
    # The review request body can only ever carry decision/reviewer_notes
    # (DocumentReviewRequest forbids extra fields) -- there is no way for
    # the caller to smuggle extracted_data through this endpoint. The
    # corrected, valid data lives only in what the repository returns for
    # get_import_draft, proving validation reads persisted draft state.
    corrected_draft = _draft_with(
        extracted_data={
            "name": "Alice Johnson",
            "role_applied": "Corrected Role After Review",
        }
    )
    draft_repo, _ = _wire_import_draft_service(monkeypatch, corrected_draft)

    response = client.post(
        "/documents/drafts/draft_1/review",
        json={"decision": "approved"},
    )

    assert response.status_code == 200
    draft_repo.get_import_draft.assert_called_once_with("draft_1")
    draft_repo.approve_import_draft.assert_called_once()


# ---------------------------------------------------------------------
# 12. Final import validation remains active as defense in depth
# ---------------------------------------------------------------------

def test_import_still_validates_invalid_data_after_approval():
    # Simulates a draft that reached APPROVED status but still carries
    # invalid persisted extracted_data. BusinessImportService must
    # independently reject it at import time, without ever writing the
    # business entity.
    approved_invalid_draft = _draft_with(
        status=DocumentStatus.APPROVED.value,
        extracted_data={"name": "Alice"},  # missing role_applied
    )

    draft_repo = Mock()
    draft_repo.get_import_draft.return_value = approved_invalid_draft

    business_repo = Mock()
    business_repo.find_entity_by_source_import_draft_id.return_value = None

    service = BusinessImportService(
        import_draft_repository=draft_repo,
        business_data_repository=business_repo,
    )

    with pytest.raises(BusinessImportError):
        service.import_draft("draft_1")

    business_repo.create_candidate.assert_not_called()


# ===========================================================================
# M7 HARDENING BATCH 2 — UPLOAD target_context REGISTRY CONTRACT
#
# The registry (document_registry.py) is now the source of truth for which
# target_context fields a document type requires. The three performance
# evidence types (performance_review, self_assessment, manager_evaluation)
# target "goal" and require employee_name + review_period; every other
# document type currently has an empty required_target_context_fields,
# meaning NO target_context fields are allowed for it. POST /documents/upload
# validates target_context against this contract before reading the file or
# calling DocumentService.
# ===========================================================================

_PERFORMANCE_EVIDENCE_TYPES = (
    "performance_review",
    "self_assessment",
    "manager_evaluation",
)


# ---------------------------------------------------------------------
# 1. Registry: performance evidence types target "goal" and require
#    employee_name + review_period.
# ---------------------------------------------------------------------

@pytest.mark.parametrize("document_type", _PERFORMANCE_EVIDENCE_TYPES)
def test_performance_evidence_registry_targets_goal_and_requires_goal_identity(
    document_type,
):
    config = document_routes.DOCUMENT_TYPE_REGISTRY[document_type]

    assert config.target_business_entity == "goal"
    assert config.required_target_context_fields == [
        "employee_name",
        "review_period",
    ]


# ---------------------------------------------------------------------
# 2. GET /documents/types exposes required_target_context_fields
# ---------------------------------------------------------------------

def test_types_endpoint_exposes_required_target_context_fields(client):
    response = client.get("/documents/types")

    assert response.status_code == 200
    items = {item["document_type"]: item for item in response.json()["items"]}

    for document_type in _PERFORMANCE_EVIDENCE_TYPES:
        assert items[document_type]["required_target_context_fields"] == [
            "employee_name",
            "review_period",
        ]

    # Representative no-context type: the frontend can derive an empty
    # conditional form contract for it.
    assert items["resume"]["required_target_context_fields"] == []


# ---------------------------------------------------------------------
# 3. Missing target_context entirely is rejected before the service call
# ---------------------------------------------------------------------

def test_upload_performance_evidence_rejects_missing_target_context_before_service_call(
    client, monkeypatch
):
    service = Mock()
    monkeypatch.setattr(document_routes, "_document_service", service)

    response = client.post(
        "/documents/upload",
        files={"file": ("review.pdf", b"content", "application/pdf")},
        data={"expected_document_type": "performance_review"},
    )

    assert response.status_code == 400
    assert _error_code(response) == "INVALID_TARGET_CONTEXT"

    error = response.json()["detail"]["error"]
    assert error["field"] == "target_context"
    assert set(error["details"]["required_fields"]) == {
        "employee_name",
        "review_period",
    }
    service.upload_document.assert_not_called()


# ---------------------------------------------------------------------
# 4. A missing required context field (only employee_name given) is rejected
# ---------------------------------------------------------------------

def test_upload_performance_evidence_rejects_missing_required_context_field(
    client, monkeypatch
):
    service = Mock()
    monkeypatch.setattr(document_routes, "_document_service", service)

    response = client.post(
        "/documents/upload",
        files={"file": ("review.pdf", b"content", "application/pdf")},
        data={
            "expected_document_type": "performance_review",
            "target_context": '{"employee_name": "Alice"}',
        },
    )

    assert response.status_code == 400
    assert _error_code(response) == "INVALID_TARGET_CONTEXT"
    assert response.json()["detail"]["error"]["field"] == "target_context"
    service.upload_document.assert_not_called()


# ---------------------------------------------------------------------
# 5. A blank required context value is rejected
# ---------------------------------------------------------------------

def test_upload_performance_evidence_rejects_blank_required_context_value(
    client, monkeypatch
):
    service = Mock()
    monkeypatch.setattr(document_routes, "_document_service", service)

    response = client.post(
        "/documents/upload",
        files={"file": ("review.pdf", b"content", "application/pdf")},
        data={
            "expected_document_type": "performance_review",
            "target_context": (
                '{"employee_name": "Alice", "review_period": "   "}'
            ),
        },
    )

    assert response.status_code == 400
    assert _error_code(response) == "INVALID_TARGET_CONTEXT"
    service.upload_document.assert_not_called()


# ---------------------------------------------------------------------
# 6. A non-string required context value is rejected
# ---------------------------------------------------------------------

def test_upload_performance_evidence_rejects_non_string_required_context_value(
    client, monkeypatch
):
    service = Mock()
    monkeypatch.setattr(document_routes, "_document_service", service)

    response = client.post(
        "/documents/upload",
        files={"file": ("review.pdf", b"content", "application/pdf")},
        data={
            "expected_document_type": "performance_review",
            "target_context": (
                '{"employee_name": "Alice", "review_period": 2026}'
            ),
        },
    )

    assert response.status_code == 400
    assert _error_code(response) == "INVALID_TARGET_CONTEXT"
    service.upload_document.assert_not_called()


# ---------------------------------------------------------------------
# 7. An unexpected/extra context field is rejected
# ---------------------------------------------------------------------

def test_upload_performance_evidence_rejects_unexpected_context_field(
    client, monkeypatch
):
    service = Mock()
    monkeypatch.setattr(document_routes, "_document_service", service)

    response = client.post(
        "/documents/upload",
        files={"file": ("review.pdf", b"content", "application/pdf")},
        data={
            "expected_document_type": "performance_review",
            "target_context": (
                '{"employee_name": "Alice", "review_period": "Q2 2026", '
                '"extra": "not allowed"}'
            ),
        },
    )

    assert response.status_code == 400
    assert _error_code(response) == "INVALID_TARGET_CONTEXT"

    details = response.json()["detail"]["error"]["details"]
    assert set(details["allowed_fields"]) == {"employee_name", "review_period"}
    service.upload_document.assert_not_called()


# ---------------------------------------------------------------------
# 8. A valid, complete target_context is accepted and forwarded exactly
# ---------------------------------------------------------------------

def test_upload_performance_evidence_accepts_valid_target_context_and_forwards_it(
    client, monkeypatch
):
    service = Mock()
    service.upload_document.return_value = classified_document()
    monkeypatch.setattr(document_routes, "_document_service", service)

    response = client.post(
        "/documents/upload",
        files={"file": ("review.pdf", b"%PDF-1.4 content", "application/pdf")},
        data={
            "expected_document_type": "performance_review",
            "target_context": (
                '{"employee_name": "Alice", "review_period": "Q2 2026"}'
            ),
        },
    )

    assert response.status_code == 201
    service.upload_document.assert_called_once_with(
        content=b"%PDF-1.4 content",
        original_filename="review.pdf",
        content_type="application/pdf",
        uploaded_by="user_1",
        expected_document_type="performance_review",
        target_context={"employee_name": "Alice", "review_period": "Q2 2026"},
    )


# ---------------------------------------------------------------------
# 9. A no-context document type (resume) accepts an absent target_context
#    and forwards {} to DocumentService
# ---------------------------------------------------------------------

def test_upload_no_context_document_accepts_empty_context(client, monkeypatch):
    service = Mock()
    service.upload_document.return_value = classified_document()
    monkeypatch.setattr(document_routes, "_document_service", service)

    response = client.post(
        "/documents/upload",
        files={"file": ("resume.pdf", b"%PDF-1.4 content", "application/pdf")},
        data={"expected_document_type": "resume"},
    )

    assert response.status_code == 201
    service.upload_document.assert_called_once_with(
        content=b"%PDF-1.4 content",
        original_filename="resume.pdf",
        content_type="application/pdf",
        uploaded_by="user_1",
        expected_document_type="resume",
        target_context={},
    )


# ---------------------------------------------------------------------
# 10. A no-context document type (resume) rejects arbitrary nonempty
#     context before the service call
# ---------------------------------------------------------------------

def test_upload_no_context_document_rejects_arbitrary_nonempty_context_before_service_call(
    client, monkeypatch
):
    service = Mock()
    monkeypatch.setattr(document_routes, "_document_service", service)

    response = client.post(
        "/documents/upload",
        files={"file": ("resume.pdf", b"content", "application/pdf")},
        data={
            "expected_document_type": "resume",
            "target_context": '{"source": "swagger-or-react"}',
        },
    )

    assert response.status_code == 400
    assert _error_code(response) == "INVALID_TARGET_CONTEXT"
    assert response.json()["detail"]["error"]["details"]["allowed_fields"] == []
    service.upload_document.assert_not_called()
