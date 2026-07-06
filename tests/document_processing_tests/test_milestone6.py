from copy import deepcopy
from unittest.mock import Mock, patch

import pytest

from backend.database.business_data_repository import BusinessDataRepository
from backend.database.import_draft_repository import ImportDraftRepository

from backend.document_processing.document_models import (
    BusinessDomain,
    ClassificationResult,
    DocumentOutcome,
    DocumentStatus,
    DraftOperation,
    ProcessingResult,
)
from backend.services.business_import_service import (
    BusinessImportError,
    BusinessImportService,
)
from backend.services.document_processing_service import (
    DocumentProcessingError,
    DocumentProcessingService,
)
from backend.services.document_service import (
    DocumentService,
    DocumentServiceError,
)
from backend.services.import_draft_service import (
    ImportDraftService,
    ImportDraftServiceError,
)


# ==========================================================
# SHARED VALID BUSINESS FIXTURES
# ==========================================================

def valid_candidate_data() -> dict:
    """
    Valid against the actual CandidateCreateRequest contract.

    Required:
    - name
    - role_applied

    Remaining fields use valid explicit values consistent with the
    uploaded schema.
    """
    return {
        "name": "Alice Johnson",
        "role_applied": "Software Engineer",
        "skills": ["Python", "FastAPI"],
        "experience_years": 3,
        "email": "alice@example.com",
        "phone": "9876543210",
    }


def valid_product_data() -> dict:
    """
    Valid against the actual ProductCreateRequest contract.

    product_name is required. The remaining fields are supplied with
    values matching their real schema types.
    """
    return {
        "product_name": "Product A",
        "description": "A business software product.",
        "pain_points": ["Manual work"],
        "target_industries": ["Technology"],
        "category": "SaaS",
        "price_range": "₹1000-₹5000/month",
    }


# ==========================================================
# DOCUMENT PROCESSING SERVICE FIXTURES
# ==========================================================

def classification(outcome, target=None):
    return {
        "document_id": "doc_1",
        "document_type": "resume",
        "business_domain": BusinessDomain.RECRUITMENT.value,
        "outcome": outcome.value,
        "target_business_entity": target,
        "review_required": outcome == DocumentOutcome.ENTITY_IMPORT,
        "confidence": 0.95,
        "classified_at": "2026-07-03T00:00:00Z",
    }


def processing_result():
    return ProcessingResult(
        document_id="doc_1",
        document_type="resume",
        business_domain=BusinessDomain.RECRUITMENT,
        processor_name="FakeProcessor",
        extracted_data={"name": "Alice"},
        confidence=0.9,
        processed_at="2026-07-03T00:00:00Z",
        ai_summary="Candidate summary",
    ).model_dump(mode="json")


def document(
    status,
    outcome=DocumentOutcome.ENTITY_IMPORT,
    result=None,
):
    return {
        "document_id": "doc_1",
        "metadata": {
            "document_id": "doc_1",
            "original_filename": "resume.pdf",
            "content_type": "application/pdf",
            "size_bytes": 100,
            "uploaded_by": "user",
            "uploaded_at": "2026-07-03T00:00:00Z",
            "status": status.value,
            "document_type": "resume",
            "business_domain": BusinessDomain.RECRUITMENT.value,
            "outcome": outcome.value,
            "target_business_entity": (
                "candidate"
                if outcome == DocumentOutcome.ENTITY_IMPORT
                else None
            ),
        },
        "classification": classification(
            outcome,
            "candidate"
            if outcome == DocumentOutcome.ENTITY_IMPORT
            else None,
        ),
        "extracted_text": "resume text",
        "processing_result": result,
    }


class FakeDocumentRepo:
    def __init__(self, doc):
        self.doc = deepcopy(doc)
        self.result_updates = 0
        self.status_updates = []

    def get_document(self, document_id):
        return deepcopy(self.doc)

    def update_processing_status(
        self,
        document_id,
        status,
        error_message=None,
    ):
        self.status_updates.append(status)
        self.doc["metadata"]["status"] = status.value
        return deepcopy(self.doc)

    def update_processing_result(self, document_id, result):
        self.result_updates += 1
        self.doc["processing_result"] = result.model_dump(mode="json")
        self.doc["metadata"]["status"] = DocumentStatus.PROCESSED.value
        return deepcopy(self.doc)


class FakeDraftRepo:
    def __init__(self, drafts=None):
        self.drafts = deepcopy(drafts or [])
        self.create_calls = 0

    def list_drafts(self, document_id=None):
        return deepcopy(
            [
                draft
                for draft in self.drafts
                if draft["document_id"] == document_id
            ]
        )

    def create_import_draft(self, data):
        self.create_calls += 1
        draft = {
            **deepcopy(data),
            "status": DocumentStatus.PENDING_REVIEW.value,
        }
        self.drafts.append(draft)
        return deepcopy(draft)


class FakeProcessor:
    runs = 0

    def run(self, content, metadata):
        type(self).runs += 1
        return ProcessingResult(**processing_result())


def test_classified_runs_processor_persists_result_and_creates_one_draft():
    FakeProcessor.runs = 0
    docs = FakeDocumentRepo(document(DocumentStatus.CLASSIFIED))
    drafts = FakeDraftRepo()
    service = DocumentProcessingService(docs, drafts)

    with patch(
        "backend.services.document_processing_service.get_processor_class",
        return_value=FakeProcessor,
    ):
        result = service.process_document("doc_1")

    assert FakeProcessor.runs == 1
    assert docs.result_updates == 1
    assert drafts.create_calls == 1
    assert result["status"] == DocumentStatus.PENDING_REVIEW.value


@pytest.mark.parametrize(
    "outcome",
    [
        DocumentOutcome.WORKFLOW_SOURCE,
    ],
)
def test_non_import_outcomes_create_no_draft(outcome):
    FakeProcessor.runs = 0
    docs = FakeDocumentRepo(
        document(DocumentStatus.CLASSIFIED, outcome)
    )
    drafts = FakeDraftRepo()
    service = DocumentProcessingService(docs, drafts)

    with patch(
        "backend.services.document_processing_service.get_processor_class",
        return_value=FakeProcessor,
    ):
        result = service.process_document("doc_1")

    assert result["status"] == DocumentStatus.PROCESSED.value
    assert drafts.create_calls == 0


