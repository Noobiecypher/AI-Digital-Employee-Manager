"""
document_repository.py
=======================
DocumentRepository — MongoDB persistence for uploaded documents in the
Document Upload & AI Document Ingestion subsystem.

This is the ONLY module that reads from or writes to the 'documents'
collection. No other module constructs queries or touches pymongo
directly for document persistence.

Layering contract
-----------------
    DocumentService (later milestone)  →  DocumentRepository  →  MongoDB

The repository speaks exclusively in plain dicts (and the typed
DocumentMetadata / ClassificationResult / ProcessingResult objects
defined in document_models.py, which it serialises on the way in).
It has no knowledge of HTTP, FastAPI, upload handling, classification
logic, extraction logic, or business-entity import. It performs CRUD
only.

MongoDB document schema
------------------------
    {
        "_id":                document_id,   # str — Mongo primary key
        "metadata":            dict,         # DocumentMetadata.model_dump(mode="json")
        "classification":      dict | None,  # ClassificationResult.model_dump(mode="json")
        "processing_result":   dict | None,  # ProcessingResult.model_dump(mode="json")
        "processing_history":  list[dict],   # [{"status", "timestamp", "message"}, ...]
        "workflow_id":         str | None,   # set once the document is attached to a workflow
        "tags":                list[str],
        "error_message":       str | None,   # populated when metadata.status == FAILED
        "created_at":          datetime,     # UTC; written once on insert
        "updated_at":          datetime,     # UTC; overwritten on every mutating call
    }

"owner" queries
----------------
DocumentMetadata has no separate "owner" concept distinct from the
uploader — search_documents() accepts an `owner` filter as an alias for
`uploaded_by` (metadata.uploaded_by) so callers can use either name.

Recommended indexes (run once during provisioning)
---------------------------------------------------
    db.documents.create_index("metadata.document_type")
    db.documents.create_index("metadata.status")
    db.documents.create_index("metadata.outcome")
    db.documents.create_index("workflow_id")
    db.documents.create_index("metadata.uploaded_by")
    db.documents.create_index("created_at")
    db.documents.create_index("tags")
    # _id (== document_id) is automatically indexed by MongoDB.

Dependency injection
--------------------
DocumentRepository accepts an optional Collection at construction time.
Pass a mongomock collection in tests to avoid hitting a real database:

    from mongomock import MongoClient as MockClient
    col = MockClient()["test"]["documents"]
    repo = DocumentRepository(collection=col)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from backend.database.mongo import get_documents_collection
from backend.document_processing.document_models import (
    BusinessDomain,
    ClassificationResult,
    DocumentMetadata,
    DocumentOutcome,
    DocumentStatus,
    ProcessingResult,
)

logger = logging.getLogger(__name__)


class DocumentRepository:
    """
    All MongoDB CRUD operations for uploaded documents.

    Methods
    -------
    create_document(metadata)                          → dict
    get_document(document_id)                           → dict
    update_document(document_id, updates)                → dict
    update_processing_status(document_id, status, ...)    → dict
    update_classification(document_id, classification)    → dict
    update_processing_result(document_id, result)         → dict
    list_documents(...)                                  → list[dict]
    search_documents(...)                                → list[dict]
    delete_document(document_id)                         → None

    Stateless beyond the lazily-resolved Collection handle: every
    method depends only on its arguments and the collection.
    """

    def __init__(self, collection: Optional[Collection] = None) -> None:
        """
        Args:
            collection: Optional pymongo Collection. If omitted, resolved
                        lazily on first access via get_documents_collection().
                        Pass an explicit collection in unit tests.
        """
        self._collection: Optional[Collection] = collection

    @property
    def collection(self) -> Collection:
        """Resolve and cache the collection on first access."""
        if self._collection is None:
            self._collection = get_documents_collection()
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

        Replaces '_id' with 'document_id' and formats timestamp fields
        as ISO 8601 strings, without altering the caller-facing meaning
        of any field.
        """
        result = {k: v for k, v in document.items() if k != "_id"}
        result["document_id"] = document["_id"]
        result["created_at"] = cls._fmt(document.get("created_at"))
        result["updated_at"] = cls._fmt(document.get("updated_at"))
        return result

    @staticmethod
    def _history_entry(status: str, message: str) -> dict:
        """Build one processing_history entry."""
        return {
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": message,
        }

    # ==================================================================
    # CREATE / READ
    # ==================================================================

    def create_document(self, metadata: DocumentMetadata) -> dict:
        """
        Insert a new document record.

        The document_id must already be set on `metadata` — generating
        it is upload-orchestration logic and belongs to the caller
        (DocumentService, a later milestone), not to this repository.

        Args:
            metadata: Fully populated DocumentMetadata describing the
                      uploaded file, as it exists immediately after
                      upload (document_type / business_domain / outcome /
                      target_business_entity are typically still unset
                      at this point).

        Returns:
            The inserted document as a public dict.

        Raises:
            ValueError:   If a document with the same document_id exists.
            RuntimeError: On any PyMongo failure.
        """
        document_id = metadata.document_id

        try:
            existing = self.collection.find_one({"_id": document_id})
        except PyMongoError as exc:
            logger.error(
                "create_document pre-check failed for '%s': %s",
                document_id,
                exc,
            )
            raise RuntimeError(
                f"Failed to create document '{document_id}': {exc}"
            ) from exc

        if existing is not None:
            raise ValueError(f"Document '{document_id}' already exists")

        now = datetime.now(timezone.utc)
        document = {
            "_id": document_id,
            "metadata": metadata.model_dump(mode="json"),
            "classification": None,
            "extracted_text": None,
            "processing_result": None,
            "processing_history": [
                self._history_entry(
                    metadata.status.value,
                    "Document uploaded.",
                )
            ],
            "workflow_id": None,
            "tags": [],
            "error_message": None,
            "created_at": now,
            "updated_at": now,
        }

        try:
            self.collection.insert_one(document)
        except PyMongoError as exc:
            logger.error(
                "create_document insert failed for '%s': %s",
                document_id,
                exc,
            )
            raise RuntimeError(
                f"Failed to create document '{document_id}': {exc}"
            ) from exc

        logger.debug("Document '%s' created.", document_id)
        return self._serialize(document)

    def get_document(self, document_id: str) -> dict:
        """
        Return a single document by document_id.

        Args:
            document_id: Identifier of the document to retrieve.

        Returns:
            Document dict.

        Raises:
            ValueError:   If no document with that id exists.
            RuntimeError: On any PyMongo failure.
        """
        try:
            doc = self.collection.find_one({"_id": document_id})
        except PyMongoError as exc:
            logger.error("get_document('%s') failed: %s", document_id, exc)
            raise RuntimeError(
                f"Failed to retrieve document '{document_id}': {exc}"
            ) from exc

        if doc is None:
            raise ValueError(f"Document '{document_id}' not found")

        return self._serialize(doc)

    # ==================================================================
    # UPDATE
    # ==================================================================

    def update_document(self, document_id: str, updates: dict) -> dict:
        """
        Apply partial updates to a document via $set.

        Generic pass-through, mirroring BusinessDataRepository.update_employee:
        only keys present in `updates` are written. Dotted paths (e.g.
        "metadata.uploaded_by", "tags") are supported since MongoDB's
        $set honours them directly. For the structured fields —
        classification, processing_result, processing_status/history —
        prefer the dedicated update_* methods below, which also append
        a processing_history entry; this method does not.

        Args:
            document_id: Identifier of the document to update.
            updates:     Dict of field-value pairs to apply.

        Returns:
            The full updated document dict.

        Raises:
            ValueError:   If no document with that id exists.
            RuntimeError: On any PyMongo failure.
        """
        self.get_document(document_id)  # raises ValueError if missing

        if not updates:
            return self.get_document(document_id)

        try:
            self.collection.update_one(
                {"_id": document_id},
                {
                    "$set": {
                        **updates,
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )
        except PyMongoError as exc:
            logger.error(
                "update_document('%s') failed: %s",
                document_id,
                exc,
            )
            raise RuntimeError(
                f"Failed to update document '{document_id}': {exc}"
            ) from exc

        logger.debug(
            "Document '%s' updated — fields: %s",
            document_id,
            list(updates),
        )
        return self.get_document(document_id)
    
    def update_extracted_text(
        self,
        document_id: str,
        extracted_text: str,
    ) -> dict:
        """
        Store the extracted plain-text representation of a document.

        The extracted text is derived from the original uploaded file
        (PDF/DOCX/TXT/etc.) and is intended for downstream AI
        classification, domain processors, search, and future agent
        access. This method persists only the extracted text; it performs
        no parsing or extraction itself.

        Args:
            document_id: Identifier of the document to update.
            extracted_text: Plain-text content extracted from the stored
                            document.

        Returns:
            The full updated document dict.

        Raises:
            ValueError:   If no document with that id exists.
            RuntimeError: On any PyMongo failure.
        """
        self.get_document(document_id)

        return self.update_document(
            document_id,
            {
                "extracted_text": extracted_text,
            },
        )
        

    def update_processing_status(
        self,
        document_id: str,
        status: DocumentStatus,
        error_message: Optional[str] = None,
    ) -> dict:
        """
        Update a document's lifecycle status and append a history entry.

        Args:
            document_id:   Identifier of the document to update.
            status:        New DocumentStatus value.
            error_message: Populated only when status == FAILED; cleared
                            (set to None) for any other status.

        Returns:
            The full updated document dict.

        Raises:
            ValueError:   If no document with that id exists.
            RuntimeError: On any PyMongo failure.
        """
        self.get_document(document_id)  # raises ValueError if missing

        message = error_message or f"Status changed to '{status.value}'."

        try:
            self.collection.update_one(
                {"_id": document_id},
                {
                    "$set": {
                        "metadata.status": status.value,
                        "error_message": error_message,
                        "updated_at": datetime.now(timezone.utc),
                    },
                    "$push": {
                        "processing_history": self._history_entry(
                            status.value, message
                        )
                    },
                },
            )
        except PyMongoError as exc:
            logger.error(
                "update_processing_status('%s') failed: %s",
                document_id,
                exc,
            )
            raise RuntimeError(
                f"Failed to update processing status for document "
                f"'{document_id}': {exc}"
            ) from exc

        logger.debug(
            "Document '%s' status changed to '%s'.",
            document_id,
            status.value,
        )
        return self.get_document(document_id)

    def update_classification(
        self,
        document_id: str,
        classification: ClassificationResult,
    ) -> dict:
        """
        Store a classification result against a document.

        Also syncs metadata.document_type / business_domain / outcome /
        target_business_entity from the classification result, since
        DocumentMetadata documents those fields as "populated once
        DocumentClassifier has run" — this is a direct data copy, not
        classification logic.

        Args:
            document_id:    Identifier of the document to update.
            classification: The ClassificationResult to store.

        Returns:
            The full updated document dict.

        Raises:
            ValueError:   If no document with that id exists.
            RuntimeError: On any PyMongo failure.
        """
        self.get_document(document_id)  # raises ValueError if missing

        try:
            self.collection.update_one(
                {"_id": document_id},
                {
                    "$set": {
                        "classification": classification.model_dump(mode="json"),
                        "metadata.document_type": classification.document_type,
                        "metadata.business_domain": classification.business_domain.value,
                        "metadata.outcome": classification.outcome.value,
                        "metadata.target_business_entity": (
                            classification.target_business_entity
                        ),
                        "updated_at": datetime.now(timezone.utc),
                    },
                    "$push": {
                        "processing_history": self._history_entry(
                            "classified",
                            f"Classified as document_type="
                            f"'{classification.document_type}' "
                            f"(confidence={classification.confidence:.2f}).",
                        )
                    },
                },
            )
        except PyMongoError as exc:
            logger.error(
                "update_classification('%s') failed: %s",
                document_id,
                exc,
            )
            raise RuntimeError(
                f"Failed to update classification for document "
                f"'{document_id}': {exc}"
            ) from exc

        logger.debug("Document '%s' classification stored.", document_id)
        return self.get_document(document_id)

    def update_processing_result(
        self,
        document_id: str,
        result: ProcessingResult,
    ) -> dict:
        """
        Store a processing (extraction) result against a document.

        Args:
            document_id: Identifier of the document to update.
            result:      The ProcessingResult to store.

        Returns:
            The full updated document dict.

        Raises:
            ValueError:   If no document with that id exists.
            RuntimeError: On any PyMongo failure.
        """
        self.get_document(document_id)  # raises ValueError if missing

        try:
            self.collection.update_one(
                {"_id": document_id},
                {
                    "$set": {
                        "processing_result": result.model_dump(mode="json"),
                        "updated_at": datetime.now(timezone.utc),
                    },
                    "$push": {
                        "processing_history": self._history_entry(
                            "processed",
                            f"Processed by '{result.processor_name}'.",
                        )
                    },
                },
            )
        except PyMongoError as exc:
            logger.error(
                "update_processing_result('%s') failed: %s",
                document_id,
                exc,
            )
            raise RuntimeError(
                f"Failed to update processing result for document "
                f"'{document_id}': {exc}"
            ) from exc

        logger.debug("Document '%s' processing result stored.", document_id)
        return self.get_document(document_id)

    # ==================================================================
    # LIST / SEARCH
    # ==================================================================

    def get_documents_by_ids(self, document_ids: list[str]) -> list[dict]:
        """
        Return documents matching any of the given document_ids.

        M6.6 addition — bulk read used by DocumentContextService to build
        lightweight contexts / revalidate several IDs in one round trip
        instead of N sequential get_document() calls. Missing IDs are
        silently omitted from the result (caller must check which IDs
        came back, e.g. via {d["document_id"] for d in results}).

        Args:
            document_ids: Document IDs to fetch. Empty list returns [].

        Returns:
            List of document dicts (public shape, same as get_document()),
            in no guaranteed order.

        Raises:
            RuntimeError: On any PyMongo failure.
        """
        if not document_ids:
            return []

        try:
            cursor = self.collection.find({"_id": {"$in": list(document_ids)}})
            return [self._serialize(doc) for doc in cursor]
        except PyMongoError as exc:
            logger.error("get_documents_by_ids failed: %s", exc)
            raise RuntimeError(f"Failed to fetch documents by ids: {exc}") from exc

    def list_documents(
        self,
        limit: Optional[int] = None,
        skip: int = 0,
    ) -> list[dict]:
        """
        Return all documents, sorted by created_at ascending.

        Args:
            limit: Optional maximum number of documents to return.
            skip:  Number of documents to skip (for pagination).

        Returns:
            List of document dicts.

        Raises:
            RuntimeError: On any PyMongo failure.
        """
        try:
            cursor = self.collection.find({}, sort=[("created_at", 1)], skip=skip)
            if limit is not None:
                cursor = cursor.limit(limit)
            return [self._serialize(doc) for doc in cursor]
        except PyMongoError as exc:
            logger.error("list_documents failed: %s", exc)
            raise RuntimeError(f"Failed to list documents: {exc}") from exc

    @staticmethod
    def _build_search_query(
        *,
        document_type: Optional[str] = None,
        processing_status: Optional[DocumentStatus] = None,
        owner: Optional[str] = None,
        workflow_id: Optional[str] = None,
        uploaded_by: Optional[str] = None,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
        outcome: Optional[DocumentOutcome] = None,
        business_domain: Optional[BusinessDomain] = None,
        tags: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """
        Build the shared PyMongo filter used by both search_documents()
        and count_documents(), so the two never drift out of sync.

        business_domain is an M7 addition (GET /documents needs it as a
        list filter); it follows the exact same "exact match on a
        metadata.* field" pattern as document_type/outcome above.
        """
        query: dict[str, Any] = {}

        if document_type is not None:
            query["metadata.document_type"] = document_type
        if processing_status is not None:
            query["metadata.status"] = processing_status.value
        if workflow_id is not None:
            query["workflow_id"] = workflow_id

        if outcome is not None:
            query["metadata.outcome"] = outcome.value

        if business_domain is not None:
            query["metadata.business_domain"] = business_domain.value

        uploader = uploaded_by or owner
        if uploader is not None:
            query["metadata.uploaded_by"] = uploader

        if created_after is not None or created_before is not None:
            date_filter: dict[str, datetime] = {}
            if created_after is not None:
                date_filter["$gte"] = created_after
            if created_before is not None:
                date_filter["$lte"] = created_before
            query["created_at"] = date_filter

        if tags:
            query["tags"] = {"$in": tags}

        return query

    def search_documents(
        self,
        *,
        document_type: Optional[str] = None,
        processing_status: Optional[DocumentStatus] = None,
        owner: Optional[str] = None,
        workflow_id: Optional[str] = None,
        uploaded_by: Optional[str] = None,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
        outcome: Optional[DocumentOutcome] = None,
        business_domain: Optional[BusinessDomain] = None,
        tags: Optional[list[str]] = None,
        limit: Optional[int] = None,
        skip: int = 0,
    ) -> list[dict]:
        """
        Return documents matching all supplied filters, sorted by
        created_at descending (most recent first).

        Every filter is optional and combined with AND semantics.
        `owner` and `uploaded_by` both filter on metadata.uploaded_by —
        `owner` exists as a convenience alias since DocumentMetadata
        has no separate ownership concept; supplying both is redundant
        but not an error.

        Args:
            document_type:      Exact match on metadata.document_type.
            processing_status:  Exact match on metadata.status.
            owner:               Alias for uploaded_by.
            workflow_id:         Exact match on workflow_id.
            uploaded_by:         Exact match on metadata.uploaded_by.
            created_after:       Inclusive lower bound on created_at.
            created_before:      Inclusive upper bound on created_at.
            outcome:            Exact match on metadata.outcome.
            business_domain:    Exact match on metadata.business_domain.
            tags:                Documents carrying at least one of these tags.
            limit:               Optional maximum number of results.
            skip:                Number of results to skip (pagination).

        Returns:
            List of matching document dicts.

        Raises:
            RuntimeError: On any PyMongo failure.
        """
        query = self._build_search_query(
            document_type=document_type,
            processing_status=processing_status,
            owner=owner,
            workflow_id=workflow_id,
            uploaded_by=uploaded_by,
            created_after=created_after,
            created_before=created_before,
            outcome=outcome,
            business_domain=business_domain,
            tags=tags,
        )

        try:
            cursor = self.collection.find(
                query,
                sort=[("created_at", -1)],
                skip=skip,
            )
            if limit is not None:
                cursor = cursor.limit(limit)
            return [self._serialize(doc) for doc in cursor]
        except PyMongoError as exc:
            logger.error("search_documents failed: %s", exc)
            raise RuntimeError(f"Failed to search documents: {exc}") from exc

    def count_documents(
        self,
        *,
        document_type: Optional[str] = None,
        processing_status: Optional[DocumentStatus] = None,
        owner: Optional[str] = None,
        workflow_id: Optional[str] = None,
        uploaded_by: Optional[str] = None,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
        outcome: Optional[DocumentOutcome] = None,
        business_domain: Optional[BusinessDomain] = None,
        tags: Optional[list[str]] = None,
    ) -> int:
        """
        Return the count of documents matching the same filters as
        search_documents(), without fetching or materializing them.

        M7 addition: lets GET /documents report an accurate `total`
        across the whole filtered set while `items` only returns one
        page — without the route loading every matching record itself.

        Raises:
            RuntimeError: On any PyMongo failure.
        """
        query = self._build_search_query(
            document_type=document_type,
            processing_status=processing_status,
            owner=owner,
            workflow_id=workflow_id,
            uploaded_by=uploaded_by,
            created_after=created_after,
            created_before=created_before,
            outcome=outcome,
            business_domain=business_domain,
            tags=tags,
        )
        try:
            return self.collection.count_documents(query)
        except PyMongoError as exc:
            logger.error("count_documents failed: %s", exc)
            raise RuntimeError(f"Failed to count documents: {exc}") from exc

    # ==================================================================
    # DELETE
    # ==================================================================

    def delete_document(self, document_id: str) -> None:
        """
        Delete a document by document_id.

        Args:
            document_id: Identifier of the document to delete.

        Raises:
            ValueError:   If no document with that id exists.
            RuntimeError: On any PyMongo failure.
        """
        self.get_document(document_id)  # raises ValueError if missing

        try:
            self.collection.delete_one({"_id": document_id})
        except PyMongoError as exc:
            logger.error("delete_document('%s') failed: %s", document_id, exc)
            raise RuntimeError(
                f"Failed to delete document '{document_id}': {exc}"
            ) from exc

        logger.debug("Document '%s' deleted.", document_id)
