"""
document_lifecycle_service.py
==============================
DocumentLifecycleService — deletion eligibility policy and cleanup
orchestration for the Document Upload & AI Document Ingestion subsystem
(Milestone 7).

This service owns exactly one decision: "can this document be deleted
without destroying durable entity/import/evidence lineage, and if so,
how do we clean it up?" It is a peer of DocumentService and
DocumentProcessingService, not a replacement for either.

Deletion policy
----------------
Allowed  (no durable lineage destroyed):
    - UPLOADED / CLASSIFIED / FAILED — never reached a reviewable or
      durable outcome.
    - REJECTED — a human explicitly rejected the derived draft; nothing
      durable was ever produced from it.
    - PROCESSED — reached the processing stage but produced no draft
      requiring review (workflow-source documents), or no draft exists
      yet at all, AND the document is not currently attached to a
      workflow (workflow_id is None).

Blocked  (409 DOCUMENT_NOT_DELETABLE):
    - PENDING_REVIEW / APPROVED — an ImportDraft is awaiting or has
      received review and is on its way to (or already at) durable
      entity/evidence creation.
    - IMPORTED — a durable Candidate, Product, or Goal-evidence record
      has already been created from this document.
    - PROCESSING — an in-progress or recoverable processing state must not
      be destroyed while lifecycle recovery may still be required.  
    - Any document with an existing ImportDraft still in
      PENDING_REVIEW / APPROVED / IMPORTED status, even if the
      document's own status has drifted (defense in depth against
      partial-failure lifecycle desync).
    - Any document currently attached to a workflow (workflow_id set),
      since it is an active lifecycle dependency.

This module never cascades into business collections, never unlinks
imported Candidate/Product/Goal relationships, and never rewrites
workflow history — it only ever deletes the document's own record,
its own physical file, and (when safe) its own non-durable draft.
"""

from __future__ import annotations

import logging
from typing import Optional

from backend.database.document_repository import DocumentRepository
from backend.database.import_draft_repository import ImportDraftRepository
from backend.document_processing.document_models import DocumentStatus
from backend.services.document_storage import (
    DocumentStorage,
    DocumentStorageError,
    LocalDocumentStorage,
)

logger = logging.getLogger(__name__)

# Document lifecycle statuses that always block deletion outright.
_BLOCKED_DOCUMENT_STATUSES = (
    DocumentStatus.PENDING_REVIEW,
    DocumentStatus.PROCESSING,
    DocumentStatus.APPROVED,
    DocumentStatus.IMPORTED,
)

# ImportDraft statuses that block deletion of their originating document,
# checked independently of the document's own status as a defense-in-depth
# measure against partial-failure lifecycle desync.
_BLOCKED_DRAFT_STATUSES = (
    DocumentStatus.PENDING_REVIEW,
    DocumentStatus.APPROVED,
    DocumentStatus.IMPORTED,
)


# ==========================================================
# STANDARDIZED SERVICE EXCEPTIONS
# ==========================================================

class DocumentLifecycleError(Exception):
    """
    Raised when a lifecycle operation fails for infrastructural reasons
    such as persistence or storage failure. Missing documents use
    DocumentLifecycleNotFoundError, while policy refusals use
    DocumentNotDeletableError.
    """

    def __init__(self, document_id: str, reason: str) -> None:
        self.document_id = document_id
        self.reason = reason
        super().__init__(
            f"Document lifecycle operation failed for '{document_id}': {reason}"
        )


class DocumentNotDeletableError(Exception):
    """
    Raised when a document exists but current durable-lineage policy
    forbids deleting it. Routes map this to 409 DOCUMENT_NOT_DELETABLE.
    """

    def __init__(self, document_id: str, reason: str) -> None:
        self.document_id = document_id
        self.reason = reason
        super().__init__(f"Document '{document_id}' cannot be deleted: {reason}")


class DocumentLifecycleNotFoundError(DocumentLifecycleError):
    """Raised when the requested document does not exist."""


# ==========================================================
# DOCUMENT LIFECYCLE SERVICE
# ==========================================================