def test_processed_result_does_not_rerun_and_creates_missing_draft():
    FakeProcessor.runs = 0
    docs = FakeDocumentRepo(
        document(
            DocumentStatus.PROCESSED,
            result=processing_result(),
        )
    )
    drafts = FakeDraftRepo()

    result = DocumentProcessingService(
        docs,
        drafts,
    ).process_document("doc_1")

    assert FakeProcessor.runs == 0
    assert drafts.create_calls == 1
    assert result["status"] == DocumentStatus.PENDING_REVIEW.value


@pytest.mark.parametrize(
    "draft_status",
    [
        DocumentStatus.PENDING_REVIEW,
        DocumentStatus.APPROVED,
        DocumentStatus.REJECTED,
        DocumentStatus.IMPORTED,
    ],
)
def test_existing_draft_is_reused_without_downgrade(draft_status):
    docs = FakeDocumentRepo(
        document(
            DocumentStatus.PROCESSED,
            result=processing_result(),
        )
    )
    drafts = FakeDraftRepo(
        [
            {
                "draft_id": "draft_1",
                "document_id": "doc_1",
                "status": draft_status.value,
            }
        ]
    )

    result = DocumentProcessingService(
        docs,
        drafts,
    ).process_document("doc_1")

    assert drafts.create_calls == 0
    assert result["status"] == draft_status.value
    assert docs.doc["metadata"]["status"] == draft_status.value


def test_multiple_drafts_raise_integrity_error():
    docs = FakeDocumentRepo(
        document(
            DocumentStatus.PROCESSED,
            result=processing_result(),
        )
    )
    drafts = FakeDraftRepo(
        [
            {
                "draft_id": "d1",
                "document_id": "doc_1",
                "status": DocumentStatus.PENDING_REVIEW.value,
            },
            {
                "draft_id": "d2",
                "document_id": "doc_1",
                "status": DocumentStatus.PENDING_REVIEW.value,
            },
        ]
    )

    with pytest.raises(
        DocumentProcessingError,
        match="Integrity/idempotency",
    ):
        DocumentProcessingService(
            docs,
            drafts,
        ).process_document("doc_1")


@pytest.mark.parametrize(
    "status",
    [
        DocumentStatus.PROCESSING,
        DocumentStatus.FAILED,
    ],
)
def test_processing_or_failed_with_result_resumes_without_rerun(status):
    FakeProcessor.runs = 0
    docs = FakeDocumentRepo(
        document(
            status,
            result=processing_result(),
        )
    )
    drafts = FakeDraftRepo()

    DocumentProcessingService(
        docs,
        drafts,
    ).process_document("doc_1")

    assert FakeProcessor.runs == 0


@pytest.mark.parametrize(
    "status",
    [
        DocumentStatus.PROCESSING,
        DocumentStatus.FAILED,
    ],
)
def test_processing_or_failed_without_result_requires_manual_intervention(
    status,
):
    docs = FakeDocumentRepo(document(status))

    with pytest.raises(
        DocumentProcessingError,
        match="manual intervention",
    ):
        DocumentProcessingService(
            docs,
            FakeDraftRepo(),
        ).process_document("doc_1")


# ==========================================================
# IMPORT DRAFT SERVICE FIXTURES
# ==========================================================

class ReviewDraftRepo:
    def __init__(
        self,
        status=DocumentStatus.PENDING_REVIEW,
    ):
        self.draft = {
            "draft_id": "draft_1",
            "document_id": "doc_1",
            "status": status.value,
            "target_business_entity": "candidate",
            "operation": "create_entity",
            "extracted_data": {
                "name": "Alice",
                "role_applied": "Engineer",
            },
        }
    def get_import_draft(self, draft_id):
        return deepcopy(self.draft)

    def update_import_draft(self, draft_id, updates):
        self.draft.update(deepcopy(updates))
        return deepcopy(self.draft)

    def approve_import_draft(
        self,
        draft_id,
        reviewed_by,
        review_notes=None,
    ):
        if self.draft["status"] != DocumentStatus.PENDING_REVIEW.value:
            raise ValueError("not pending")

        self.draft["status"] = DocumentStatus.APPROVED.value
        return deepcopy(self.draft)

    def reject_import_draft(
        self,
        draft_id,
        reviewed_by,
        review_notes=None,
    ):
        if self.draft["status"] != DocumentStatus.PENDING_REVIEW.value:
            raise ValueError("not pending")

        self.draft["status"] = DocumentStatus.REJECTED.value
        return deepcopy(self.draft)


def review_document(
    status=DocumentStatus.PENDING_REVIEW,
):
    return {
        "document_id": "doc_1",
        "metadata": {
            "status": status.value,
        },
    }


def test_pending_draft_can_be_edited():
    drafts = ReviewDraftRepo()
    service = ImportDraftService(
        drafts,
        FakeDocumentRepo(review_document()),
    )

    result = service.update_reviewed_data(
        "draft_1",
        {"name": "Alice Updated"},
    )

    assert result["extracted_data"]["name"] == "Alice Updated"


@pytest.mark.parametrize(
    "status",
    [
        DocumentStatus.APPROVED,
        DocumentStatus.REJECTED,
        DocumentStatus.IMPORTED,
    ],
)
def test_non_pending_draft_cannot_be_edited(status):
    service = ImportDraftService(
        ReviewDraftRepo(status),
        FakeDocumentRepo(review_document(status)),
    )

    with pytest.raises(ImportDraftServiceError):
        service.update_reviewed_data(
            "draft_1",
            {"name": "Changed"},
        )


@pytest.mark.parametrize(
    "method,expected",
    [
        ("approve", DocumentStatus.APPROVED),
        ("reject", DocumentStatus.REJECTED),
    ],
)
def test_review_decision_synchronizes_draft_and_document(
    method,
    expected,
):
    drafts = ReviewDraftRepo()
    docs = FakeDocumentRepo(review_document())
    service = ImportDraftService(drafts, docs)

    getattr(service, method)(
        "draft_1",
        "reviewer",
    )

    assert drafts.draft["status"] == expected.value
    assert docs.doc["metadata"]["status"] == expected.value


@pytest.mark.parametrize(
    "method,status",
    [
        ("approve", DocumentStatus.APPROVED),
        ("reject", DocumentStatus.REJECTED),
    ],
)
def test_review_retry_repairs_document_sync(method, status):
    drafts = ReviewDraftRepo(status)
    docs = FakeDocumentRepo(
        review_document(DocumentStatus.PENDING_REVIEW)
    )

    result = getattr(
        ImportDraftService(drafts, docs),
        method,
    )(
        "draft_1",
        "reviewer",
    )

    assert result["status"] == status.value
    assert docs.doc["metadata"]["status"] == status.value


