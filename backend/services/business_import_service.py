"""
business_import_service.py
==========================
Approved ImportDraft -> business entity orchestration.

BusinessImportService is the only document-derived path into Candidate
and Product business entities.

It:
- loads an ImportDraft;
- detects an already-materialized entity by source_import_draft_id;
- validates final reviewed data with the existing strict API contracts;
- adds trusted internal provenance;
- explicitly dispatches Candidate/Product creation;
- completes Draft and Document lifecycle state;
- safely resumes partial failures without creating duplicate entities.

It never accesses MongoDB directly.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import ValidationError

from backend.api.business_schemas import CandidateCreateRequest, ProductCreateRequest
from backend.database.business_data_repository import BusinessDataRepository
from backend.database.document_repository import DocumentRepository
from backend.database.import_draft_repository import ImportDraftRepository
from backend.document_processing.document_models import DraftOperation, DocumentStatus


class BusinessImportError(Exception):
    def __init__(self, draft_id: str, reason: str) -> None:
        self.draft_id = draft_id
        self.reason = reason
        super().__init__(f"Business import failed for draft '{draft_id}': {reason}")


class BusinessImportService:
    def __init__(self, import_draft_repository: Optional[ImportDraftRepository] = None,
                 document_repository: Optional[DocumentRepository] = None,
                 business_data_repository: Optional[BusinessDataRepository] = None) -> None:
        self._import_draft_repo = import_draft_repository or ImportDraftRepository()
        self._document_repo = document_repository or DocumentRepository()
        self._business_repo = business_data_repository or BusinessDataRepository()

    def import_draft(self, draft_id: str) -> dict:
        draft = self._get_draft_or_raise(draft_id)
        operation = self._operation(draft)
        if operation == DraftOperation.CREATE_ENTITY:
            return self._create_entity(draft)
        if operation == DraftOperation.ENRICH_ENTITY:
            return self._enrich_product(draft)
        if operation == DraftOperation.ATTACH_EVIDENCE:
            return self._attach_evidence(draft)
        raise BusinessImportError(draft_id, f"Unsupported draft operation '{operation.value}'.")

    @staticmethod
    def _operation(draft: dict) -> DraftOperation:
        raw = draft.get("operation", DraftOperation.CREATE_ENTITY.value)
        if raw == DraftOperation.ENTITY_IMPORT.value:
            return DraftOperation.CREATE_ENTITY
        return DraftOperation(raw)

    def _require_approved(self, draft: dict) -> None:
        status = DocumentStatus(draft["status"])
        if status not in (DocumentStatus.APPROVED, DocumentStatus.IMPORTED):
            raise BusinessImportError(draft["draft_id"],
                f"Business application requires an approved draft; current status is '{status.value}'.")

    def _create_entity(self, draft: dict) -> dict:
        draft_id = draft["draft_id"]
        target = draft["target_business_entity"]
        if target not in ("candidate", "product"):
            raise BusinessImportError(draft_id, f"Unsupported target business entity '{target}'.")
        existing = self._find_materialized_entity(draft_id)
        if existing is not None:
            if existing["target_business_entity"] != target:
                raise BusinessImportError(draft_id, "Import identity conflict.")
            return self._complete_lifecycle(draft, existing["entity"], True)
        self._require_approved(draft)
        data = self._validate_create(draft)
        persistence = {**data,
            "source_document_ids": list(draft.get("source_document_ids") or [draft["document_id"]]),
            "ai_summary": draft.get("ai_summary"),
            "source_import_draft_id": draft_id}
        try:
            entity = (self._business_repo.create_candidate(persistence)
                      if target == "candidate" else self._business_repo.create_product(persistence))
        except (ValueError, RuntimeError) as exc:
            raise BusinessImportError(draft_id, f"Failed to create {target}: {exc}") from exc
        return self._complete_lifecycle(draft, entity, False)

    def _enrich_product(self, draft: dict) -> dict:
        draft_id = draft["draft_id"]
        if draft.get("target_business_entity") != "product":
            raise BusinessImportError(draft_id, "ENRICH_ENTITY is supported only for Product drafts.")
        target = draft.get("target_entity_key")
        if not target:
            raise BusinessImportError(draft_id, "Product enrichment requires an explicit target Product.")
        try:
            existing = self._business_repo.find_product_by_enrichment_draft_id(draft_id)
        except RuntimeError as exc:
            raise BusinessImportError(draft_id, f"Failed to check enrichment idempotency: {exc}") from exc
        if existing is not None:
            return self._complete_lifecycle(draft, existing, True)
        self._require_approved(draft)
        try:
            current = self._business_repo.get_product(target)
        except (ValueError, RuntimeError) as exc:
            raise BusinessImportError(draft_id, f"Target Product '{target}' not found: {exc}") from exc
        try:
            final = ProductCreateRequest.model_validate(
                draft["extracted_data"]
            ).model_dump()
            final["product_name"] = current["product_name"]
            entity = self._business_repo.enrich_product_from_draft(
                current["product_name"], final, draft_id=draft_id, document_id=draft["document_id"])
        except ValidationError as exc:
            raise BusinessImportError(draft_id, f"Final reviewed Product data is invalid: {exc}") from exc
        except (ValueError, RuntimeError) as exc:
            raise BusinessImportError(draft_id, f"Failed to enrich Product: {exc}") from exc
        return self._complete_lifecycle(draft, entity, False)

    def _attach_evidence(self, draft: dict) -> dict:
        draft_id = draft["draft_id"]
        self._require_approved(draft)
        context = draft.get("target_context") or {}
        employee_name = str(context.get("employee_name") or "").strip()
        review_period = str(context.get("review_period") or "").strip()
        if not employee_name or not review_period:
            raise BusinessImportError(draft_id, "Evidence requires employee_name and review_period.")
        evidence = {"document_id": draft["document_id"],
                    "document_type": self._document_type(draft["document_id"]),
                    "ai_summary": draft.get("ai_summary"),
                    "reviewed_evidence": draft["extracted_data"],
                    "linked_at": datetime.now(timezone.utc).isoformat(),
                    "reviewed_by": draft.get("reviewed_by")}
        try:
            goal = self._business_repo.add_goal_document_evidence(employee_name, review_period, evidence)
        except (ValueError, RuntimeError) as exc:
            raise BusinessImportError(draft_id, f"Failed to attach Goal evidence: {exc}") from exc
        return self._complete_lifecycle(draft, goal, False)

    def _document_type(self, document_id: str) -> str:
        try:
            doc = self._document_repo.get_document(document_id)
            return doc["metadata"]["document_type"]
        except (ValueError, RuntimeError, KeyError) as exc:
            raise BusinessImportError(document_id, f"Failed to resolve evidence document type: {exc}") from exc

    def _validate_create(self, draft: dict) -> dict:
        try:
            model = CandidateCreateRequest if draft["target_business_entity"] == "candidate" else ProductCreateRequest
            return model.model_validate(draft["extracted_data"]).model_dump()
        except ValidationError as exc:
            raise BusinessImportError(draft["draft_id"], f"Final reviewed business data is invalid: {exc}") from exc

    def _complete_lifecycle(self, draft: dict, entity: dict, reused: bool) -> dict:
        draft_id, document_id = draft["draft_id"], draft["document_id"]
        status = DocumentStatus(draft["status"])
        if status not in (DocumentStatus.APPROVED, DocumentStatus.IMPORTED):
            raise BusinessImportError(draft_id, f"Cannot complete lifecycle from '{status.value}'.")
        if status != DocumentStatus.IMPORTED:
            try:
                draft = self._import_draft_repo.update_import_draft(draft_id, {"status": DocumentStatus.IMPORTED.value})
            except (ValueError, RuntimeError) as exc:
                raise BusinessImportError(draft_id, f"Business write exists, but failed to mark draft IMPORTED: {exc}") from exc
        try:
            document = self._document_repo.get_document(document_id)
            document_status = DocumentStatus(document["metadata"]["status"])
            if document_status != DocumentStatus.IMPORTED:
                if document_status != DocumentStatus.APPROVED:
                    raise BusinessImportError(draft_id, f"Cannot complete document lifecycle from '{document_status.value}'.")
                self._document_repo.update_processing_status(document_id, DocumentStatus.IMPORTED)
        except BusinessImportError:
            raise
        except (ValueError, RuntimeError) as exc:
            raise BusinessImportError(draft_id, f"Business write exists, but document lifecycle completion failed: {exc}") from exc
        return {"draft_id": draft_id, "document_id": document_id,
                "target_business_entity": draft["target_business_entity"], "entity": entity,
                "status": DocumentStatus.IMPORTED.value, "reused_existing_entity": reused,
                "message": "Approved draft applied and lifecycle completed."}

    def _get_draft_or_raise(self, draft_id: str) -> dict:
        try:
            return self._import_draft_repo.get_import_draft(draft_id)
        except (ValueError, RuntimeError) as exc:
            raise BusinessImportError(draft_id, f"Failed to retrieve import draft: {exc}") from exc

    def _find_materialized_entity(self, draft_id: str) -> Optional[dict]:
        try:
            return self._business_repo.find_entity_by_source_import_draft_id(draft_id)
        except RuntimeError as exc:
            raise BusinessImportError(draft_id, f"Failed to check import idempotency: {exc}") from exc
