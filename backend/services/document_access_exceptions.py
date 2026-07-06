"""
document_access_exceptions.py
==============================
M6.6 — Focused, domain-level exceptions for controlled document access.

DocumentContextService and DataLoader raise these instead of letting raw
PyMongo/DocumentStorageError exceptions reach agents or the executor, so
callers can distinguish access-policy failures (expected, user-facing)
from infrastructure failures (unexpected, logged as bugs/outages).

All exceptions carry `document_id` (or the offending list, for atomic
selection failures) so the caller can build a clear error message without
re-deriving context.
"""

from __future__ import annotations


class DocumentAccessError(Exception):
    """Base class for all M6.6 document-access errors."""


class DocumentNotFoundError(DocumentAccessError):
    """The document_id does not exist in the document repository."""

    def __init__(self, document_id: str) -> None:
        self.document_id = document_id
        super().__init__(f"Document '{document_id}' not found.")


class DocumentNotEligibleError(DocumentAccessError):
    """The document exists but is not in a lifecycle status valid for
    the access path being attempted (e.g. not PROCESSED / not IMPORTED)."""

    def __init__(self, document_id: str, status: str, expected: str) -> None:
        self.document_id = document_id
        self.status = status
        self.expected = expected
        super().__init__(
            f"Document '{document_id}' has status '{status}'; "
            f"expected '{expected}' for this access path."
        )


class DocumentTypeNotAllowedError(DocumentAccessError):
    """The document's type is not permitted for the requested workflow slot."""

    def __init__(self, document_id: str, document_type: str | None, workflow_slot: str) -> None:
        self.document_id = document_id
        self.document_type = document_type
        self.workflow_slot = workflow_slot
        super().__init__(
            f"Document '{document_id}' has type '{document_type}', which is "
            f"not eligible for workflow slot '{workflow_slot}'."
        )


class DocumentNotSelectedError(DocumentAccessError):
    """The document_id is not present in the current workflow's
    AgentState.document_ids — it was never resolved/selected for this
    workflow, so no content access is permitted even if the document
    itself exists and is otherwise eligible."""

    def __init__(self, document_id: str, workflow_id: str) -> None:
        self.document_id = document_id
        self.workflow_id = workflow_id
        super().__init__(
            f"Document '{document_id}' is not selected for workflow "
            f"'{workflow_id}'. Access denied."
        )


class ExtractedTextUnavailableError(DocumentAccessError):
    """The document is selected/eligible but has no extracted text."""

    def __init__(self, document_id: str) -> None:
        self.document_id = document_id
        super().__init__(f"No extracted text available for document '{document_id}'.")


class OriginalFileUnavailableError(DocumentAccessError):
    """The document is selected/eligible but the original file could not
    be retrieved from storage."""

    def __init__(self, document_id: str, reason: str) -> None:
        self.document_id = document_id
        self.reason = reason
        super().__init__(
            f"Original file unavailable for document '{document_id}': {reason}"
        )