def test_conflicting_review_retry_fails():
    service = ImportDraftService(
        ReviewDraftRepo(DocumentStatus.REJECTED),
        FakeDocumentRepo(
            review_document(DocumentStatus.REJECTED)
        ),
    )

    with pytest.raises(ImportDraftServiceError):
        service.approve(
            "draft_1",
            "reviewer",
        )


# ==========================================================
# BUSINESS IMPORT SERVICE FIXTURES
# ==========================================================

class ImportDraftRepo:
    def __init__(self, draft):
        self.draft = deepcopy(draft)
        self.update_calls = 0

    def get_import_draft(self, draft_id):
        return deepcopy(self.draft)

    def update_import_draft(self, draft_id, updates):
        self.update_calls += 1
        self.draft.update(deepcopy(updates))
        return deepcopy(self.draft)


class BusinessRepo:
    def __init__(self):
        self.existing = None
        self.candidate_calls = 0
        self.product_calls = 0
        self.created_data = None
        self.creation_error = None
        self.lookup_error = None

    def find_entity_by_source_import_draft_id(self, draft_id):
        if self.lookup_error:
            raise self.lookup_error
        return deepcopy(self.existing)

    def create_candidate(self, data):
        self.candidate_calls += 1

        if self.creation_error:
            raise self.creation_error

        self.created_data = deepcopy(data)
        entity = {
            "candidate_id": "candidate_1",
            **deepcopy(data),
        }
        self.existing = {
            "target_business_entity": "candidate",
            "entity": entity,
        }
        return entity

    def create_product(self, data):
        self.product_calls += 1

        if self.creation_error:
            raise self.creation_error

        self.created_data = deepcopy(data)
        entity = deepcopy(data)
        self.existing = {
            "target_business_entity": "product",
            "entity": entity,
        }
        return entity


def approved_draft(target, data):
    return {
        "draft_id": "draft_1",
        "document_id": "doc_1",
        "source_document_ids": ["doc_1"],
        "target_business_entity": target,
        "extracted_data": deepcopy(data),
        "ai_summary": "AI summary",
        "status": DocumentStatus.APPROVED.value,
    }


def import_docs():
    return FakeDocumentRepo(
        review_document(DocumentStatus.APPROVED)
    )


def test_valid_candidate_import_and_provenance():
    drafts = ImportDraftRepo(
        approved_draft(
            "candidate",
            valid_candidate_data(),
        )
    )
    business = BusinessRepo()

    result = BusinessImportService(
        drafts,
        import_docs(),
        business,
    ).import_draft("draft_1")

    assert result["status"] == DocumentStatus.IMPORTED.value
    assert business.candidate_calls == 1
    assert business.created_data["name"] == "Alice Johnson"
    assert (
        business.created_data["role_applied"]
        == "Software Engineer"
    )
    assert (
        business.created_data["source_import_draft_id"]
        == "draft_1"
    )
    assert business.created_data["source_document_ids"] == ["doc_1"]
    assert business.created_data["ai_summary"] == "AI summary"


def test_valid_product_import():
    drafts = ImportDraftRepo(
        approved_draft(
            "product",
            valid_product_data(),
        )
    )
    business = BusinessRepo()

    result = BusinessImportService(
        drafts,
        import_docs(),
        business,
    ).import_draft("draft_1")

    assert result["status"] == DocumentStatus.IMPORTED.value
    assert business.product_calls == 1


def test_candidate_full_schema_validation_is_enforced():
    invalid_candidate = valid_candidate_data()
    invalid_candidate.pop("role_applied")

    drafts = ImportDraftRepo(
        approved_draft(
            "candidate",
            invalid_candidate,
        )
    )
    business = BusinessRepo()

    with pytest.raises(
        BusinessImportError,
        match="invalid",
    ):
        BusinessImportService(
            drafts,
            import_docs(),
            business,
        ).import_draft("draft_1")

    assert business.candidate_calls == 0
    assert drafts.draft["status"] == DocumentStatus.APPROVED.value


def test_product_full_schema_validation_is_enforced():
    invalid_product = {
        "product_name": "Product A",
        "unknown_field": "not allowed",
    }

    drafts = ImportDraftRepo(
        approved_draft(
            "product",
            invalid_product,
        )
    )
    business = BusinessRepo()

    with pytest.raises(
        BusinessImportError,
        match="invalid",
    ):
        BusinessImportService(
            drafts,
            import_docs(),
            business,
        ).import_draft("draft_1")

    assert business.product_calls == 0
    assert drafts.draft["status"] == DocumentStatus.APPROVED.value


def test_non_approved_new_import_is_rejected():
    draft = approved_draft(
        "candidate",
        valid_candidate_data(),
    )
    draft["status"] = DocumentStatus.PENDING_REVIEW.value

    business = BusinessRepo()

    with pytest.raises(BusinessImportError):
        BusinessImportService(
            ImportDraftRepo(draft),
            import_docs(),
            business,
        ).import_draft("draft_1")

    assert business.candidate_calls == 0


@pytest.mark.parametrize(
    "target,data_factory",
    [
        ("candidate", valid_candidate_data),
        ("product", valid_product_data),
    ],
)
def test_same_draft_never_creates_two_entities(
    target,
    data_factory,
):
    drafts = ImportDraftRepo(
        approved_draft(
            target,
            data_factory(),
        )
    )
    docs = import_docs()
    business = BusinessRepo()
    service = BusinessImportService(
        drafts,
        docs,
        business,
    )

    service.import_draft("draft_1")
    service.import_draft("draft_1")

    assert (
        business.candidate_calls + business.product_calls
        == 1
    )


def test_retry_after_entity_creation_and_failed_draft_update_reuses_entity():
    drafts = ImportDraftRepo(
        approved_draft(
            "candidate",
            valid_candidate_data(),
        )
    )
    docs = import_docs()
    business = BusinessRepo()

    original_update = drafts.update_import_draft
    drafts.update_import_draft = Mock(
        side_effect=RuntimeError("fail")
    )

    with pytest.raises(BusinessImportError):
        BusinessImportService(
            drafts,
            docs,
            business,
        ).import_draft("draft_1")

    assert business.candidate_calls == 1

    drafts.update_import_draft = original_update

    result = BusinessImportService(
        drafts,
        docs,
        business,
    ).import_draft("draft_1")

    assert business.candidate_calls == 1
    assert drafts.draft["status"] == DocumentStatus.IMPORTED.value
    assert result["reused_existing_entity"] is True


