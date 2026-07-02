"""
document_service.py
====================
DocumentService — orchestration layer for the Document Upload & AI
Document Ingestion subsystem.

DocumentService answers exactly one question: "given a newly uploaded
file, what sequence of calls to DocumentStorage, DocumentRepository,
and DocumentClassifier turns it into a classified, persisted
document?" It owns coordination only — it never performs storage,
persistence, or classification itself; it calls the components that do.

Pipeline (Milestone 4 scope)
------------------------------
    Upload
        -> DocumentStorage.save_file()
        -> Create DocumentMetadata
        -> DocumentRepository.create_document()
        -> DocumentTextExtractor.extract_text()
        -> DocumentRepository.update_extracted_text()
        -> DocumentClassifier.classify()
        -> DocumentRepository.update_classification()
        -> Return document information


Explicitly NOT this module's responsibility
--------------------------------------------
- Running domain processors / extraction (BaseProcessor subclasses).
- Creating a ProcessingResult.
- Creating an ImportDraft.
- Calling BusinessImportService.
- Updating business entities.
- API routes, request/response schemas, or FastAPI concerns.
- Performing text extraction itself; orchestration is delegated to
  DocumentTextExtractor.

Failure handling
------------------
If persistence fails after a file has already been physically stored,
the stored file is deleted as a best-effort compensating action so
uploads never leave orphaned files behind. If classification fails
after the document record was created, the document's status is
updated to FAILED (with the failure reason recorded) rather than left
UPLOADED, so it is visible to whatever review tooling later milestones
add. Every failure is surfaced to the caller as a DocumentServiceError.

Dependency injection
--------------------
DocumentService accepts its four collaborators at construction time,
each defaulting to the standard concrete implementation if omitted —
mirroring the optional-collection injection pattern already used by
the repositories:

    service = DocumentService()                      # production defaults
    service = DocumentService(storage=fake_storage,   # unit tests
                               repository=fake_repo,
                               classifier=fake_classifier)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional
from pathlib import Path

from backend.database.document_repository import DocumentRepository
from backend.document_processing.document_classifier import (
    ClassificationError,
    DocumentClassifier,
)
from backend.document_processing.document_models import (
    DocumentMetadata,
    DocumentStatus,
)
from backend.services.document_storage import (
    DocumentStorage,
    DocumentStorageError,
    LocalDocumentStorage,
)
from backend.services.document_text_extractor import (
    DocumentTextExtractor,
    DocumentTextExtractorError,
)

logger = logging.getLogger(__name__)


# ==========================================================
# STANDARDIZED SERVICE EXCEPTION
# ==========================================================

class DocumentServiceError(Exception):
    """
    Raised when the upload orchestration pipeline fails at any step.

    Carries document_id (when one has been assigned) and a human-
    readable reason so the failure can be logged and diagnosed, and so
    a future API layer can map it to a clear HTTP error, without
    inspecting a raw traceback or the originating component's
    exception type.
    """

    def __init__(self, document_id: Optional[str], reason: str) -> None:
        self.document_id = document_id
        self.reason = reason

        label = document_id or "(unassigned)"
        super().__init__(f"Document service failed for '{label}': {reason}")


# ==========================================================
# DOCUMENT SERVICE
# ==========================================================

class DocumentService:
    """
    Orchestrates the document upload pipeline: physical storage,
    Mongo persistence, and classification.

    Stateless beyond its four collaborators:  every method depends
    only on its arguments and the injected storage, repository,
    classifier, and text extractor instances.
    """

    def __init__(
        self,
        storage: Optional[DocumentStorage] = None,
        repository: Optional[DocumentRepository] = None,
        classifier: Optional[DocumentClassifier] = None,
        text_extractor: Optional[DocumentTextExtractor] = None,
    ) -> None:
        """
        Args:
            storage:     DocumentStorage implementation. Defaults to
                         LocalDocumentStorage() — the only concrete
                         backend that exists today. Depending on the
                         DocumentStorage interface (not
                         LocalDocumentStorage specifically) is what
                         lets a future S3/Blob/GCS backend be injected
                         here with no other code changing.
            repository:  DocumentRepository instance. Defaults to a
                         new DocumentRepository() (lazy Mongo
                         collection resolution, per its own docstring).
            classifier:  DocumentClassifier instance. Defaults to a new
                         DocumentClassifier() (stateless, per its own
                         docstring).
            text_extractor: DocumentTextExtractor instance.
                            Defaults to a new DocumentTextExtractor().

        """
        self._storage: DocumentStorage = storage or LocalDocumentStorage()
        self._repository: DocumentRepository = repository or DocumentRepository()
        self._classifier: DocumentClassifier = classifier or DocumentClassifier()
        self._text_extractor: DocumentTextExtractor = (
            text_extractor or DocumentTextExtractor()
        )

    # ==================================================================
    # UPLOAD PIPELINE
    # ==================================================================

    def upload_document(
        self,
        *,
        content: bytes,
        original_filename: str,
        content_type: str,
        uploaded_by: str,
    ) -> dict:
        """
        Run the full upload -> persist -> classify pipeline for one file.

        Args:
            content:            Raw uploaded file bytes.
            original_filename:  Filename as uploaded.
            content_type:       MIME type as uploaded (e.g. "application/pdf").
            uploaded_by:        Identifier of the uploading user.

            Text extraction is performed internally using the configured
            DocumentTextExtractor after the file has been stored.

        Returns:
            The persisted document dict (as returned by
            DocumentRepository), including its stored classification.

        Raises:
            DocumentServiceError: If any pipeline step fails. The
                                   underlying storage / repository /
                                   classifier exception is chained via
                                   `__cause__`.
        """
        # ------------------------------------------------------------
        # Step 1 — physical storage
        # ------------------------------------------------------------
        try:
            storage_meta = self._storage.save_file(content, original_filename)
        except DocumentStorageError as exc:
            raise DocumentServiceError(
                document_id=None,
                reason=f"Failed to store uploaded file: {exc}",
            ) from exc

        document_id = storage_meta.document_id

        # ------------------------------------------------------------
        # Step 2 — build DocumentMetadata
        # ------------------------------------------------------------
        metadata = DocumentMetadata(
            document_id=document_id,
            original_filename=original_filename,
            content_type=content_type,
            size_bytes=storage_meta.size_bytes,
            uploaded_by=uploaded_by,
            uploaded_at=datetime.now(timezone.utc).isoformat(),
            status=DocumentStatus.UPLOADED,
        )

        # ------------------------------------------------------------
        # Step 3 — persist document record
        # ------------------------------------------------------------
        try:
            self._repository.create_document(metadata)
        except (ValueError, RuntimeError) as exc:
            self._compensate_stored_file(document_id)
            raise DocumentServiceError(
                document_id=document_id,
                reason=f"Failed to persist document metadata: {exc}",
            ) from exc

        # ------------------------------------------------------------
        # Step 4 — extract text
        # ------------------------------------------------------------

        try:
            text = self._text_extractor.extract_text(
                Path(storage_meta.storage_path),
                content_type,
            )
        except DocumentTextExtractorError as exc:
            self._mark_failed(document_id, str(exc))
            raise DocumentServiceError(
                document_id=document_id,
                reason=f"Text extraction failed: {exc}",
            ) from exc

        try:
            self._repository.update_extracted_text(
                document_id,
                text,
            )
        except (ValueError, RuntimeError) as exc:
            self._mark_failed(document_id, str(exc))
            raise DocumentServiceError(
                document_id=document_id,
                reason=f"Failed to persist extracted text: {exc}",
            ) from exc

        # ------------------------------------------------------------
        # Step 5 — classify
        # ------------------------------------------------------------
        try:
            classification = self._classifier.classify(
                text,
                metadata,
            )
        except ClassificationError as exc:
            self._mark_failed(document_id, str(exc))
            raise DocumentServiceError(
                document_id=document_id,
                reason=f"Classification failed: {exc}",
            ) from exc

        # ------------------------------------------------------------
        # Step 6 — persist classification result
        # ------------------------------------------------------------
        try:
            self._repository.update_classification(document_id, classification)
        except (ValueError, RuntimeError) as exc:
            self._mark_failed(document_id, f"Failed to persist classification: {exc}")
            raise DocumentServiceError(
                document_id=document_id,
                reason=f"Failed to persist classification: {exc}",
            ) from exc

        # ------------------------------------------------------------
        # Step 7 — advance lifecycle status to CLASSIFIED
        # ------------------------------------------------------------
        try:
            document = self._repository.update_processing_status(
                document_id, DocumentStatus.CLASSIFIED
            )
        except (ValueError, RuntimeError) as exc:
            raise DocumentServiceError(
                document_id=document_id,
                reason=f"Failed to update processing status: {exc}",
            ) from exc

        logger.info(
            "Document '%s' uploaded and classified as '%s'.",
            document_id,
            classification.document_type,
        )
        return document

    # ==================================================================
    # SUPPORTING READS / LIFECYCLE
    # ==================================================================
    # Minimal, direct coordination of the same two collaborators used
    # by the upload pipeline — no classification or processing
    # involved. Kept here because "get a document's info" / "get its
    # bytes back" / "remove it entirely" are natural counterparts to
    # "upload a document," not a new area of responsibility.

    def get_document(self, document_id: str) -> dict:
        """
        Return a document's persisted record.

        Args:
            document_id: Identifier of the document to retrieve.

        Returns:
            The document dict, as returned by DocumentRepository.

        Raises:
            DocumentServiceError: If no document with that id exists,
                                   or the lookup fails.
        """
        try:
            return self._repository.get_document(document_id)
        except (ValueError, RuntimeError) as exc:
            raise DocumentServiceError(
                document_id=document_id,
                reason=f"Failed to retrieve document: {exc}",
            ) from exc

    def download_document(self, document_id: str) -> tuple[bytes, dict]:
        """
        Return a document's raw file bytes together with its record.

        Args:
            document_id: Identifier of the document to download.

        Returns:
            A (content, document) tuple: the stored file bytes and the
            persisted document dict.

        Raises:
            DocumentServiceError: If the document record or the
                                   physical file cannot be found.
        """
        document = self.get_document(document_id)  # raises DocumentServiceError

        try:
            content = self._storage.get_file(document_id)
        except DocumentStorageError as exc:
            raise DocumentServiceError(
                document_id=document_id,
                reason=f"Failed to read stored file: {exc}",
            ) from exc

        return content, document

    def delete_document(self, document_id: str) -> None:
        """
        Delete both the physical file and the persisted record for a
        document.

        The Mongo record is deleted first so the document disappears
        from listings immediately; the physical file is then removed
        as a best-effort follow-up (logged, not raised, if it is
        already missing — deletion is idempotent from the caller's
        point of view).

        Args:
            document_id: Identifier of the document to delete.

        Raises:
            DocumentServiceError: If the document record does not
                                   exist, or the Mongo delete fails.
        """
        try:
            self._repository.delete_document(document_id)
        except (ValueError, RuntimeError) as exc:
            raise DocumentServiceError(
                document_id=document_id,
                reason=f"Failed to delete document record: {exc}",
            ) from exc

        self._compensate_stored_file(document_id)
        logger.info("Document '%s' deleted.", document_id)

    # ==================================================================
    # PRIVATE HELPERS
    # ==================================================================



    def _mark_failed(self, document_id: str, error_message: str) -> None:
        """
        Best-effort transition of a document to FAILED status.

        Used when a later pipeline step fails after the document
        record already exists, so the failure is visible on the
        document itself rather than only in logs. Failures here are
        logged, not raised — the caller already has a more specific
        DocumentServiceError to raise for the original failure.
        """
        try:
            self._repository.update_processing_status(
                document_id, DocumentStatus.FAILED, error_message=error_message
            )
        except (ValueError, RuntimeError) as exc:
            logger.error(
                "Failed to mark document '%s' as FAILED after a pipeline "
                "error: %s",
                document_id,
                exc,
            )

    def _compensate_stored_file(self, document_id: str) -> None:
        """
        Best-effort deletion of a physically stored file.

        Used to avoid orphaned files when a later pipeline step fails,
        and when a document is deleted outright. Failures here are
        logged, not raised, since the file may already be absent or
        the caller already has a more specific error to raise.
        """
        try:
            if self._storage.file_exists(document_id):
                self._storage.delete_file(document_id)
        except DocumentStorageError as exc:
            logger.error(
                "Failed to clean up stored file for document '%s': %s",
                document_id,
                exc,
            )
