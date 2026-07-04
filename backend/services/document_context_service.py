"""
document_context_service.py
=============================
M6.6 — DocumentContextService: the single centralized policy/access layer
for all document context reaching workflows/agents.

    Agent -> DataLoader -> DocumentContextService -> DocumentRepository / DocumentStorage

This service NEVER talks to agents or LLMs, and agents/DataLoader NEVER
talk to DocumentRepository/DocumentStorage directly for document content.

Responsibilities
----------------
1. Selection/validation
   - validate_workflow_source_selection(): explicit IDs supplied as
     workflow input (market_research, performance_report). Atomic —
     any invalid ID fails the whole selection.
   - Entity-linked resolution is done by BusinessDataRepository
     (get_product_source_document_ids / get_goal_evidence_document_ids /
     get_candidate_source_document_ids); this service only validates the
     IDs those lookups return via validate_entity_linked_ids().

2. Lightweight context — document_id, document_type, filename, AI summary,
   structured extracted data. No full text.

3. Deep content — full extracted text, only for IDs already present in
   the workflow's AgentState.document_ids.

4. Original file — deepest, most exceptional access level. Same
   selected-ID enforcement, delegates storage resolution to DocumentStorage.

No AI calls happen in this service. No agent/LLM imports. No workflow
imports (this module knows nothing about AgentState, Task, or executors —
callers pass plain document_id lists).
"""

from __future__ import annotations

import logging
from typing import Optional

from backend.database.document_repository import DocumentRepository
from backend.document_processing.document_models import DocumentStatus
from backend.services.document_storage import (
    DocumentStorage,
    DocumentStorageError,
    LocalDocumentStorage,
)
from backend.services.document_access_exceptions import (
    DocumentNotFoundError,
    DocumentNotEligibleError,
    DocumentTypeNotAllowedError,
    DocumentNotSelectedError,
    ExtractedTextUnavailableError,
    OriginalFileUnavailableError,
)

logger = logging.getLogger(__name__)

# Lifecycle states a document may be in for each access path.
_WORKFLOW_SOURCE_ELIGIBLE_STATUS = DocumentStatus.PROCESSED.value
_ENTITY_LINKED_ELIGIBLE_STATUS = DocumentStatus.IMPORTED.value
# Runtime content access (lightweight/text/file) accepts either — a
# document reaching AgentState.document_ids has already cleared one of
# the two selection paths above.
_RUNTIME_VALID_STATUSES = {
    DocumentStatus.PROCESSED.value,
    DocumentStatus.IMPORTED.value,
}


def _dedupe_preserve_order(ids: list[str]) -> list[str]:
    """Deduplicate a list of IDs while preserving first-seen order."""
    return list(dict.fromkeys(ids))