def test_retry_after_document_update_failure_reuses_entity():
    drafts = ImportDraftRepo(
        approved_draft(
            "candidate",
            valid_candidate_data(),
        )
    )
    docs = import_docs()
    business = BusinessRepo()

    original_update = docs.update_processing_status
    docs.update_processing_status = Mock(
        side_effect=RuntimeError("fail")
    )

    with pytest.raises(BusinessImportError):
        BusinessImportService(
            drafts,
            docs,
            business,
        ).import_draft("draft_1")

    assert business.candidate_calls == 1
    assert drafts.draft["status"] == DocumentStatus.IMPORTED.value

    docs.update_processing_status = original_update

    result = BusinessImportService(
        drafts,
        docs,
        business,
    ).import_draft("draft_1")

    assert business.candidate_calls == 1
    assert docs.doc["metadata"]["status"] == DocumentStatus.IMPORTED.value
    assert result["reused_existing_entity"] is True


def test_product_duplicate_failure_leaves_draft_approved():
    drafts = ImportDraftRepo(
        approved_draft(
            "product",
            valid_product_data(),
        )
    )
    business = BusinessRepo()
    business.creation_error = ValueError(
        "Product already exists"
    )

    with pytest.raises(BusinessImportError):
        BusinessImportService(
            drafts,
            import_docs(),
            business,
        ).import_draft("draft_1")

    assert drafts.draft["status"] == DocumentStatus.APPROVED.value


def test_validation_failure_leaves_draft_approved():
    invalid_candidate = valid_candidate_data()
    invalid_candidate.pop("role_applied")

    drafts = ImportDraftRepo(
        approved_draft(
            "candidate",
            invalid_candidate,
        )
    )
    business = BusinessRepo()

    with pytest.raises(BusinessImportError):
        BusinessImportService(
            drafts,
            import_docs(),
            business,
        ).import_draft("draft_1")

    assert business.candidate_calls == 0
    assert drafts.draft["status"] == DocumentStatus.APPROVED.value


def test_entity_creation_failure_leaves_draft_approved():
    drafts = ImportDraftRepo(
        approved_draft(
            "candidate",
            valid_candidate_data(),
        )
    )
    business = BusinessRepo()
    business.creation_error = RuntimeError(
        "database failure"
    )

    with pytest.raises(BusinessImportError):
        BusinessImportService(
            drafts,
            import_docs(),
            business,
        ).import_draft("draft_1")

    assert drafts.draft["status"] == DocumentStatus.APPROVED.value


def test_unsupported_target_fails_clearly():
    drafts = ImportDraftRepo(
        approved_draft(
            "employee",
            {"employee_name": "Alice"},
        )
    )

    with pytest.raises(
        BusinessImportError,
        match="Unsupported",
    ):
        BusinessImportService(
            drafts,
            import_docs(),
            BusinessRepo(),
        ).import_draft("draft_1")


def test_import_identity_integrity_violation_fails_clearly():
    drafts = ImportDraftRepo(
        approved_draft(
            "candidate",
            valid_candidate_data(),
        )
    )
    business = BusinessRepo()
    business.lookup_error = RuntimeError(
        "Integrity/idempotency violation: import draft "
        "'draft_1' has materialized both a Candidate and a Product."
    )

    with pytest.raises(
        BusinessImportError,
        match="Integrity/idempotency violation",
    ):
        BusinessImportService(
            drafts,
            import_docs(),
            business,
        ).import_draft("draft_1")

    assert business.candidate_calls == 0
    assert business.product_calls == 0

# ==========================================================
# MILESTONE 6.5 — DECLARED DOCUMENT-TYPE VERIFICATION
# ==========================================================

class UploadStorage:
    def __init__(self):
        self.deleted = []

    def save_file(self, content, original_filename):
        return type(
            "StorageMeta",
            (),
            {
                "document_id": "doc_declared",
                "storage_path": "/tmp/doc_declared",
                "original_filename": original_filename,
                "size_bytes": len(content),
            },
        )()

    def delete_file(self, document_id):
        self.deleted.append(document_id)


class UploadTextExtractor:
    def extract_text(self, path, content_type):
        return "independently classified document text"


class UploadClassifier:
    def __init__(self, actual_type):
        self.actual_type = actual_type
        self.seen_metadata = None

    def classify(self, text, metadata):
        self.seen_metadata = metadata
        if self.actual_type == "resume":
            domain = BusinessDomain.RECRUITMENT
            outcome = DocumentOutcome.ENTITY_IMPORT
            target = "candidate"
            review_required = True
        else:
            domain = BusinessDomain.SALES
            outcome = DocumentOutcome.ENTITY_IMPORT
            target = "product"
            review_required = True

        return ClassificationResult(
            document_id=metadata.document_id,
            document_type=self.actual_type,
            business_domain=domain,
            outcome=outcome,
            target_business_entity=target,
            review_required=review_required,
            confidence=0.95,
            classified_at="2026-07-04T00:00:00Z",
        )


class UploadDocumentRepo:
    def __init__(self):
        self.metadata = None
        self.classification_updates = 0
        self.persisted_classification = None
        self.status = DocumentStatus.UPLOADED
        self.error_message = None

    def create_document(self, metadata):
        self.metadata = metadata
        return {"document_id": metadata.document_id}

    def update_extracted_text(self, document_id, text):
        return {"document_id": document_id, "extracted_text": text}

    def update_classification(self, document_id, classification):
        self.classification_updates += 1
        self.persisted_classification = classification.model_dump(mode="json")
        return {
            "document_id": document_id,
            "classification": deepcopy(self.persisted_classification),
        }

    def update_processing_status(
        self,
        document_id,
        status,
        error_message=None,
    ):
        self.status = status
        self.error_message = error_message
        return {
            "document_id": document_id,
            "metadata": {
                "status": status.value,
                "expected_document_type": (
                    self.metadata.expected_document_type
                    if self.metadata is not None
                    else None
                ),
                "target_context": (
                    deepcopy(self.metadata.target_context)
                    if self.metadata is not None
                    else {}
                ),
            },
        }


