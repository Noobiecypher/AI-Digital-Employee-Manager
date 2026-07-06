"""
document_processing_service.py
===============================
DocumentProcessingService — processing orchestration for the Document
Upload & AI Document Ingestion subsystem (Milestone 6).

Owns exactly one pipeline stage: CLASSIFIED -> processor -> persisted
ProcessingResult -> (ENTITY_IMPORT only) ImportDraft -> PENDING_REVIEW.

This is a peer of DocumentService (backend/services/document_service.py),
not a replacement or extension of it. DocumentService is frozen and its
own docstring explicitly excludes processor execution, ProcessingResult
creation, and ImportDraft creation — this service begins exactly where
DocumentService stops (status == CLASSIFIED).

Explicitly NOT this module's responsibility
--------------------------------------------
- Upload / physical storage / initial classification (DocumentService).
- Human review coordination (ImportDraftService).
- Business entity creation (BusinessImportService).
- Any FastAPI route or request/response schema concerns.

Stage-aware recovery (Correction 1)
------------------------------------
process_document() re-reads the document first and branches on its
current status rather than using a single CLASSIFIED-only retry gate:

    CLASSIFIED
        -> run the processor, persist ProcessingResult, advance.
    PROCESSED (ProcessingResult already persisted)
        -> never rerun the processor;
        -> for ENTITY_IMPORT, create the draft only if one doesn't
           already exist yet (checked via
           ImportDraftRepository.list_drafts(document_id=...), which
           already provides this lookup — no repository change needed).
    PROCESSING / FAILED
        -> if a ProcessingResult is already durably persisted (a crash
           happened after persistence but before the status advanced),
           resume from that result exactly as the PROCESSED case does;
        -> otherwise, do NOT blindly rerun an uncertain LLM operation —
           raise, so the caller/human can decide (there is no way to
           know whether a half-finished extraction is safe to retry).
    PENDING_REVIEW / APPROVED / REJECTED / IMPORTED
        -> already past this stage; never rerun the processor, never
           create a duplicate draft. Reported back as a no-op.

Collaborators
-------------
DocumentRepository, ImportDraftRepository — both already used by
DocumentService, kept at the same architectural layer
(backend/services/). ProcessorRegistry.get_processor_class() is used to
resolve (not instantiate ahead of time) the processor class for a given
ClassificationResult.
"""

from __future__ import annotations

import logging
from typing import Optional
from uuid import uuid4

from backend.database.document_repository import DocumentRepository
from backend.database.import_draft_repository import ImportDraftRepository
from backend.document_processing.base_processor import ProcessorError
from backend.document_processing.document_models import (
    ClassificationResult,
    DocumentMetadata,
    DraftOperation,
    DocumentOutcome,
    DocumentStatus,
    ProcessingResult,
)
from backend.document_processing.processor_registry import get_processor_class

logger = logging.getLogger(__name__)

# Statuses from which a processor result can safely be trusted as
# already-durably-persisted and reused, rather than rerun.
_RESULT_RESUMABLE_STATUSES = (
    DocumentStatus.PROCESSED,
    DocumentStatus.PROCESSING,
    DocumentStatus.FAILED,
)

# Statuses that mean this stage is already complete; process_document()
# is a safe no-op for these.
_ALREADY_PAST_STAGE_STATUSES = (
    DocumentStatus.PENDING_REVIEW,
    DocumentStatus.APPROVED,
    DocumentStatus.REJECTED,
    DocumentStatus.IMPORTED,
)


# ==========================================================
# STANDARDIZED SERVICE EXCEPTION
# ==========================================================

class DocumentProcessingError(Exception):
    """
    Raised when the processing-orchestration pipeline fails, or when a
    document is in a state that cannot be safely (re)processed.

    Carries document_id and a human-readable reason.
    """

    def __init__(self, document_id: str, reason: str) -> None:
        self.document_id = document_id
        self.reason = reason
        super().__init__(
            f"Document processing failed for '{document_id}': {reason}"
        )


# ==========================================================
# DOCUMENT PROCESSING SERVICE
# ==========================================================

