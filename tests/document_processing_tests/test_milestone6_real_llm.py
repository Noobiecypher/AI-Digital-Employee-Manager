"""Real-LLM integration coverage for the Milestone 6.5 orchestration."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from backend.document_processing.document_models import (
    DocumentOutcome,
    DocumentStatus,
    DraftOperation,
)
from backend.services.business_import_service import BusinessImportService
from backend.services.document_processing_service import DocumentProcessingService
from backend.services.document_service import DocumentService
from backend.services.document_storage import StorageMetadata
from backend.services.import_draft_service import ImportDraftService
from datetime import datetime, timezone


PERFORMANCE_REVIEW_TEXT = """
PERFORMANCE REVIEW — Q2 2026
Employee: Alice Johnson
Review period: Q2 2026

Alice delivered the document-ingestion backend milestone on schedule and
increased automated test coverage from 68% to 86%. She closed 31 assigned
engineering tasks, with 29 completed on time, and reduced escaped defects by
35% compared with Q1.

Key achievements:
- Completed the document ingestion orchestration and review pipeline.
- Improved automated test coverage and release reliability.
- Resolved several cross-service integration issues before release.

Strengths:
- Strong backend architecture and debugging skills.
- Reliable delivery and ownership.
- Effective collaboration with product and frontend teammates.

Areas for improvement:
- Keep technical documentation updated more consistently.
- Improve estimation accuracy for large integration tasks.

