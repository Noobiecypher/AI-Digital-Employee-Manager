"""
document_storage.py
====================
Physical file storage for the Document Upload & AI Document Ingestion
subsystem.

DocumentStorage answers exactly one question: "where do the raw bytes
of an uploaded file live, and how do I save / read / delete them?" It
owns physical storage only — it never touches MongoDB, never runs
classification or extraction, and never knows about FastAPI, routes,
or DocumentMetadata.

Responsibilities
-----------------
- Generate a unique document_id for each newly saved file.
- Save uploaded file bytes to durable storage.
- Retrieve stored file bytes by document_id.
- Delete stored files by document_id.
- Report whether a file exists for a given document_id.
- Return storage metadata (StorageMetadata) describing what was stored.

Explicitly NOT this module's responsibility
--------------------------------------------
- MongoDB persistence (document_repository.py).
- Classification (document_classifier.py) or extraction (processors).
- Business entity import.
- Orchestrating the upload pipeline (document_service.py).

Swappable backend, stable interface
-------------------------------------
DocumentStorage is an abstract interface. LocalDocumentStorage is the
MVP implementation, writing files to a local directory (default
"uploads/"). A future S3DocumentStorage / AzureBlobDocumentStorage /
GCSDocumentStorage can implement the same four abstract methods
(save_file, get_file, delete_file, file_exists) and be swapped in via
constructor injection — DocumentService (and everything above it)
depends only on the DocumentStorage interface, never on
LocalDocumentStorage directly, so no other component needs to change
when the backend changes.

Storage key convention
------------------------
Files are stored under a single flat directory, keyed purely by
document_id (no file extension, no nested per-document directories):

    uploads/<document_id>

This mirrors how object storage backends address objects (an opaque
key, not a filesystem path), which is exactly what keeps the future
migration to S3 / Blob / GCS a drop-in: document_id becomes the S3
object key / blob name unchanged. original_filename and content_type
are NOT needed to locate a stored file — they are tracked separately
in DocumentMetadata (document_repository.py), not by this module.

Agents never call DocumentStorage directly
---------------------------------------------
Per the frozen architecture, agents access documents only through the
future DataLoader abstraction. DocumentStorage is consumed exclusively
by DocumentService.
"""

from __future__ import annotations

import logging
import os
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_DEFAULT_STORAGE_DIR = "uploads"


# ==========================================================
# STANDARDIZED STORAGE EXCEPTION
# ==========================================================

class DocumentStorageError(Exception):
    """
    Raised when a physical storage operation fails — e.g. the file is
    missing on read/delete, or an OS-level error occurs on write.

    Carries document_id and a human-readable reason so the failure can
    be logged and diagnosed without a raw traceback.
    """

    def __init__(self, document_id: str, reason: str) -> None:
        self.document_id = document_id
        self.reason = reason

        super().__init__(
            f"Storage operation failed for document '{document_id}': {reason}"
        )


# ==========================================================
# STORAGE METADATA
# ==========================================================

@dataclass(frozen=True)
class StorageMetadata:
    """
    Describes a file as it was physically stored.

    This is a storage-layer value object, distinct from
    document_processing.document_models.DocumentMetadata (the Mongo-
    facing model). DocumentService is responsible for combining the
    two — StorageMetadata never crosses into document_repository.py.
    """

    document_id: str
    storage_path: str
    original_filename: str
    size_bytes: int
    stored_at: str  # ISO 8601 UTC timestamp


# ==========================================================
# ABSTRACT INTERFACE
# ==========================================================

class DocumentStorage(ABC):
    """
    Abstract interface for physical document storage backends.

    Every concrete backend (LocalDocumentStorage today; S3 / Azure
    Blob / GCS later) implements exactly these four methods. Callers
    — DocumentService in particular — should depend on this type, not
    on any concrete subclass, so the storage backend can be swapped
    without touching orchestration code.
    """

    @abstractmethod
    def save_file(
        self,
        content: bytes,
        original_filename: str,
        document_id: Optional[str] = None,
    ) -> StorageMetadata:
        """
        Persist file bytes to storage, generating a document_id if one
        is not supplied.

        Args:
            content:           Raw file bytes to store.
            original_filename: The filename as uploaded, kept only for
                                StorageMetadata / caller bookkeeping —
                                not used to address the stored file.
            document_id:       Optional caller-supplied id. If omitted,
                                a new unique id is generated.

        Returns:
            StorageMetadata describing what was stored.

        Raises:
            DocumentStorageError: If the file cannot be written.
        """
        ...

    @abstractmethod
    def get_file(self, document_id: str) -> bytes:
        """
        Retrieve stored file bytes by document_id.

        Raises:
            DocumentStorageError: If no file exists for document_id,
                                   or it cannot be read.
        """
        ...

    @abstractmethod
    def delete_file(self, document_id: str) -> None:
        """
        Delete the stored file for document_id.

        Raises:
            DocumentStorageError: If no file exists for document_id,
                                   or it cannot be deleted.
        """
        ...

    @abstractmethod
    def file_exists(self, document_id: str) -> bool:
        """Return True if a stored file exists for document_id."""
        ...