def test_declared_document_type_match_succeeds_and_declaration_persists():
    repo = UploadDocumentRepo()
    classifier = UploadClassifier("resume")
    service = DocumentService(
        storage=UploadStorage(),
        repository=repo,
        classifier=classifier,
        text_extractor=UploadTextExtractor(),
    )

    result = service.upload_document(
        content=b"resume bytes",
        original_filename="resume.pdf",
        content_type="application/pdf",
        uploaded_by="user",
        expected_document_type="resume",
        target_context={
            "employee_name": "Alice",
            "review_period": "2026-H1",
        },
    )

    assert result["metadata"]["status"] == DocumentStatus.CLASSIFIED.value
    assert repo.metadata.expected_document_type == "resume"
    assert repo.metadata.target_context == {
        "employee_name": "Alice",
        "review_period": "2026-H1",
    }
    assert classifier.seen_metadata.expected_document_type == "resume"
    assert repo.classification_updates == 1


def test_declared_document_type_mismatch_fails_with_expected_and_actual():
    repo = UploadDocumentRepo()
    service = DocumentService(
        storage=UploadStorage(),
        repository=repo,
        classifier=UploadClassifier("product_information"),
        text_extractor=UploadTextExtractor(),
    )

    with pytest.raises(DocumentServiceError) as exc_info:
        service.upload_document(
            content=b"product bytes",
            original_filename="declared-resume.pdf",
            content_type="application/pdf",
            uploaded_by="user",
            expected_document_type="resume",
        )

    message = str(exc_info.value)
    assert "expected 'resume'" in message
    assert "actual 'product_information'" in message
    assert repo.metadata.expected_document_type == "resume"
    assert repo.status == DocumentStatus.FAILED
    assert repo.classification_updates == 1
    assert repo.persisted_classification["document_type"] == "product_information"

    failed_doc = {
        "document_id": "doc_declared",
        "metadata": {
            "status": DocumentStatus.FAILED.value,
            "expected_document_type": "resume",
        },
        "classification": deepcopy(repo.persisted_classification),
        "processing_result": None,
    }
    with pytest.raises(DocumentProcessingError, match="manual intervention"):
        DocumentProcessingService(
            FakeDocumentRepo(failed_doc), FakeDraftRepo()
        ).process_document("doc_declared")


# ==========================================================
# MILESTONE 6.5 — ENTITY_EVIDENCE REVIEW DRAFTS
# ==========================================================

def evidence_document(status, result=None):
    doc = document(
        status,
        outcome=DocumentOutcome.ENTITY_EVIDENCE,
        result=result,
    )
    doc["metadata"].update(
        {
            "document_type": "performance_review",
            "business_domain": BusinessDomain.PERFORMANCE.value,
            "target_business_entity": "goal",
            "target_context": {
                "employee_name": "Alice Johnson",
                "review_period": "2026-H1",
            },
        }
    )
    doc["classification"] = {
        "document_id": "doc_1",
        "document_type": "performance_review",
        "business_domain": BusinessDomain.PERFORMANCE.value,
        "outcome": DocumentOutcome.ENTITY_EVIDENCE.value,
        "target_business_entity": "goal",
        "review_required": True,
        "confidence": 0.95,
        "classified_at": "2026-07-04T00:00:00Z",
    }
    if result is not None:
        doc["processing_result"] = deepcopy(result)
    return doc


def evidence_processing_result():
    return ProcessingResult(
        document_id="doc_1",
        document_type="performance_review",
        business_domain=BusinessDomain.PERFORMANCE,
        processor_name="FakeProcessor",
        extracted_data={
            "overall_rating": 4.5,
            "strengths": ["Delivery"],
        },
        confidence=0.91,
        processed_at="2026-07-04T00:00:00Z",
        ai_summary="Strong performance evidence",
    ).model_dump(mode="json")


def test_entity_evidence_creates_one_attach_evidence_draft_and_pending_review():
    docs = FakeDocumentRepo(
        evidence_document(
            DocumentStatus.PROCESSED,
            evidence_processing_result(),
        )
    )
    drafts = FakeDraftRepo()

    result = DocumentProcessingService(docs, drafts).process_document("doc_1")

    assert drafts.create_calls == 1
    assert result["status"] == DocumentStatus.PENDING_REVIEW.value
    draft = drafts.drafts[0]
    assert draft["operation"] == DraftOperation.ATTACH_EVIDENCE
    assert draft["target_business_entity"] == "goal"
    assert draft["target_context"] == {
        "employee_name": "Alice Johnson",
        "review_period": "2026-H1",
    }


def test_evidence_recovery_creates_missing_draft_without_rerunning_processor():
    FakeProcessor.runs = 0
    docs = FakeDocumentRepo(
        evidence_document(
            DocumentStatus.PROCESSED,
            evidence_processing_result(),
        )
    )
    drafts = FakeDraftRepo()

    with patch(
        "backend.services.document_processing_service.get_processor_class",
        return_value=FakeProcessor,
    ):
        result = DocumentProcessingService(docs, drafts).process_document(
            "doc_1"
        )

    assert FakeProcessor.runs == 0
    assert drafts.create_calls == 1
    assert result["status"] == DocumentStatus.PENDING_REVIEW.value


def test_pending_evidence_data_and_target_context_can_be_edited():
    drafts = ReviewDraftRepo()
    drafts.draft.update(
        {
            "operation": DraftOperation.ATTACH_EVIDENCE.value,
            "target_business_entity": "goal",
            "target_context": {
                "employee_name": "Alice",
                "review_period": "2026-H1",
            },
        }
    )
    service = ImportDraftService(
        drafts,
        FakeDocumentRepo(review_document()),
    )

    updated_data = service.update_reviewed_data(
        "draft_1",
        {"strengths": ["Updated evidence"]},
    )
    updated_target = service.update_target_context(
        "draft_1",
        employee_name="Alice Johnson",
        review_period="2026-H2",
    )

    assert updated_data["extracted_data"] == {
        "strengths": ["Updated evidence"]
    }
    assert updated_target["target_context"] == {
        "employee_name": "Alice Johnson",
        "review_period": "2026-H2",
    }


@pytest.mark.parametrize(
    "status",
    [
        DocumentStatus.APPROVED,
        DocumentStatus.REJECTED,
        DocumentStatus.IMPORTED,
    ],
)
def test_post_review_evidence_target_context_editing_fails(status):
    drafts = ReviewDraftRepo(status)
    drafts.draft.update(
        {
            "operation": DraftOperation.ATTACH_EVIDENCE.value,
            "target_business_entity": "goal",
            "target_context": {
                "employee_name": "Alice",
                "review_period": "2026-H1",
            },
        }
    )
    service = ImportDraftService(
        drafts,
        FakeDocumentRepo(review_document(status)),
    )

    with pytest.raises(ImportDraftServiceError):
        service.update_target_context(
            "draft_1",
            employee_name="Changed",
            review_period="Changed",
        )