Overall rating: 4.4 out of 5.
Goals referenced: complete document ingestion backend; improve automated test coverage.
""".strip()


class InMemoryStorage:
    def save_file(self, content: bytes, original_filename: str) -> StorageMetadata:
        return StorageMetadata(
            document_id="real-m65-performance",
            original_filename=original_filename,
            storage_path=str(Path("unused-performance-review.txt")),
            size_bytes=len(content),
            stored_at=datetime.now(timezone.utc),
        )

    def delete_file(self, document_id: str) -> None:
        return None


class FixedTextExtractor:
    def extract_text(self, path: Path, content_type: str) -> str:
        return PERFORMANCE_REVIEW_TEXT


class InMemoryDocumentRepository:
    def __init__(self) -> None:
        self.documents: dict[str, dict] = {}

    def create_document(self, metadata):
        doc = {
            "document_id": metadata.document_id,
            "metadata": metadata.model_dump(mode="json"),
            "extracted_text": None,
            "classification": None,
            "processing_result": None,
        }
        self.documents[metadata.document_id] = doc
        return deepcopy(doc)

    def get_document(self, document_id: str):
        if document_id not in self.documents:
            raise ValueError(f"Document '{document_id}' not found")
        return deepcopy(self.documents[document_id])

    def update_extracted_text(self, document_id: str, text: str):
        self.documents[document_id]["extracted_text"] = text
        return self.get_document(document_id)

    def update_classification(self, document_id: str, classification):
        doc = self.documents[document_id]
        doc["classification"] = classification.model_dump(mode="json")
        doc["metadata"].update({
            "document_type": classification.document_type,
            "business_domain": classification.business_domain.value,
            "outcome": classification.outcome.value,
            "target_business_entity": classification.target_business_entity,
        })
        return self.get_document(document_id)

    def update_processing_result(self, document_id: str, result):
        self.documents[document_id]["processing_result"] = result.model_dump(mode="json")
        return self.get_document(document_id)

    def update_processing_status(self, document_id: str, status, error_message=None):
        doc = self.documents[document_id]
        doc["metadata"]["status"] = status.value
        doc["metadata"]["error_message"] = error_message
        return self.get_document(document_id)


class InMemoryDraftRepository:
    def __init__(self) -> None:
        self.drafts: dict[str, dict] = {}

    def create_import_draft(self, data: dict):
        draft = deepcopy(data)
        draft.setdefault("status", DocumentStatus.PENDING_REVIEW.value)
        self.drafts[draft["draft_id"]] = draft
        return deepcopy(draft)

    def get_import_draft(self, draft_id: str):
        if draft_id not in self.drafts:
            raise ValueError(f"Draft '{draft_id}' not found")
        return deepcopy(self.drafts[draft_id])

    def list_drafts(self, document_id=None, **kwargs):
        values = list(self.drafts.values())
        if document_id is not None:
            values = [d for d in values if d["document_id"] == document_id]
        return deepcopy(values)

    def update_import_draft(self, draft_id: str, updates: dict):
        self.drafts[draft_id].update(deepcopy(updates))
        return self.get_import_draft(draft_id)

    def approve_import_draft(self, draft_id: str, reviewed_by: str, review_notes=None):
        return self.update_import_draft(draft_id, {
            "status": DocumentStatus.APPROVED.value,
            "reviewed_by": reviewed_by,
            "review_notes": review_notes,
        })

    def reject_import_draft(self, draft_id: str, reviewed_by: str, review_notes=None):
        return self.update_import_draft(draft_id, {
            "status": DocumentStatus.REJECTED.value,
            "reviewed_by": reviewed_by,
            "review_notes": review_notes,
        })


class InMemoryBusinessRepository:
    def __init__(self) -> None:
        self.goals = {
            ("Alice Johnson", "Q2 2026"): {
                "employee_name": "Alice Johnson",
                "review_period": "Q2 2026",
                "goals_set": [
                    "Complete document ingestion backend",
                    "Improve automated test coverage",
                ],
                "goals_achieved": [],
                "document_evidence": [],
            }
        }

    def find_entity_by_source_import_draft_id(self, draft_id: str):
        return None

    def add_goal_document_evidence(self, employee_name: str, review_period: str, evidence: dict):
        key = (employee_name, review_period)
        if key not in self.goals:
            raise ValueError("Goal not found")
        goal = self.goals[key]
        if not any(item["document_id"] == evidence["document_id"] for item in goal["document_evidence"]):
            goal["document_evidence"].append(deepcopy(evidence))
        return deepcopy(goal)


@pytest.mark.integration
def test_real_llm_performance_evidence_flows_through_m65_orchestration():
    documents = InMemoryDocumentRepository()
    drafts = InMemoryDraftRepository()
    business = InMemoryBusinessRepository()

    uploaded = DocumentService(
        storage=InMemoryStorage(),
        repository=documents,
        text_extractor=FixedTextExtractor(),
    ).upload_document(
        content=PERFORMANCE_REVIEW_TEXT.encode("utf-8"),
        original_filename="alice_q2_2026_performance_review.txt",
        content_type="text/plain",
        uploaded_by="integration-test",
        expected_document_type="performance_review",
        target_context={
            "employee_name": "Alice Johnson",
            "review_period": "Q2 2026",
        },
    )

    document_id = uploaded["document_id"]
    classified = documents.get_document(document_id)
    assert classified["classification"]["document_type"] == "performance_review"
    assert classified["metadata"]["expected_document_type"] == "performance_review"
    assert classified["classification"]["document_type"] == classified["metadata"]["expected_document_type"]
    assert classified["metadata"]["status"] == DocumentStatus.CLASSIFIED.value

    processed = DocumentProcessingService(documents, drafts).process_document(document_id)
    assert processed["status"] == DocumentStatus.PENDING_REVIEW.value

    persisted = documents.get_document(document_id)
    result = persisted["processing_result"]
    assert result is not None
    assert result["processor_name"] == "PerformanceProcessor"
    assert persisted["classification"]["outcome"] == DocumentOutcome.ENTITY_EVIDENCE.value
    assert result["extracted_data"]
    assert any(result["extracted_data"].get(name) for name in ("strengths", "weaknesses", "goals_referenced", "summary"))

    matching_drafts = drafts.list_drafts(document_id=document_id)
    assert len(matching_drafts) == 1
    draft = matching_drafts[0]
    assert draft["operation"] == DraftOperation.ATTACH_EVIDENCE.value
    assert draft["status"] == DocumentStatus.PENDING_REVIEW.value
    assert draft["target_context"] == {
        "employee_name": "Alice Johnson",
        "review_period": "Q2 2026",
    }
    assert draft["extracted_data"]

    approved = ImportDraftService(drafts, documents).approve(
        draft["draft_id"], reviewed_by="manager@example.com"
    )
    assert approved["status"] == DocumentStatus.APPROVED.value
    assert documents.get_document(document_id)["metadata"]["status"] == DocumentStatus.APPROVED.value

    importer = BusinessImportService(drafts, documents, business)
    first = importer.import_draft(draft["draft_id"])
    goal = first["entity"]
    assert goal["employee_name"] == "Alice Johnson"
    assert goal["review_period"] == "Q2 2026"
    assert len(goal["document_evidence"]) == 1

    snapshot = goal["document_evidence"][0]
    assert snapshot["document_id"] == document_id
    assert snapshot["reviewed_evidence"]
    assert "extracted_text" not in snapshot
    assert "file_bytes" not in snapshot
    assert PERFORMANCE_REVIEW_TEXT not in repr(snapshot)

    second = importer.import_draft(draft["draft_id"])
    assert len(second["entity"]["document_evidence"]) == 1
    assert documents.get_document(document_id)["metadata"]["status"] == DocumentStatus.IMPORTED.value
