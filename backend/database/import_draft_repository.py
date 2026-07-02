"""
import_draft_repository.py
===========================
ImportDraftRepository — MongoDB persistence for import drafts in the
Document Upload & AI Document Ingestion subsystem.

This is the ONLY module that reads from or writes to the
'import_drafts' collection. No other module constructs queries or
touches pymongo directly for draft persistence.

Layering contract
-----------------
    BusinessImportService / review routes (later milestones)
        →  ImportDraftRepository  →  MongoDB

The repository speaks exclusively in plain dicts. It has no knowledge
of HTTP, FastAPI, extraction logic, or business-entity import. It
performs CRUD (plus the minimal review-status transition guard
described below) only — it never writes to business collections.

MongoDB document schema
------------------------
    {
        "_id":                  draft_id,            # str — Mongo primary key
        "document_id":          str,                  # originating document
        "source_document_ids":  list[str],            # documents contributing
                                                        # to this draft; defaults
                                                        # to [document_id]
        "business_domain":      str,                  # BusinessDomain value
        "target_business_entity": str,
        "extracted_data":       dict,
        "confidence":           float | None,          # carried over from the
                                                        # originating ProcessingResult
        "status":               str,                   # DocumentStatus value
        "reviewed_by":          str | None,
        "review_notes":         str | None,
        "created_at":           datetime,               # UTC; written once on insert
        "updated_at":           datetime,               # UTC; overwritten on every mutation
    }

This mirrors document_processing.document_models.ImportDraft
field-for-field. Repositories store plain dicts, not enforced Pydantic
instances, so this is a storage-layer extension, not a redefinition of
the ImportDraft contract.

Recommended indexes (run once during provisioning)
---------------------------------------------------
    db.import_drafts.create_index("status")
    db.import_drafts.create_index("source_document_ids")
    db.import_drafts.create_index("document_id")
    db.import_drafts.create_index("created_at")
    # _id (== draft_id) is automatically indexed by MongoDB.

Dependency injection
--------------------
ImportDraftRepository accepts an optional Collection at construction
time. Pass a mongomock collection in tests to avoid hitting a real
database:

    from mongomock import MongoClient as MockClient
    col = MockClient()["test"]["import_drafts"]
    repo = ImportDraftRepository(collection=col)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from backend.database.mongo import get_import_drafts_collection
from backend.document_processing.document_models import BusinessDomain, DocumentStatus

logger = logging.getLogger(__name__)


class ImportDraftRepository:
    """
    All MongoDB CRUD operations for import drafts.

    Methods
    -------
    create_import_draft(data)                              → dict
    get_import_draft(draft_id)                              → dict
    update_import_draft(draft_id, updates)                   → dict
    approve_import_draft(draft_id, reviewed_by, ...)          → dict
    reject_import_draft(draft_id, reviewed_by, ...)           → dict
    list_pending_drafts()                                     → list[dict]
    list_drafts(...)                                          → list[dict]
    delete_import_draft(draft_id)                              → None

    Stateless beyond the lazily-resolved Collection handle: every
    method depends only on its arguments and the collection.
    """

    def __init__(self, collection: Optional[Collection] = None) -> None:
        """
        Args:
            collection: Optional pymongo Collection. If omitted, resolved
                        lazily on first access via get_import_drafts_collection().
                        Pass an explicit collection in unit tests.
        """
        self._collection: Optional[Collection] = collection

    @property
    def collection(self) -> Collection:
        """Resolve and cache the collection on first access."""
        if self._collection is None:
            self._collection = get_import_drafts_collection()
        return self._collection

    # ==================================================================
    # PRIVATE HELPERS
    # ==================================================================

    @staticmethod
    def _fmt(value: datetime | None) -> str | None:
        """Format a datetime as 'YYYY-MM-DDTHH:MM:SSZ', or None through."""
        return value.strftime("%Y-%m-%dT%H:%M:%SZ") if value else None

    @classmethod
    def _serialize(cls, document: dict) -> dict:
        """
        Convert a raw Mongo document into the public dict shape.

        Replaces '_id' with 'draft_id' and formats timestamp fields as
        ISO 8601 strings.
        """
        result = {k: v for k, v in document.items() if k != "_id"}
        result["draft_id"] = document["_id"]
        result["created_at"] = cls._fmt(document.get("created_at"))
        result["updated_at"] = cls._fmt(document.get("updated_at"))
        return result

    @staticmethod
    def _as_value(value: Any) -> Any:
        """Return .value if `value` is an Enum member, else pass through."""
        return value.value if hasattr(value, "value") else value

    # ==================================================================
    # CREATE / READ
    # ==================================================================

    def create_import_draft(self, data: dict) -> dict:
        """
        Insert a new import draft.

        Required keys in `data`:
            draft_id                (str)
            document_id             (str)
            business_domain         (BusinessDomain | str)
            target_business_entity  (str)
            extracted_data          (dict)

        Optional keys in `data`:
            confidence           (float | None)          — default None
            source_document_ids  (list[str])              — default [document_id]
            status               (DocumentStatus | str)    — default PENDING_REVIEW

        Args:
            data: Dict describing the draft to create.

        Returns:
            The inserted draft as a public dict.

        Raises:
            ValueError:   If a draft with the same draft_id exists, or
                          a required key is missing.
            RuntimeError: On any PyMongo failure.
        """
        draft_id: str = data["draft_id"]
        document_id: str = data["document_id"]

        try:
            existing = self.collection.find_one({"_id": draft_id})
        except PyMongoError as exc:
            logger.error(
                "create_import_draft pre-check failed for '%s': %s",
                draft_id,
                exc,
            )
            raise RuntimeError(
                f"Failed to create import draft '{draft_id}': {exc}"
            ) from exc

        if existing is not None:
            raise ValueError(f"Import draft '{draft_id}' already exists")

        now = datetime.now(timezone.utc)
        status = self._as_value(data.get("status", DocumentStatus.PENDING_REVIEW))
        business_domain = self._as_value(data["business_domain"])

        document = {
            "_id": draft_id,
            "document_id": document_id,
            "source_document_ids": data.get("source_document_ids") or [document_id],
            "business_domain": business_domain,
            "target_business_entity": data["target_business_entity"],
            "extracted_data": data["extracted_data"],
            "confidence": data.get("confidence"),
            "status": status,
            "reviewed_by": None,
            "review_notes": None,
            "created_at": now,
            "updated_at": now,
        }

        try:
            self.collection.insert_one(document)
        except PyMongoError as exc:
            logger.error(
                "create_import_draft insert failed for '%s': %s",
                draft_id,
                exc,
            )
            raise RuntimeError(
                f"Failed to create import draft '{draft_id}': {exc}"
            ) from exc

        logger.debug(
            "Import draft '%s' created for document '%s'.",
            draft_id,
            document_id,
        )
        return self._serialize(document)

    def get_import_draft(self, draft_id: str) -> dict:
        """
        Return a single import draft by draft_id.

        Args:
            draft_id: Identifier of the draft to retrieve.

        Returns:
            Draft dict.

        Raises:
            ValueError:   If no draft with that id exists.
            RuntimeError: On any PyMongo failure.
        """
        try:
            doc = self.collection.find_one({"_id": draft_id})
        except PyMongoError as exc:
            logger.error("get_import_draft('%s') failed: %s", draft_id, exc)
            raise RuntimeError(
                f"Failed to retrieve import draft '{draft_id}': {exc}"
            ) from exc

        if doc is None:
            raise ValueError(f"Import draft '{draft_id}' not found")

        return self._serialize(doc)

    # ==================================================================
    # UPDATE
    # ==================================================================

    def update_import_draft(self, draft_id: str, updates: dict) -> dict:
        """
        Apply partial updates to a draft via $set.

        Generic pass-through, mirroring BusinessDataRepository.update_employee:
        only keys present in `updates` are written (e.g. corrected
        extracted_data, confidence, source_document_ids). For approval /
        rejection, prefer approve_import_draft() / reject_import_draft(),
        which also enforce the pending-review precondition.

        Args:
            draft_id: Identifier of the draft to update.
            updates:  Dict of field-value pairs to apply.

        Returns:
            The full updated draft dict.

        Raises:
            ValueError:   If no draft with that id exists.
            RuntimeError: On any PyMongo failure.
        """
        self.get_import_draft(draft_id)  # raises ValueError if missing

        if not updates:
            return self.get_import_draft(draft_id)

        try:
            self.collection.update_one(
                {"_id": draft_id},
                {
                    "$set": {
                        **updates,
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )
        except PyMongoError as exc:
            logger.error("update_import_draft('%s') failed: %s", draft_id, exc)
            raise RuntimeError(
                f"Failed to update import draft '{draft_id}': {exc}"
            ) from exc

        logger.debug(
            "Import draft '%s' updated — fields: %s",
            draft_id,
            list(updates),
        )
        return self.get_import_draft(draft_id)

    def _set_review_decision(
        self,
        draft_id: str,
        new_status: DocumentStatus,
        reviewed_by: str,
        review_notes: Optional[str],
    ) -> dict:
        """
        Shared implementation for approve_import_draft() / reject_import_draft().

        Enforces that a decision can only be recorded against a draft
        that is currently PENDING_REVIEW — this is a minimal status-
        transition guard, not review or import business logic, and
        mirrors the equivalent precondition check already used in
        BusinessDataRepository.review_goal_update().
        """
        draft = self.get_import_draft(draft_id)

        if draft["status"] != DocumentStatus.PENDING_REVIEW.value:
            raise ValueError(
                f"Import draft '{draft_id}' is not pending review "
                f"(current status: '{draft['status']}')"
            )

        try:
            self.collection.update_one(
                {"_id": draft_id},
                {
                    "$set": {
                        "status": new_status.value,
                        "reviewed_by": reviewed_by,
                        "review_notes": review_notes,
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )
        except PyMongoError as exc:
            logger.error(
                "review decision failed for draft '%s': %s",
                draft_id,
                exc,
            )
            raise RuntimeError(
                f"Failed to record review decision for import draft "
                f"'{draft_id}': {exc}"
            ) from exc

        logger.debug(
            "Import draft '%s' set to '%s' by '%s'.",
            draft_id,
            new_status.value,
            reviewed_by,
        )
        return self.get_import_draft(draft_id)

    def approve_import_draft(
        self,
        draft_id: str,
        reviewed_by: str,
        review_notes: Optional[str] = None,
    ) -> dict:
        """
        Mark a pending draft as APPROVED.

        Args:
            draft_id:     Identifier of the draft to approve.
            reviewed_by:  Identifier of the reviewer.
            review_notes: Optional free-text notes from the reviewer.

        Returns:
            The full updated draft dict.

        Raises:
            ValueError:   If the draft does not exist or is not
                          currently PENDING_REVIEW.
            RuntimeError: On any PyMongo failure.
        """
        return self._set_review_decision(
            draft_id, DocumentStatus.APPROVED, reviewed_by, review_notes
        )

    def reject_import_draft(
        self,
        draft_id: str,
        reviewed_by: str,
        review_notes: Optional[str] = None,
    ) -> dict:
        """
        Mark a pending draft as REJECTED.

        Args:
            draft_id:     Identifier of the draft to reject.
            reviewed_by:  Identifier of the reviewer.
            review_notes: Optional free-text notes from the reviewer.

        Returns:
            The full updated draft dict.

        Raises:
            ValueError:   If the draft does not exist or is not
                          currently PENDING_REVIEW.
            RuntimeError: On any PyMongo failure.
        """
        return self._set_review_decision(
            draft_id, DocumentStatus.REJECTED, reviewed_by, review_notes
        )

    # ==================================================================
    # LIST
    # ==================================================================

    def list_pending_drafts(self) -> list[dict]:
        """
        Return all drafts currently awaiting review, oldest first.

        Returns:
            List of draft dicts with status == PENDING_REVIEW.

        Raises:
            RuntimeError: On any PyMongo failure.
        """
        return self.list_drafts(status=DocumentStatus.PENDING_REVIEW)

    def list_drafts(
        self,
        *,
        status: Optional[DocumentStatus] = None,
        document_id: Optional[str] = None,
        source_document_id: Optional[str] = None,
        limit: Optional[int] = None,
        skip: int = 0,
    ) -> list[dict]:
        """
        Return drafts matching all supplied filters, oldest first.

        Every filter is optional and combined with AND semantics.

        Args:
            status:              Exact match on draft status.
            document_id:         Exact match on the originating document_id.
            source_document_id:  Match drafts whose source_document_ids
                                 contains this id.
            limit:               Optional maximum number of results.
            skip:                Number of results to skip (pagination).

        Returns:
            List of matching draft dicts.

        Raises:
            RuntimeError: On any PyMongo failure.
        """
        query: dict[str, Any] = {}

        if status is not None:
            query["status"] = status.value
        if document_id is not None:
            query["document_id"] = document_id
        if source_document_id is not None:
            query["source_document_ids"] = source_document_id

        try:
            cursor = self.collection.find(
                query,
                sort=[("created_at", 1)],
                skip=skip,
            )
            if limit is not None:
                cursor = cursor.limit(limit)
            return [self._serialize(doc) for doc in cursor]
        except PyMongoError as exc:
            logger.error("list_drafts failed: %s", exc)
            raise RuntimeError(f"Failed to list import drafts: {exc}") from exc

    # ==================================================================
    # DELETE
    # ==================================================================

    def delete_import_draft(self, draft_id: str) -> None:
        """
        Delete a draft by draft_id.

        Args:
            draft_id: Identifier of the draft to delete.

        Raises:
            ValueError:   If no draft with that id exists.
            RuntimeError: On any PyMongo failure.
        """
        self.get_import_draft(draft_id)  # raises ValueError if missing

        try:
            self.collection.delete_one({"_id": draft_id})
        except PyMongoError as exc:
            logger.error("delete_import_draft('%s') failed: %s", draft_id, exc)
            raise RuntimeError(
                f"Failed to delete import draft '{draft_id}': {exc}"
            ) from exc

        logger.debug("Import draft '%s' deleted.", draft_id)