# ==========================================================
# MILESTONE 6.5 — PRODUCT OPERATION SELECTION
# ==========================================================

def test_candidate_cannot_select_enrich_entity():
    drafts = ReviewDraftRepo()
    drafts.draft["target_business_entity"] = "candidate"
    service = ImportDraftService(
        drafts,
        FakeDocumentRepo(review_document()),
    )

    with pytest.raises(ImportDraftServiceError):
        service.update_operation(
            "draft_1",
            DraftOperation.ENRICH_ENTITY.value,
            target_entity_key="Candidate A",
        )


def test_product_enrichment_requires_explicit_target():
    drafts = ReviewDraftRepo()
    drafts.draft["target_business_entity"] = "product"
    service = ImportDraftService(
        drafts,
        FakeDocumentRepo(review_document()),
    )

    with pytest.raises(ImportDraftServiceError):
        service.update_operation(
            "draft_1",
            DraftOperation.ENRICH_ENTITY.value,
        )


class ReviewBusinessRepo:
    def __init__(self, product):
        self.product = deepcopy(product)
        self.get_calls = []

    def get_product(self, product_name):
        self.get_calls.append(product_name)
        if product_name.lower() != self.product["product_name"].lower():
            raise ValueError("product not found")
        return deepcopy(self.product)


def test_selecting_product_enrichment_prepares_complete_reviewed_final_state():
    drafts = ReviewDraftRepo()
    drafts.draft.update({
        "target_business_entity": "product",
        "extracted_data": {
            "product_name": "AI suggested rename",
            "description": "New extracted description",
            "pain_points": ["New pain"],
        },
    })
    business = ReviewBusinessRepo({
        **valid_product_data(),
        "product_name": "Canonical Product",
        "description": "Existing description",
        "category": "Existing category",
        "price_range": "Existing price",
        "source_document_ids": ["doc_old"],
        "source_import_draft_id": "draft_create",
        "source_enrichment_draft_ids": ["draft_prior"],
        "ai_summary": "internal",
        "_id": "mongo-id",
    })
    service = ImportDraftService(
        drafts, FakeDocumentRepo(review_document()), business
    )

    result = service.update_operation(
        "draft_1",
        DraftOperation.ENRICH_ENTITY.value,
        target_entity_key="canonical product",
    )

    assert business.get_calls == ["canonical product"]
    assert result["operation"] == DraftOperation.ENRICH_ENTITY.value
    assert result["target_entity_key"] == "Canonical Product"
    assert result["extracted_data"]["product_name"] == "Canonical Product"
    assert result["extracted_data"]["description"] == "New extracted description"
    assert result["extracted_data"]["pain_points"] == ["New pain"]
    assert result["extracted_data"]["category"] == "Existing category"
    assert result["extracted_data"]["price_range"] == "Existing price"
    for field in (
        "_id",
        "source_document_ids",
        "source_import_draft_id",
        "source_enrichment_draft_ids",
        "ai_summary",
    ):
        assert field not in result["extracted_data"]

    edited = service.update_reviewed_data(
        "draft_1",
        {**result["extracted_data"], "description": "Reviewer final description"},
    )
    assert edited["extracted_data"]["description"] == "Reviewer final description"


@pytest.mark.parametrize(
    "edit_kind", ["operation", "data"]
)
def test_post_review_product_enrichment_edits_fail(edit_kind):
    drafts = ReviewDraftRepo(DocumentStatus.APPROVED)
    drafts.draft.update({
        "target_business_entity": "product",
        "operation": DraftOperation.ENRICH_ENTITY.value,
        "target_entity_key": "Product A",
        "extracted_data": valid_product_data(),
    })
    service = ImportDraftService(
        drafts,
        FakeDocumentRepo(review_document(DocumentStatus.APPROVED)),
        ReviewBusinessRepo(valid_product_data()),
    )

    with pytest.raises(ImportDraftServiceError):
        if edit_kind == "operation":
            service.update_operation(
                "draft_1", DraftOperation.CREATE_ENTITY.value
            )
        else:
            service.update_reviewed_data("draft_1", valid_product_data())


# ==========================================================
# MILESTONE 6.5 — APPROVED APPLICATION FIXTURES
# ==========================================================

class M65BusinessRepo(BusinessRepo):
    def __init__(self):
        super().__init__()
        self.products = {}
        self.enrichment_by_draft = {}
        self.enrich_calls = 0
        self.goals = {}
        self.evidence_calls = 0

    def get_product(self, product_name):
        if product_name not in self.products:
            raise ValueError("product not found")
        return deepcopy(self.products[product_name])

    def find_product_by_enrichment_draft_id(self, draft_id):
        product = self.enrichment_by_draft.get(draft_id)
        return deepcopy(product) if product is not None else None

    def enrich_product_from_draft(
        self,
        product_name,
        final_data,
        *,
        draft_id,
        document_id,
    ):
        if draft_id in self.enrichment_by_draft:
            return deepcopy(self.enrichment_by_draft[draft_id])

        self.enrich_calls += 1
        current = self.products[product_name]
        updated = {
            **deepcopy(current),
            **deepcopy(final_data),
            "product_name": current["product_name"],
            "source_document_ids": list(
                dict.fromkeys(
                    [
                        *(current.get("source_document_ids") or []),
                        document_id,
                    ]
                )
            ),
            "source_enrichment_draft_ids": list(
                dict.fromkeys(
                    [
                        *(
                            current.get("source_enrichment_draft_ids")
                            or []
                        ),
                        draft_id,
                    ]
                )
            ),
        }
        self.products[product_name] = deepcopy(updated)
        self.enrichment_by_draft[draft_id] = deepcopy(updated)
        return deepcopy(updated)

    def add_goal_document_evidence(
        self,
        employee_name,
        review_period,
        evidence,
    ):
        key = (employee_name, review_period)
        if key not in self.goals:
            raise ValueError("goal not found")

        goal = self.goals[key]
        existing_ids = {
            item["document_id"]
            for item in goal.get("document_evidence", [])
        }
        if evidence["document_id"] not in existing_ids:
            self.evidence_calls += 1
            goal.setdefault("document_evidence", []).append(
                deepcopy(evidence)
            )
        return deepcopy(goal)