class DocumentContextService:
    """Centralized document eligibility/access policy layer for M6.6."""

    def __init__(
        self,
        repository: Optional[DocumentRepository] = None,
        storage: Optional[DocumentStorage] = None,
    ) -> None:
        """
        Args:
            repository: Optional DocumentRepository (injected for tests).
            storage:    Optional DocumentStorage (injected for tests).
        """
        self._repository = repository or DocumentRepository()
        self._storage = storage or LocalDocumentStorage()

    # ------------------------------------------------------------------
    # PRIVATE HELPERS
    # ------------------------------------------------------------------

    def _fetch_many(self, document_ids: list[str]) -> dict[str, dict]:
        """Bulk-fetch documents, returned as a document_id -> doc dict."""
        docs = self._repository.get_documents_by_ids(document_ids)
        return {d["document_id"]: d for d in docs}

    @staticmethod
    def _status_of(doc: dict) -> str:
        return doc.get("metadata", {}).get("status")

    @staticmethod
    def _type_of(doc: dict) -> Optional[str]:
        return doc.get("metadata", {}).get("document_type")

    # ------------------------------------------------------------------
    # SELECTION / VALIDATION
    # ------------------------------------------------------------------

    def validate_workflow_source_selection(
        self,
        document_ids: list[str],
        *,
        workflow_slot: str,
        allowed_document_types: set[str],
    ) -> list[str]:
        """
        Validate an explicit list of workflow-source document IDs for one
        workflow input slot (e.g. 'market_research', 'performance_report.hr',
        'performance_report.sales').

        Eligibility (ALL required, checked atomically):
          - document exists,
          - metadata.status == PROCESSED,
          - metadata.document_type is one of allowed_document_types.

        Empty input is valid and returns [] (no selection made).

        Args:
            document_ids: Caller-supplied IDs (order as given by the caller).
            workflow_slot: Label identifying the slot being validated, used
                            only in error messages (e.g. 'market_research').
            allowed_document_types: Exact document_type strings eligible
                            for this slot.

        Returns:
            Deduplicated, order-preserved list of validated document IDs.

        Raises:
            DocumentNotFoundError, DocumentNotEligibleError,
            DocumentTypeNotAllowedError: On the first ineligible ID found.
            Nothing is partially accepted — either the whole selection
            validates, or the call raises before returning.
        """
        deduped = _dedupe_preserve_order(document_ids)
        if not deduped:
            return []

        docs_by_id = self._fetch_many(deduped)

        for doc_id in deduped:
            doc = docs_by_id.get(doc_id)
            if doc is None:
                raise DocumentNotFoundError(doc_id)

            status = self._status_of(doc)
            if status != _WORKFLOW_SOURCE_ELIGIBLE_STATUS:
                raise DocumentNotEligibleError(
                    doc_id, status, _WORKFLOW_SOURCE_ELIGIBLE_STATUS
                )

            doc_type = self._type_of(doc)
            if doc_type not in allowed_document_types:
                raise DocumentTypeNotAllowedError(doc_id, doc_type, workflow_slot)

        return deduped

    def validate_entity_linked_ids(
        self,
        document_ids: list[str],
        *,
        workflow_slot: str,
    ) -> list[str]:
        """
        Validate document IDs resolved from a trusted business-entity
        relationship (Product.source_document_ids, Goal.document_evidence,
        Candidate resume links).

        Eligibility (ALL required):
          - document exists,
          - metadata.status == IMPORTED (the completed import lifecycle
            state for entity-linked documents).

        A missing/deleted document referenced by a business entity does
        NOT fail workflow initialization — it is silently dropped, since
        the entity relationship itself (not the caller) produced this ID
        and the workflow should still be able to proceed using whatever
        valid evidence remains. This mirrors "no linked documents still
        allows workflow execution" for Sales Outreach / Performance
        Review / Performance Report.

        Args:
            document_ids: IDs from a trusted entity-linked lookup.
            workflow_slot: Label for logging only.

        Returns:
            Deduplicated, order-preserved list of document IDs that are
            still valid. May be shorter than the input, or empty.
        """
        deduped = _dedupe_preserve_order(document_ids)
        if not deduped:
            return []

        docs_by_id = self._fetch_many(deduped)
        valid: list[str] = []

        for doc_id in deduped:
            doc = docs_by_id.get(doc_id)
            if doc is None:
                logger.info(
                    "Entity-linked document '%s' (slot=%s) no longer exists; skipping.",
                    doc_id, workflow_slot,
                )
                continue
            if self._status_of(doc) != _ENTITY_LINKED_ELIGIBLE_STATUS:
                logger.info(
                    "Entity-linked document '%s' (slot=%s) has status '%s' != IMPORTED; skipping.",
                    doc_id, workflow_slot, self._status_of(doc),
                )
                continue
            valid.append(doc_id)

        return valid

    # ------------------------------------------------------------------
    # RUNTIME ENFORCEMENT HELPER
    # ------------------------------------------------------------------

    def _enforce_selected(
        self,
        document_id: str,
        allowed_document_ids: list[str],
        workflow_id: str,
    ) -> dict:
        """
        Revalidate one document_id at content-access time:
          1. it must belong to the workflow's allowed_document_ids,
          2. it must still exist,
          3. it must still be in a valid completed lifecycle status.

        Returns the fetched document dict on success.
        """
        if document_id not in allowed_document_ids:
            raise DocumentNotSelectedError(document_id, workflow_id)

        try:
            doc = self._repository.get_document(document_id)
        except ValueError:
            raise DocumentNotFoundError(document_id)

        status = self._status_of(doc)
        if status not in _RUNTIME_VALID_STATUSES:
            raise DocumentNotEligibleError(
                document_id, status, "/".join(sorted(_RUNTIME_VALID_STATUSES))
            )

        return doc

    # ------------------------------------------------------------------
    # LIGHTWEIGHT CONTEXT
    # ------------------------------------------------------------------

    @staticmethod
    def _to_lightweight(doc: dict) -> dict:
        metadata = doc.get("metadata", {}) or {}
        processing_result = doc.get("processing_result") or {}
        return {
            "document_id": doc.get("document_id"),
            "document_type": metadata.get("document_type"),
            "original_filename": metadata.get("original_filename"),
            "ai_summary": processing_result.get("ai_summary"),
            "structured_data": processing_result.get("extracted_data") or {},
        }

    def get_lightweight_context(
        self,
        document_id: str,
        *,
        allowed_document_ids: list[str],
        workflow_id: str,
    ) -> dict:
        """
        Return lightweight context for one selected document: document_id,
        document_type, original_filename, ai_summary, structured_data.
        Never includes full extracted text or Mongo _id.

        Raises:
            DocumentNotSelectedError, DocumentNotFoundError,
            DocumentNotEligibleError.
        """
        doc = self._enforce_selected(document_id, allowed_document_ids, workflow_id)
        return self._to_lightweight(doc)

    def get_lightweight_contexts(
        self,
        document_ids: list[str],
        *,
        allowed_document_ids: list[str],
        workflow_id: str,
    ) -> list[dict]:
        """
        Return lightweight context for several selected documents. Each ID
        is independently enforced/revalidated; if document_ids is a subset
        of allowed_document_ids there is no partial-failure ambiguity —
        any ineligible ID raises immediately (fail clearly rather than
        silently dropping requested content).
        """
        return [
            self.get_lightweight_context(
                doc_id,
                allowed_document_ids=allowed_document_ids,
                workflow_id=workflow_id,
            )
            for doc_id in document_ids
        ]

    # ------------------------------------------------------------------
    # DEEP CONTENT — FULL EXTRACTED TEXT
    # ------------------------------------------------------------------

    def get_extracted_text(
        self,
        document_id: str,
        *,
        allowed_document_ids: list[str],
        workflow_id: str,
    ) -> str:
        """
        Return the full extracted text for one selected document.

        Does NOT fall back to the original file — if extracted text is
        unavailable, this raises rather than silently escalating access
        level. Callers that genuinely need deeper context must explicitly
        call get_original_file().

        Raises:
            DocumentNotSelectedError, DocumentNotFoundError,
            DocumentNotEligibleError, ExtractedTextUnavailableError.
        """
        doc = self._enforce_selected(document_id, allowed_document_ids, workflow_id)
        text = doc.get("extracted_text")
        if not text:
            raise ExtractedTextUnavailableError(document_id)
        return text

    # ------------------------------------------------------------------
    # ORIGINAL FILE — DEEPEST, MOST EXCEPTIONAL ACCESS
    # ------------------------------------------------------------------

    def get_original_file(
        self,
        document_id: str,
        *,
        allowed_document_ids: list[str],
        workflow_id: str,
    ) -> bytes:
        """
        Return the original file bytes for one selected document, via the
        existing DocumentStorage layer. This is the deepest, most
        exceptional access level — intended only for a future
        agent/tool that cannot get enough context from structured fields,
        AI summary, or extracted text.

        Never places the returned bytes into AgentState; the caller
        (DataLoader) must not do so either.

        Raises:
            DocumentNotSelectedError, DocumentNotFoundError,
            DocumentNotEligibleError, OriginalFileUnavailableError.
        """
        self._enforce_selected(document_id, allowed_document_ids, workflow_id)

        try:
            return self._storage.get_file(document_id)
        except DocumentStorageError as exc:
            raise OriginalFileUnavailableError(document_id, exc.reason) from exc
