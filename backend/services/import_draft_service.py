"""
import_draft_service.py
=======================
Human review coordination for ENTITY_IMPORT drafts.

Owns:
- progressive correction/completion of extracted_data while pending;
- PENDING_REVIEW -> APPROVED review decisions;
- PENDING_REVIEW -> REJECTED review decisions;
- synchronization of the originating Document lifecycle;
- retry recovery when the draft transition succeeded but document
  synchronization failed.

Does not:
- run processors;
- create ImportDrafts;
- create business entities;
- call BusinessImportService;
- access MongoDB directly;
- contain FastAPI routes.
"""

from __future__ import annotations

from typing import Optional

from pydantic import ValidationError

from backend.api.business_schemas import ProductCreateRequest

from backend.database.business_data_repository import BusinessDataRepository
from backend.database.document_repository import DocumentRepository
from backend.database.import_draft_repository import ImportDraftRepository
from backend.document_processing.document_models import DocumentStatus


class ImportDraftServiceError(Exception):
    """Raised when draft review coordination cannot safely complete."""

    def __init__(self, draft_id: str, reason: str) -> None:
        self.draft_id = draft_id
        self.reason = reason
        super().__init__(
            f"Import draft service failed for '{draft_id}': {reason}"
        )


class ImportDraftService:
    """Coordinates editable review and review lifecycle transitions."""

    def __init__(
        self,
        import_draft_repository: Optional[ImportDraftRepository] = None,
        document_repository: Optional[DocumentRepository] = None,
        business_data_repository: Optional[BusinessDataRepository] = None,
    ) -> None:
        self._import_draft_repo = (
            import_draft_repository or ImportDraftRepository()
        )
        self._document_repo = document_repository or DocumentRepository()
        self._business_repo = (
            business_data_repository or BusinessDataRepository()
        )

    def update_reviewed_data(
        self,
        draft_id: str,
        extracted_data: dict,
    ) -> dict:
        """
        Update human-reviewed extracted data while review is pending.

        CREATE_ENTITY and ATTACH_EVIDENCE preserve the existing replacement
        semantics. ENRICH_ENTITY treats the incoming data as a partial patch
        over the complete proposed final Product state already stored in the
        draft.
        """
        draft = self._get_draft_or_raise(draft_id)
        status = DocumentStatus(draft["status"])

        if status != DocumentStatus.PENDING_REVIEW:
            raise ImportDraftServiceError(
                draft_id=draft_id,
                reason=(
                    f"Draft data can only be edited while pending review; "
                    f"current status is '{status.value}'."
                ),
            )

        reviewed_data = extracted_data

        if draft.get("operation", "create_entity") == "enrich_entity":
            current_proposed = dict(draft.get("extracted_data") or {})
            canonical_product_name = current_proposed.get("product_name")

            if not canonical_product_name:
                raise ImportDraftServiceError(
                    draft_id=draft_id,
                    reason=(
                        "Product enrichment draft is missing its canonical "
                        "product_name."
                    ),
                )

            reviewed_data = {
                **current_proposed,
                **extracted_data,
                "product_name": canonical_product_name,
            }

            try:
                reviewed_data = ProductCreateRequest.model_validate(
                    reviewed_data
                ).model_dump()
            except ValidationError as exc:
                raise ImportDraftServiceError(
                    draft_id=draft_id,
                    reason=f"Invalid reviewed Product state: {exc}",
                ) from exc

        try:
            return self._import_draft_repo.update_import_draft(
                draft_id,
                {"extracted_data": reviewed_data},
            )
        except (ValueError, RuntimeError) as exc:
            raise ImportDraftServiceError(
                draft_id=draft_id,
                reason=f"Failed to update reviewed data: {exc}",
            ) from exc

    def update_operation(
        self,
        draft_id: str,
        operation: str,
        target_entity_key: str | None = None,
    ) -> dict:
        """Select CREATE_ENTITY or prepare a reviewed Product enrichment."""
        draft = self._get_draft_or_raise(draft_id)
        status = DocumentStatus(draft["status"])
        if status != DocumentStatus.PENDING_REVIEW:
            raise ImportDraftServiceError(
                draft_id,
                "Draft operation can only be edited while pending review.",
            )
        if operation not in ("create_entity", "enrich_entity"):
            raise ImportDraftServiceError(
                draft_id, f"Unsupported editable operation '{operation}'."
            )

        updates = {
            "operation": operation,
            "target_entity_key": None,
        }
        if operation == "enrich_entity":
            if draft.get("target_business_entity") != "product":
                raise ImportDraftServiceError(
                    draft_id, "Candidate drafts cannot use ENRICH_ENTITY."
                )
            if not target_entity_key:
                raise ImportDraftServiceError(
                    draft_id,
                    "Product enrichment requires an explicit target Product.",
                )
            try:
                current = self._business_repo.get_product(target_entity_key)
            except (ValueError, RuntimeError) as exc:
                raise ImportDraftServiceError(
                    draft_id,
                    f"Failed to load target Product '{target_entity_key}': {exc}",
                ) from exc

            system_fields = {
                "_id",
                "source_document_ids",
                "source_import_draft_id",
                "source_enrichment_draft_ids",
                "ai_summary",
            }
            proposed = {
                key: value
                for key, value in current.items()
                if key not in system_fields
            }
            proposed.update(draft.get("extracted_data") or {})
            for key in system_fields:
                proposed.pop(key, None)
            proposed["product_name"] = current["product_name"]

            updates = {
                "operation": operation,
                "target_entity_key": current["product_name"],
                "extracted_data": proposed,
            }

        try:
            return self._import_draft_repo.update_import_draft(
                draft_id, updates
            )
        except (ValueError, RuntimeError) as exc:
            raise ImportDraftServiceError(
                draft_id, f"Failed to update draft operation: {exc}"
            ) from exc

    def update_target_context(
        self,
        draft_id: str,
        *,
        employee_name: str,
        review_period: str,
    ) -> dict:
        """Correct evidence Goal association while review is pending."""
        draft = self._get_draft_or_raise(draft_id)
        status = DocumentStatus(draft["status"])
        if status != DocumentStatus.PENDING_REVIEW:
            raise ImportDraftServiceError(
                draft_id=draft_id,
                reason=(
                    "Draft target context can only be edited while pending "
                    f"review; current status is '{status.value}'."
                ),
            )
        if draft.get("operation", "create_entity") != "attach_evidence":
            raise ImportDraftServiceError(
                draft_id=draft_id,
                reason="Target context editing is only valid for evidence drafts.",
            )
        try:
            return self._import_draft_repo.update_import_draft(
                draft_id,
                {"target_context": {
                    "employee_name": employee_name,
                    "review_period": review_period,
                }},
            )
        except (ValueError, RuntimeError) as exc:
            raise ImportDraftServiceError(
                draft_id=draft_id,
                reason=f"Failed to update target context: {exc}",
            ) from exc

    def approve(
        self,
        draft_id: str,
        reviewed_by: str,
        review_notes: Optional[str] = None,
    ) -> dict:
        """Approve a pending draft and synchronize its document."""
        return self._apply_decision(
            draft_id=draft_id,
            desired_status=DocumentStatus.APPROVED,
            reviewed_by=reviewed_by,
            review_notes=review_notes,
        )

    def reject(
        self,
        draft_id: str,
        reviewed_by: str,
        review_notes: Optional[str] = None,
    ) -> dict:
        """Reject a pending draft and synchronize its document."""
        return self._apply_decision(
            draft_id=draft_id,
            desired_status=DocumentStatus.REJECTED,
            reviewed_by=reviewed_by,
            review_notes=review_notes,
        )

    def _apply_decision(
        self,
        *,
        draft_id: str,
        desired_status: DocumentStatus,
        reviewed_by: str,
        review_notes: Optional[str],
    ) -> dict:
        draft = self._get_draft_or_raise(draft_id)
        current_status = DocumentStatus(draft["status"])

        if current_status == desired_status:
            # Recovery path: draft transition already succeeded during a
            # prior call, so only repair document synchronization.
            return self._synchronize_document(draft, desired_status)

        if current_status != DocumentStatus.PENDING_REVIEW:
            raise ImportDraftServiceError(
                draft_id=draft_id,
                reason=(
                    f"Cannot change draft from '{current_status.value}' "
                    f"to '{desired_status.value}'."
                ),
            )

        try:
            if desired_status == DocumentStatus.APPROVED:
                draft = self._import_draft_repo.approve_import_draft(
                    draft_id,
                    reviewed_by,
                    review_notes,
                )
            else:
                draft = self._import_draft_repo.reject_import_draft(
                    draft_id,
                    reviewed_by,
                    review_notes,
                )
        except (ValueError, RuntimeError) as exc:
            raise ImportDraftServiceError(
                draft_id=draft_id,
                reason=(
                    f"Failed to set draft status to "
                    f"'{desired_status.value}': {exc}"
                ),
            ) from exc

        return self._synchronize_document(draft, desired_status)

    def _synchronize_document(
        self,
        draft: dict,
        desired_status: DocumentStatus,
    ) -> dict:
        draft_id = draft["draft_id"]
        document_id = draft["document_id"]

        try:
            document = self._document_repo.get_document(document_id)
        except (ValueError, RuntimeError) as exc:
            raise ImportDraftServiceError(
                draft_id=draft_id,
                reason=f"Failed to retrieve source document: {exc}",
            ) from exc

        document_status = DocumentStatus(document["metadata"]["status"])

        if document_status == desired_status:
            return {
                "draft": draft,
                "document": document,
                "status": desired_status.value,
                "message": "Review decision already synchronized.",
            }

        if document_status in (
            DocumentStatus.APPROVED,
            DocumentStatus.REJECTED,
            DocumentStatus.IMPORTED,
        ):
            raise ImportDraftServiceError(
                draft_id=draft_id,
                reason=(
                    f"Document '{document_id}' is already in conflicting "
                    f"lifecycle status '{document_status.value}'."
                ),
            )

        if document_status != DocumentStatus.PENDING_REVIEW:
            raise ImportDraftServiceError(
                draft_id=draft_id,
                reason=(
                    f"Cannot synchronize document '{document_id}' from "
                    f"status '{document_status.value}' to "
                    f"'{desired_status.value}'."
                ),
            )

        try:
            document = self._document_repo.update_processing_status(
                document_id,
                desired_status,
            )
        except (ValueError, RuntimeError) as exc:
            raise ImportDraftServiceError(
                draft_id=draft_id,
                reason=(
                    f"Draft is '{desired_status.value}' but document "
                    f"synchronization failed: {exc}"
                ),
            ) from exc

        return {
            "draft": draft,
            "document": document,
            "status": desired_status.value,
            "message": "Review decision synchronized successfully.",
        }

    def _get_draft_or_raise(self, draft_id: str) -> dict:
        try:
            return self._import_draft_repo.get_import_draft(draft_id)
        except (ValueError, RuntimeError) as exc:
            raise ImportDraftServiceError(
                draft_id=draft_id,
                reason=f"Failed to retrieve import draft: {exc}",
            ) from exc