def approved_enrichment_draft():
    return {
        "draft_id": "draft_enrich",
        "document_id": "doc_new",
        "source_document_ids": ["doc_new"],
        "target_business_entity": "product",
        "operation": DraftOperation.ENRICH_ENTITY.value,
        "target_entity_key": "Product A",
        "extracted_data": {
            **valid_product_data(),
            "product_name": "Product A",
            "description": "Reviewed final description",
            "pain_points": ["Manual work", "Slow reporting"],
            "category": "Reviewed category",
            "price_range": "Reviewed price",
        },
        "ai_summary": "New product evidence",
        "status": DocumentStatus.APPROVED.value,
    }


def approved_evidence_draft():
    return {
        "draft_id": "draft_evidence",
        "document_id": "doc_evidence",
        "source_document_ids": ["doc_evidence"],
        "target_business_entity": "goal",
        "operation": DraftOperation.ATTACH_EVIDENCE.value,
        "target_context": {
            "employee_name": "Alice Johnson",
            "review_period": "2026-H1",
        },
        "extracted_data": {
            "overall_rating": 4.5,
            "strengths": ["Delivery"],
        },
        "ai_summary": "Strong performance evidence",
        "reviewed_by": "manager@example.com",
        "status": DocumentStatus.APPROVED.value,
    }


def m65_import_docs(document_id, document_type):
    doc = FakeDocumentRepo(
        {
            "document_id": document_id,
            "metadata": {
                "status": DocumentStatus.APPROVED.value,
                "document_type": document_type,
            },
        }
    )
    return doc


def test_product_enrichment_preserves_existing_useful_fields_and_applies_reviewed_state():
    drafts = ImportDraftRepo(approved_enrichment_draft())
    business = M65BusinessRepo()
    business.products["Product A"] = {
        **valid_product_data(),
        "description": "Old description",
        "category": "SaaS",
        "price_range": "₹1000-₹5000/month",
        "source_document_ids": ["doc_old"],
        "source_import_draft_id": "draft_create",
    }

    result = BusinessImportService(
        drafts,
        m65_import_docs("doc_new", "product_information"),
        business,
    ).import_draft("draft_enrich")

    product = result["entity"]
    assert product["description"] == "Reviewed final description"
    assert product["pain_points"] == [
        "Manual work",
        "Slow reporting",
    ]
    assert product["category"] == "Reviewed category"
    assert product["price_range"] == "Reviewed price"
    assert product["source_import_draft_id"] == "draft_create"
    assert product["source_document_ids"] == ["doc_old", "doc_new"]
    assert product["source_enrichment_draft_ids"] == ["draft_enrich"]


def test_product_enrichment_retry_never_applies_twice_or_duplicates_source_ids():
    drafts = ImportDraftRepo(approved_enrichment_draft())
    business = M65BusinessRepo()
    business.products["Product A"] = {
        **valid_product_data(),
        "source_document_ids": ["doc_old"],
    }
    docs = m65_import_docs("doc_new", "product_information")
    service = BusinessImportService(drafts, docs, business)

    first = service.import_draft("draft_enrich")
    second = service.import_draft("draft_enrich")

    assert first["entity"]["source_document_ids"] == [
        "doc_old",
        "doc_new",
    ]
    assert second["entity"]["source_document_ids"] == [
        "doc_old",
        "doc_new",
    ]
    assert business.enrich_calls == 1


def test_product_enrichment_retry_after_write_before_lifecycle_completion_is_safe():
    drafts = ImportDraftRepo(approved_enrichment_draft())
    business = M65BusinessRepo()
    business.products["Product A"] = {
        **valid_product_data(),
        "source_document_ids": ["doc_old"],
    }
    docs = m65_import_docs("doc_new", "product_information")

    original_update = drafts.update_import_draft
    failed_once = {"value": False}

    def fail_first_lifecycle_update(draft_id, updates):
        if not failed_once["value"]:
            failed_once["value"] = True
            raise RuntimeError("simulated crash after Product write")
        return original_update(draft_id, updates)

    drafts.update_import_draft = fail_first_lifecycle_update
    service = BusinessImportService(drafts, docs, business)

    with pytest.raises(BusinessImportError):
        service.import_draft("draft_enrich")

    assert business.enrich_calls == 1
    assert business.products["Product A"]["source_document_ids"] == [
        "doc_old",
        "doc_new",
    ]

    result = service.import_draft("draft_enrich")

    assert result["status"] == DocumentStatus.IMPORTED.value
    assert business.enrich_calls == 1
    assert result["entity"]["source_document_ids"] == [
        "doc_old",
        "doc_new",
    ]


def test_normal_product_create_still_works_with_legacy_default_operation():
    drafts = ImportDraftRepo(
        approved_draft("product", valid_product_data())
    )
    business = BusinessRepo()

    result = BusinessImportService(
        drafts,
        import_docs(),
        business,
    ).import_draft("draft_1")

    assert result["status"] == DocumentStatus.IMPORTED.value
    assert business.product_calls == 1
    assert business.created_data["source_import_draft_id"] == "draft_1"


# ==========================================================
# MILESTONE 6.5 — GOAL EVIDENCE APPLICATION
# ==========================================================

def goal_fixture():
    return {
        "employee_name": "Alice Johnson",
        "review_period": "2026-H1",
        "goals_achieved": ["Existing achievement"],
        "pending_goal_update": {"goals_achieved": ["Pending"]},
        "status": "pending_approval",
        "goal_update_history": [{"decision": "submitted"}],
        "document_evidence": [],
    }


def test_approved_evidence_attaches_to_exact_goal_and_preserves_goal_approval_fields():
    drafts = ImportDraftRepo(approved_evidence_draft())
    business = M65BusinessRepo()
    business.goals[("Alice Johnson", "2026-H1")] = goal_fixture()
    before = deepcopy(business.goals[("Alice Johnson", "2026-H1")])

    result = BusinessImportService(
        drafts,
        m65_import_docs("doc_evidence", "performance_review"),
        business,
    ).import_draft("draft_evidence")

    goal = result["entity"]
    assert len(goal["document_evidence"]) == 1
    evidence = goal["document_evidence"][0]
    assert evidence["document_id"] == "doc_evidence"
    assert evidence["document_type"] == "performance_review"
    assert evidence["ai_summary"] == "Strong performance evidence"
    assert evidence["reviewed_evidence"] == {
        "overall_rating": 4.5,
        "strengths": ["Delivery"],
    }
    assert evidence["reviewed_by"] == "manager@example.com"

    for field in (
        "goals_achieved",
        "pending_goal_update",
        "status",
        "goal_update_history",
    ):
        assert goal[field] == before[field]