class DocumentLifecycleService:
    """Owns conditional deletion eligibility and cleanup orchestration."""

    def __init__(
        self,
        document_repository: Optional[DocumentRepository] = None,
        import_draft_repository: Optional[ImportDraftRepository] = None,
        document_storage: Optional[DocumentStorage] = None,
    ) -> None:
        self._document_repo = document_repository or DocumentRepository()
        self._import_draft_repo = import_draft_repository or ImportDraftRepository()
        self._storage: DocumentStorage = document_storage or LocalDocumentStorage()

    # ==================================================================
    # PUBLIC ENTRY POINT
    # ==================================================================

    def delete_document(self, document_id: str) -> dict:
        """
        Delete a document if, and only if, doing so destroys no durable
        entity/import/evidence lineage.

        Cleanup order: any safe non-durable draft is removed first, then
        the physical file, then the document record. Cleanup failures are
        surfaced and abort the remaining deletion steps.

        Args:
            document_id: Identifier of the document to delete.

        Returns:
            {"document_id": ..., "message": ...}

        Raises:
            DocumentLifecycleNotFoundError:
                If the document does not exist.
            DocumentLifecycleError:
                If an unexpected persistence or storage failure occurs.
            DocumentNotDeletableError:
                If deletion is blocked by policy.
        """
        document = self._get_document_or_raise(document_id)
    
        non_durable_draft = self._assert_deletable(document)

        if non_durable_draft is not None:
            self._delete_draft_or_raise(
                document_id,
                non_durable_draft["draft_id"],
            )

        self._delete_file_or_raise(document_id)

        try:
            self._document_repo.delete_document(document_id)
        except (ValueError, RuntimeError) as exc:
            raise DocumentLifecycleError(
                document_id=document_id,
                reason=f"Failed to delete document record: {exc}",
            ) from exc

        logger.info("Document '%s' deleted (lifecycle-eligible).", document_id)
        return {
            "document_id": document_id,
            "message": "Document deleted successfully.",
        }

    # ==================================================================
    # POLICY
    # ==================================================================

    def _assert_deletable(self, document: dict) -> Optional[dict]:
        """
        Enforce deletion policy for one document.

        Returns:
            The document's own non-durable (REJECTED) ImportDraft dict,
            if one exists and should be cleaned up alongside the
            document — otherwise None.

        Raises:
            DocumentNotDeletableError: If any protection rule applies.
        """
        document_id = document["document_id"]
        metadata = document.get("metadata") or {}
        status = DocumentStatus(metadata["status"])

        if status in _BLOCKED_DOCUMENT_STATUSES:
            raise DocumentNotDeletableError(
                document_id,
                (
                    f"Document has lifecycle status '{status.value}', which "
                    f"carries durable entity/import/evidence lineage and "
                    f"cannot be deleted."
                ),
            )

        drafts = self._safe_list_drafts(document_id)
        blocking_draft = None
        non_durable_draft = None
        for draft in drafts:
            draft_status = DocumentStatus(draft["status"])
            if draft_status in _BLOCKED_DRAFT_STATUSES:
                blocking_draft = draft
                break
            # REJECTED is the only draft status expected alongside a
            # deletable document; anything else (defensively) is left
            # alone rather than guessed at.
            if draft_status == DocumentStatus.REJECTED:
                non_durable_draft = draft

        if blocking_draft is not None:
            raise DocumentNotDeletableError(
                document_id,
                (
                    f"Document has an associated import draft "
                    f"'{blocking_draft['draft_id']}' in status "
                    f"'{blocking_draft['status']}', which carries durable "
                    f"entity/import/evidence lineage and cannot be deleted."
                ),
            )

        if document.get("workflow_id") is not None:
            raise DocumentNotDeletableError(
                document_id,
                (
                   "Document is explicitly attached to workflow "
                   f"'{document['workflow_id']}' and cannot be deleted."
                ),
            )

        return non_durable_draft

    # ==================================================================
    # PRIVATE HELPERS
    # ==================================================================

    def _get_document_or_raise(self, document_id: str) -> dict:
        try:
            return self._document_repo.get_document(document_id)
        except ValueError as exc:
            raise DocumentLifecycleNotFoundError(
                document_id=document_id,
                reason="Document not found.",
            ) from exc
        except RuntimeError as exc:
            raise DocumentLifecycleError(
                document_id=document_id,
                reason=f"Failed to retrieve document: {exc}",
            ) from exc

    def _safe_list_drafts(self, document_id: str) -> list[dict]:
        """
        List drafts for a document, surfacing genuine failures but never
        silently treating a lookup failure as "no drafts" — an
        infrastructure failure here must not be mistaken for a green
        light to delete.
        """
        try:
            return self._import_draft_repo.list_drafts(document_id=document_id)
        except (ValueError, RuntimeError) as exc:
            raise DocumentLifecycleError(
                document_id=document_id,
                reason=f"Failed to check import draft lineage: {exc}",
            ) from exc

    def _delete_draft_or_raise(
        self,
        document_id: str,
        draft_id: str,
    ) -> None:
        try:
            self._import_draft_repo.delete_import_draft(draft_id)
        except (ValueError, RuntimeError) as exc:
            raise DocumentLifecycleError(
                document_id=document_id,
                reason=(
                    f"Failed to delete non-durable import draft "
                    f"'{draft_id}': {exc}"
                ),
            ) from exc

    def _delete_file_or_raise(self, document_id: str) -> None:
        try:
            if self._storage.file_exists(document_id):
                self._storage.delete_file(document_id)
        except DocumentStorageError as exc:
            raise DocumentLifecycleError(
                document_id=document_id,
                reason=f"Failed to delete stored file: {exc}",
            ) from exc