class DocumentProcessingService:
    """
    Orchestrates CLASSIFIED -> processor -> ProcessingResult -> (ENTITY_IMPORT
    only) ImportDraft -> PENDING_REVIEW, with stage-aware crash recovery.
    """

    def __init__(
        self,
        document_repository: Optional[DocumentRepository] = None,
        import_draft_repository: Optional[ImportDraftRepository] = None,
    ) -> None:
        self._document_repo: DocumentRepository = (
            document_repository or DocumentRepository()
        )
        self._import_draft_repo: ImportDraftRepository = (
            import_draft_repository or ImportDraftRepository()
        )

    # ==================================================================
    # PUBLIC ENTRY POINT
    # ==================================================================

    def process_document(self, document_id: str) -> dict:
        """
        Advance a document through processing, stage-aware.

        Args:
            document_id: Identifier of the document to process.

        Returns:
            dict with at least:
                document_id, status, draft_id (or None), message

        Raises:
            DocumentProcessingError: If the document cannot be safely
                                      (re)processed in its current state,
                                      or a pipeline step fails.
        """
        document = self._get_document_or_raise(document_id)
        status = DocumentStatus(document["metadata"]["status"])

        if status == DocumentStatus.CLASSIFIED:
            document = self._run_processor(document)
            return self._advance_after_result(document)

        if status in _RESULT_RESUMABLE_STATUSES:
            if document.get("processing_result"):
                return self._advance_after_result(document)
            raise DocumentProcessingError(
                document_id=document_id,
                reason=(
                    f"Document is in status '{status.value}' with no "
                    f"persisted ProcessingResult. Rerunning an uncertain "
                    f"LLM operation is not safe; manual intervention is "
                    f"required before this document can be reprocessed."
                ),
            )

        if status in _ALREADY_PAST_STAGE_STATUSES:
            existing_draft = self._find_existing_draft(document_id)
            return {
                "document_id": document_id,
                "status": status.value,
                "draft_id": existing_draft["draft_id"] if existing_draft else None,
                "message": (
                    f"Document already past the processing stage "
                    f"(status='{status.value}'); no action taken."
                ),
            }

        raise DocumentProcessingError(
            document_id=document_id,
            reason=(
                f"Cannot process document in status '{status.value}'; "
                f"expected CLASSIFIED, or a resumable PROCESSED/"
                f"PROCESSING/FAILED state."
            ),
        )

    # ==================================================================
    # INTERNAL: FRESH PROCESSOR RUN (status == CLASSIFIED)
    # ==================================================================

    def _run_processor(self, document: dict) -> dict:
        document_id = document["document_id"]

        try:
            self._document_repo.update_processing_status(
                document_id, DocumentStatus.PROCESSING
            )
        except (ValueError, RuntimeError) as exc:
            raise DocumentProcessingError(
                document_id=document_id,
                reason=f"Failed to mark document as PROCESSING: {exc}",
            ) from exc

        classification = ClassificationResult(**document["classification"])
        metadata = DocumentMetadata(**document["metadata"])
        content = document.get("extracted_text") or ""

        try:
            processor_class = get_processor_class(classification)
            processor = processor_class()
            result: ProcessingResult = processor.run(content, metadata)
        except (ProcessorError, NotImplementedError) as exc:
            self._mark_failed(document_id, str(exc))
            raise DocumentProcessingError(
                document_id=document_id,
                reason=f"Processing failed: {exc}",
            ) from exc

        try:
            self._document_repo.update_processing_result(document_id, result)
        except (ValueError, RuntimeError) as exc:
            self._mark_failed(
                document_id, f"Failed to persist ProcessingResult: {exc}"
            )
            raise DocumentProcessingError(
                document_id=document_id,
                reason=f"Failed to persist ProcessingResult: {exc}",
            ) from exc

        logger.info(
            "Document '%s' processed by '%s'.", document_id, result.processor_name
        )
        return self._get_document_or_raise(document_id)

    # ==================================================================
    # INTERNAL: ADVANCE PAST A PERSISTED RESULT
    # (fresh run continuation, or PROCESSED/PROCESSING/FAILED recovery)
    # ==================================================================

    def _advance_after_result(self, document: dict) -> dict:
        document_id = document["document_id"]
        classification = ClassificationResult(**document["classification"])
        status = DocumentStatus(document["metadata"]["status"])

        if status in (DocumentStatus.PROCESSING, DocumentStatus.FAILED):
            try:
                document = self._document_repo.update_processing_status(
                    document_id, DocumentStatus.PROCESSED
                )
            except (ValueError, RuntimeError) as exc:
                raise DocumentProcessingError(
                    document_id=document_id,
                    reason=f"Failed to advance status to PROCESSED: {exc}",
                ) from exc
            status = DocumentStatus.PROCESSED

        if classification.outcome == DocumentOutcome.WORKFLOW_SOURCE:
            return {
                "document_id": document_id,
                "status": status.value,
                "draft_id": None,
                "message": "Processing complete; no draft required.",
            }

        return self._ensure_import_draft(document, classification, status)

    # ==================================================================
    # INTERNAL: ENTITY_IMPORT DRAFT CREATION (create-if-missing)
    # ==================================================================

    def _ensure_import_draft(
        self,
        document: dict,
        classification: ClassificationResult,
        status: DocumentStatus,
    ) -> dict:
        document_id = document["document_id"]

        existing_draft = self._find_existing_draft(document_id)
        if existing_draft is not None:
            draft_status = DocumentStatus(existing_draft["status"])

            if draft_status not in (
                DocumentStatus.PENDING_REVIEW,
                DocumentStatus.APPROVED,
                DocumentStatus.REJECTED,
                DocumentStatus.IMPORTED,
            ):
                raise DocumentProcessingError(
                    document_id=document_id,
                    reason=(
                        f"Existing import draft '{existing_draft['draft_id']}' "
                        f"has invalid lifecycle status '{draft_status.value}'."
                    ),
                )

            if status != draft_status:
                try:
                    self._document_repo.update_processing_status(
                        document_id, draft_status
                    )
                except (ValueError, RuntimeError) as exc:
                    raise DocumentProcessingError(
                        document_id=document_id,
                        reason=(
                            f"Import draft '{existing_draft['draft_id']}' "
                            f"already exists with status "
                            f"'{draft_status.value}', but failed to synchronize "
                            f"the document lifecycle: {exc}"
                        ),
                    ) from exc

            return {
                "document_id": document_id,
                "status": draft_status.value,
                "draft_id": existing_draft["draft_id"],
                "message": (
                    "Import draft already existed; none created. "
                    f"Lifecycle preserved at '{draft_status.value}'."
                ),
            }

        result = ProcessingResult(**document["processing_result"])
        draft_id = f"draft_{uuid4()}"
        metadata = document.get("metadata") or {}
        if classification.outcome == DocumentOutcome.ENTITY_EVIDENCE:
            operation = DraftOperation.ATTACH_EVIDENCE
            target_context = dict(metadata.get("target_context") or {})
        else:
            operation = DraftOperation.CREATE_ENTITY
            target_context = {}

        try:
            self._import_draft_repo.create_import_draft(
                {
                    "draft_id": draft_id,
                    "document_id": document_id,
                    "source_document_ids": [document_id],
                    "business_domain": classification.business_domain,
                    "target_business_entity": classification.target_business_entity,
                    "operation": operation,
                    "target_context": target_context,
                    "extracted_data": result.extracted_data,
                    "confidence": result.confidence,
                    "ai_summary": result.ai_summary,
                }
            )
        except (ValueError, RuntimeError) as exc:
            # Draft creation failed: document remains at PROCESSED, no
            # status advance — safe to retry via process_document() again.
            raise DocumentProcessingError(
                document_id=document_id,
                reason=f"Failed to create import draft: {exc}",
            ) from exc

        try:
            self._document_repo.update_processing_status(
                document_id, DocumentStatus.PENDING_REVIEW
            )
        except (ValueError, RuntimeError) as exc:
            raise DocumentProcessingError(
                document_id=document_id,
                reason=(
                    f"Import draft '{draft_id}' created but failed to "
                    f"advance document status to PENDING_REVIEW: {exc}"
                ),
            ) from exc

        logger.info(
            "Import draft '%s' created for document '%s'.", draft_id, document_id
        )
        return {
            "document_id": document_id,
            "status": DocumentStatus.PENDING_REVIEW.value,
            "draft_id": draft_id,
            "message": "Import draft created; pending review.",
        }

    # ==================================================================
    # PRIVATE HELPERS
    # ==================================================================

    def _get_document_or_raise(self, document_id: str) -> dict:
        try:
            return self._document_repo.get_document(document_id)
        except (ValueError, RuntimeError) as exc:
            raise DocumentProcessingError(
                document_id=document_id,
                reason=f"Failed to retrieve document: {exc}",
            ) from exc

    def _find_existing_draft(self, document_id: str) -> Optional[dict]:
        try:
            drafts = self._import_draft_repo.list_drafts(
                document_id=document_id
            )
        except (ValueError, RuntimeError) as exc:
            raise DocumentProcessingError(
                document_id=document_id,
                reason=f"Failed to look up existing import draft: {exc}",
            ) from exc

        if not drafts:
            return None

        if len(drafts) > 1:
            raise DocumentProcessingError(
                document_id=document_id,
                reason=(
                    f"Integrity/idempotency violation: found {len(drafts)} "
                    f"import drafts for one document; expected at most one."
                ),
            )

        return drafts[0]

    def _mark_failed(self, document_id: str, error_message: str) -> None:
        try:
            self._document_repo.update_processing_status(
                document_id, DocumentStatus.FAILED, error_message=error_message
            )
        except (ValueError, RuntimeError) as exc:
            logger.error(
                "Failed to mark document '%s' as FAILED: %s", document_id, exc
            )
