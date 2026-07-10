"""
workflow_repository.py
======================
WorkflowRepository — MongoDB persistence for AgentState.

This is the ONLY module that reads from or writes to the 'workflows'
collection. No other module constructs queries or touches pymongo directly.

Layering contract
-----------------
    WorkflowExecutor  →  WorkflowRepository  →  MongoDB
    API routes        →  WorkflowRepository  (timestamps only)

The repository speaks exclusively in AgentState objects and plain dicts.
It has no knowledge of HTTP, FastAPI, or frontend response shapes.

MongoDB document schema  (ref: workflow_state.md §12.2)
--------------------------------------------------------
    {
        "_id":        str,       # workflow_id ("wf_<uuid4>") — Mongo primary key
        "created_at": datetime,  # UTC; written once via $setOnInsert on first upsert
        "updated_at": datetime,  # UTC; overwritten on every save()
        "state":      dict,      # AgentState.model_dump() — full serialised state
    }

Recommended indexes (run once during provisioning)
---------------------------------------------------
    db.workflows.create_index("created_at")           # list_ids() sort
    db.workflows.create_index("state.status")         # future status-filter queries
    # _id is automatically indexed by MongoDB — no explicit creation needed.

Dependency injection
--------------------
WorkflowRepository accepts an optional Collection at construction time.
Pass a mongomock collection in tests to avoid hitting a real database:

    from mongomock import MongoClient as MockClient
    col = MockClient()["test"]["workflows"]
    repo = WorkflowRepository(collection=col)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from backend.models import AgentState
from backend.database.mongo import get_workflows_collection

logger = logging.getLogger(__name__)


class WorkflowRepository:
    """
    All MongoDB persistence operations for workflow state.

    Methods
    -------
    save(state)                  — upsert AgentState by workflow_id
    load(workflow_id)            — load AgentState; raises KeyError if missing
    list_ids()                   — return all workflow_ids in insertion order
    get_timestamps(wf_id)        — return created_at / updated_at as ISO strings
    list_workflow_states()       — return AgentState list (no timestamps)
    list_workflow_states_with_timestamps() — return (AgentState, created_at) pairs
    """

    def __init__(
        self,
        collection: Optional[Collection] = None,
    ) -> None:
        self._collection: Optional[Collection] = collection

    @property
    def collection(self) -> Collection:
        """Resolve and cache the collection on first access."""
        if self._collection is None:
            self._collection = get_workflows_collection()
        return self._collection

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def save(self, state: AgentState) -> None:
        """
        Persist AgentState using an upsert keyed on workflow_id.

        $setOnInsert ensures created_at is written exactly once — on the
        first INSERT — and never overwritten by subsequent updates.
        updated_at and state are replaced on every call.
        """
        now: datetime = datetime.now(timezone.utc)

        try:
            self.collection.update_one(
                {"_id": state.workflow_id},
                {
                    "$set": {
                        "updated_at": now,
                        "state": state.model_dump(),
                    },
                    "$setOnInsert": {
                        "created_at": now,
                    },
                },
                upsert=True,
            )
        except PyMongoError as exc:
            logger.error(
                "[%s] Failed to save state — status=%s error=%s",
                state.workflow_id,
                state.status,
                exc,
            )
            raise RuntimeError(
                f"Failed to save workflow '{state.workflow_id}': {exc}"
            ) from exc

        logger.debug(
            "[%s] Persisted — status=%s task=%s",
            state.workflow_id,
            state.status,
            state.current_task_id or "(none)",
        )

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def load(self, workflow_id: str) -> AgentState:
        """
        Load AgentState from MongoDB by workflow_id.
        """
        try:
            doc = self.collection.find_one({"_id": workflow_id})
        except PyMongoError as exc:
            logger.error("[%s] Failed to load state: %s", workflow_id, exc)
            raise RuntimeError(
                f"Failed to load workflow '{workflow_id}': {exc}"
            ) from exc

        if doc is None:
            raise KeyError(workflow_id)

        return AgentState.model_validate(doc["state"])

    def list_ids(self) -> list[str]:
        """
        Return all workflow_ids in the collection, ordered by created_at.
        """
        try:
            cursor = self.collection.find(
                {},
                {"_id": 1},
                sort=[("created_at", 1)],
            )
            return [doc["_id"] for doc in cursor]
        except PyMongoError as exc:
            logger.error("Failed to list workflow IDs: %s", exc)
            raise RuntimeError(f"Failed to list workflow IDs: {exc}") from exc

    def list_workflow_states(self) -> list[AgentState]:
        """
        Return all AgentState objects ordered by created_at.
        Used by analytics_service for status counts.
        """
        try:
            cursor = self.collection.find(
                {},
                {"state": 1, "_id": 0},
                sort=[("created_at", 1)],
            )
            return [AgentState.model_validate(doc["state"]) for doc in cursor]
        except PyMongoError as exc:
            logger.error("Failed to fetch workflow states: %s", exc)
            raise RuntimeError(f"Failed to fetch workflow states: {exc}") from exc

    def list_workflow_states_with_timestamps(self) -> list[tuple[AgentState, datetime | None]]:
        """
        Return (AgentState, created_at) pairs ordered by created_at.
        Used by analytics_service to build chart data with real dates.

        Returns:
            List of (AgentState, created_at datetime in UTC) tuples.
            created_at is None if the field is missing on older documents.
        """
        try:
            cursor = self.collection.find(
                {},
                {"state": 1, "created_at": 1, "_id": 0},
                sort=[("created_at", 1)],
            )
            result = []
            for doc in cursor:
                state = AgentState.model_validate(doc["state"])
                created_at = doc.get("created_at")  # datetime or None
                result.append((state, created_at))
            return result
        except PyMongoError as exc:
            logger.error("Failed to fetch workflow states with timestamps: %s", exc)
            raise RuntimeError(
                f"Failed to fetch workflow states with timestamps: {exc}"
            ) from exc

    def get_timestamps(self, workflow_id: str) -> dict[str, str | None]:
        """
        Return ISO-formatted created_at and updated_at for a workflow.
        """
        try:
            doc = self.collection.find_one(
                {"_id": workflow_id},
                {"created_at": 1, "updated_at": 1, "_id": 0},
            )
        except PyMongoError as exc:
            logger.error("[%s] Failed to fetch timestamps: %s", workflow_id, exc)
            raise RuntimeError(
                f"Failed to get timestamps for workflow '{workflow_id}': {exc}"
            ) from exc

        if doc is None:
            return {"created_at": None, "updated_at": None}

        def _fmt(dt: datetime | None) -> str | None:
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ") if dt else None

        return {
            "created_at": _fmt(doc.get("created_at")),
            "updated_at": _fmt(doc.get("updated_at")),
        }