# ==========================================================
# LOCAL FILESYSTEM IMPLEMENTATION (MVP)
# ==========================================================

class LocalDocumentStorage(DocumentStorage):
    """
    MVP DocumentStorage backend: stores files on the local filesystem.

    Files live under `base_dir` (default "uploads/", or the
    DOCUMENT_STORAGE_DIR environment variable), one file per
    document_id with no extension — see the storage key convention in
    the module docstring.
    """

    def __init__(self, base_dir: Optional[str] = None) -> None:
        """
        Args:
            base_dir: Directory to store files under. Defaults to the
                      DOCUMENT_STORAGE_DIR environment variable, or
                      "uploads/" if that is unset. Created (including
                      parents) if it does not already exist.
        """
        resolved = base_dir or os.getenv("DOCUMENT_STORAGE_DIR", _DEFAULT_STORAGE_DIR)
        self._base_dir = Path(resolved)
        self._base_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------
    # PRIVATE HELPERS
    # ------------------------------------------------------------

    @staticmethod
    def _validate_document_id(document_id: str) -> None:
        """
        Guard against path traversal / malformed ids being used to
        build a filesystem path.

        Raises:
            ValueError: If document_id is empty or contains path
                        separators or parent-directory references.
        """
        if not document_id or not document_id.strip():
            raise ValueError("document_id must not be empty")

        if any(token in document_id for token in ("/", "\\", "..")):
            raise ValueError(
                f"document_id '{document_id}' contains disallowed "
                f"path characters"
            )

    def _path_for(self, document_id: str) -> Path:
        self._validate_document_id(document_id)
        return self._base_dir / document_id

    @staticmethod
    def _generate_document_id() -> str:
        """Generate a unique document_id, mirroring the 'wf_<uuid4>' style
        already used for workflow_id in workflow_repository.py."""
        return f"doc_{uuid.uuid4()}"

    # ------------------------------------------------------------
    # PUBLIC INTERFACE
    # ------------------------------------------------------------

    def save_file(
        self,
        content: bytes,
        original_filename: str,
        document_id: Optional[str] = None,
    ) -> StorageMetadata:
        """
        Write `content` to disk under a document_id-keyed path.

        Args:
            content:           Raw file bytes to store.
            original_filename: Filename as uploaded (bookkeeping only).
            document_id:       Optional caller-supplied id; generated
                                if omitted.

        Returns:
            StorageMetadata describing the stored file.

        Raises:
            DocumentStorageError: If the file cannot be written, or a
                                   file already exists for document_id.
        """
        resolved_id = document_id or self._generate_document_id()
        path = self._path_for(resolved_id)

        if path.exists():
            raise DocumentStorageError(
                document_id=resolved_id,
                reason=f"A stored file already exists at '{path}'",
            )

        try:
            self._base_dir.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        except OSError as exc:
            raise DocumentStorageError(
                document_id=resolved_id,
                reason=f"Failed to write file: {exc}",
            ) from exc

        logger.debug(
            "Stored file for document '%s' (%d bytes) at '%s'.",
            resolved_id,
            len(content),
            path,
        )

        return StorageMetadata(
            document_id=resolved_id,
            storage_path=str(path),
            original_filename=original_filename,
            size_bytes=len(content),
            stored_at=datetime.now(timezone.utc).isoformat(),
        )

    def get_file(self, document_id: str) -> bytes:
        """
        Read stored file bytes for document_id.

        Raises:
            DocumentStorageError: If no file exists for document_id,
                                   or it cannot be read.
        """
        path = self._path_for(document_id)

        if not path.is_file():
            raise DocumentStorageError(
                document_id=document_id,
                reason=f"No stored file found at '{path}'",
            )

        try:
            return path.read_bytes()
        except OSError as exc:
            raise DocumentStorageError(
                document_id=document_id,
                reason=f"Failed to read file: {exc}",
            ) from exc

    def delete_file(self, document_id: str) -> None:
        """
        Delete the stored file for document_id.

        Raises:
            DocumentStorageError: If no file exists for document_id,
                                   or it cannot be deleted.
        """
        path = self._path_for(document_id)

        if not path.is_file():
            raise DocumentStorageError(
                document_id=document_id,
                reason=f"No stored file found at '{path}'",
            )

        try:
            path.unlink()
        except OSError as exc:
            raise DocumentStorageError(
                document_id=document_id,
                reason=f"Failed to delete file: {exc}",
            ) from exc

        logger.debug("Deleted stored file for document '%s'.", document_id)

    def file_exists(self, document_id: str) -> bool:
        """Return True if a stored file exists for document_id."""
        return self._path_for(document_id).is_file()