def test_missing_goal_fails_and_leaves_draft_approved():
    drafts = ImportDraftRepo(approved_evidence_draft())
    business = M65BusinessRepo()

    with pytest.raises(BusinessImportError):
        BusinessImportService(
            drafts,
            m65_import_docs("doc_evidence", "performance_review"),
            business,
        ).import_draft("draft_evidence")

    assert drafts.draft["status"] == DocumentStatus.APPROVED.value
    assert business.evidence_calls == 0


def test_evidence_retry_never_duplicates_document_id():
    drafts = ImportDraftRepo(approved_evidence_draft())
    business = M65BusinessRepo()
    business.goals[("Alice Johnson", "2026-H1")] = goal_fixture()
    service = BusinessImportService(
        drafts,
        m65_import_docs("doc_evidence", "performance_review"),
        business,
    )

    first = service.import_draft("draft_evidence")
    second = service.import_draft("draft_evidence")

    assert len(first["entity"]["document_evidence"]) == 1
    assert len(second["entity"]["document_evidence"]) == 1
    assert business.evidence_calls == 1


def test_evidence_retry_after_goal_write_before_lifecycle_completion_is_safe():
    drafts = ImportDraftRepo(approved_evidence_draft())
    business = M65BusinessRepo()
    business.goals[("Alice Johnson", "2026-H1")] = goal_fixture()
    docs = m65_import_docs("doc_evidence", "performance_review")

    original_update = drafts.update_import_draft
    failed_once = {"value": False}

    def fail_first_lifecycle_update(draft_id, updates):
        if not failed_once["value"]:
            failed_once["value"] = True
            raise RuntimeError("simulated crash after Goal write")
        return original_update(draft_id, updates)

    drafts.update_import_draft = fail_first_lifecycle_update
    service = BusinessImportService(drafts, docs, business)

    with pytest.raises(BusinessImportError):
        service.import_draft("draft_evidence")

    assert business.evidence_calls == 1
    assert len(
        business.goals[
            ("Alice Johnson", "2026-H1")
        ]["document_evidence"]
    ) == 1

    result = service.import_draft("draft_evidence")

    assert result["status"] == DocumentStatus.IMPORTED.value
    assert business.evidence_calls == 1
    assert len(result["entity"]["document_evidence"]) == 1

def enrichment_review_draft(
    status=DocumentStatus.PENDING_REVIEW,
):
    drafts = ReviewDraftRepo(status)
    drafts.draft.update(
        {
            "target_business_entity": "product",
            "operation": DraftOperation.ENRICH_ENTITY.value,
            "target_entity_key": "Product A",
            "extracted_data": {
                "product_name": "Product A",
                "description": "Existing description",
                "pain_points": ["Manual work"],
                "target_industries": ["Technology"],
                "category": "Software",
                "price_range": "₹100/month",
            },
        }
    )
    return drafts


def test_enrichment_partial_review_preserves_omitted_fields():
    drafts = enrichment_review_draft()
    service = ImportDraftService(
        drafts,
        FakeDocumentRepo(review_document()),
    )

    result = service.update_reviewed_data(
        "draft_1",
        {"price_range": "₹120/month"},
    )

    assert result["extracted_data"] == {
        "product_name": "Product A",
        "description": "Existing description",
        "pain_points": ["Manual work"],
        "target_industries": ["Technology"],
        "category": "Software",
        "price_range": "₹120/month",
    }
    assert drafts.draft["extracted_data"] == result["extracted_data"]


def test_enrichment_partial_review_overrides_submitted_fields():
    drafts = enrichment_review_draft()
    service = ImportDraftService(
        drafts,
        FakeDocumentRepo(review_document()),
    )

    result = service.update_reviewed_data(
        "draft_1",
        {
            "description": "Reviewed description",
            "category": "Enterprise Software",
        },
    )

    assert (
        result["extracted_data"]["description"]
        == "Reviewed description"
    )
    assert (
        result["extracted_data"]["category"]
        == "Enterprise Software"
    )
    assert result["extracted_data"]["pain_points"] == ["Manual work"]


def test_enrichment_partial_review_cannot_change_canonical_product_name():
    drafts = enrichment_review_draft()
    service = ImportDraftService(
        drafts,
        FakeDocumentRepo(review_document()),
    )

    result = service.update_reviewed_data(
        "draft_1",
        {
            "product_name": "Different Product",
            "description": "Reviewed description",
        },
    )

    assert result["extracted_data"]["product_name"] == "Product A"
    assert (
        result["extracted_data"]["description"]
        == "Reviewed description"
    )


def test_create_entity_review_update_still_replaces_extracted_data():
    drafts = ReviewDraftRepo()
    drafts.draft["operation"] = DraftOperation.CREATE_ENTITY.value
    service = ImportDraftService(
        drafts,
        FakeDocumentRepo(review_document()),
    )

    result = service.update_reviewed_data(
        "draft_1",
        {"name": "Replacement"},
    )

    assert result["extracted_data"] == {"name": "Replacement"}


def test_attach_evidence_review_update_still_replaces_extracted_data():
    drafts = ReviewDraftRepo()
    drafts.draft.update(
        {
            "operation": DraftOperation.ATTACH_EVIDENCE.value,
            "extracted_data": {
                "strengths": ["Old"],
                "overall_rating": 4,
            },
        }
    )
    service = ImportDraftService(
        drafts,
        FakeDocumentRepo(review_document()),
    )

    result = service.update_reviewed_data(
        "draft_1",
        {"strengths": ["Reviewed"]},
    )

    assert result["extracted_data"] == {
        "strengths": ["Reviewed"],
    }


@pytest.mark.parametrize(
    "status",
    [
        DocumentStatus.APPROVED,
        DocumentStatus.REJECTED,
        DocumentStatus.IMPORTED,
    ],
)
def test_non_pending_enrichment_draft_cannot_be_partially_edited(status):
    drafts = enrichment_review_draft(status)
    service = ImportDraftService(
        drafts,
        FakeDocumentRepo(review_document(status)),
    )

    before = deepcopy(drafts.draft["extracted_data"])

    with pytest.raises(ImportDraftServiceError):
        service.update_reviewed_data(
            "draft_1",
            {"price_range": "₹999/month"},
        )

    assert drafts.draft["extracted_data"] == before