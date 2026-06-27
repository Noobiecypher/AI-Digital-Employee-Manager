"""
user_repository.py
==================
UserRepository — MongoDB persistence for system user accounts.

This is the ONLY module that reads from or writes to the 'users' collection.
No other module constructs user queries or touches the users collection directly.

Layering contract
-----------------
    API auth routes     →  UserRepository  →  MongoDB
    Auth dependencies   →  UserRepository  (user loaded on every request)

The repository speaks exclusively in plain dicts and raises ``ValueError``
for missing or invalid entities. It has no knowledge of HTTP, FastAPI,
or response shapes.

MongoDB document schema
-----------------------
    {
        "_id":           ObjectId,   # MongoDB PK → exposed as string 'user_id'
        "email":         str,        # unique login identifier (case-insensitive)
        "password_hash": str,        # bcrypt hash; never returned by public methods
        "role":          str,        # SystemRole value, e.g. "admin", "hr"
        "full_name":     str,
        "is_active":     bool,
        "created_at":    datetime,   # UTC; set once on insert
        "updated_at":    datetime,   # UTC; refreshed on every update
    }

Public vs internal responses
-----------------------------
All public methods strip ``password_hash`` before returning.

``get_user_by_email`` is the ONE exception — it keeps ``password_hash``
because it is used exclusively by the login endpoint to verify credentials.
The login route handler is responsible for never forwarding the hash to any
HTTP response body.

Password hashing
----------------
MUST NOT happen inside this repository. The caller (auth_routes.py) is
responsible for hashing the plain-text password before calling
``create_user()``.

Email matching
--------------
All email lookups are case-insensitive via ``$regex / $options:"i"`` with
``re.escape()``, preventing duplicate accounts created with different
casings (e.g. "User@Example.com" and "user@example.com").

ObjectId handling
-----------------
MongoDB's ``_id`` ObjectId is converted to a string ``user_id`` field in
every returned dict. Callers (JWT ``sub`` claim, API path parameters) always
work with the string representation.

Dependency injection
--------------------
The collection can be injected at construction time for unit tests::

    from mongomock import MongoClient as MockClient
    db = MockClient()["test"]
    repo = UserRepository(collection=db["users"])

Omit to resolve lazily via ``get_users_collection()`` on first access.

Recommended indexes (run once during provisioning)
---------------------------------------------------
    db.users.create_index(
        "email", unique=True,
        collation={"locale": "en", "strength": 2}
    )
    db.users.create_index("role")
    db.users.create_index("is_active")
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from backend.database.mongo import get_users_collection

logger = logging.getLogger(__name__)


class UserRepository:
    """
    All MongoDB CRUD operations for system user accounts.

    Methods
    -------
    create_user(data)              → dict  (public — no password_hash)
    get_user_by_id(user_id)        → dict  (public — no password_hash)
    get_user_by_email(email)       → dict  (INTERNAL — includes password_hash)
    list_users()                   → list[dict]  (public — no password_hashes)
    update_user(user_id, updates)  → dict  (public — no password_hash)
    activate_user(user_id)         → dict  (public — no password_hash)
    deactivate_user(user_id)       → dict  (public — no password_hash)
    """

    def __init__(
        self,
        collection: Optional[Collection] = None,
    ) -> None:
        """
        Args:
            collection: Optional pymongo Collection for injection in tests.
                        Resolved lazily via ``get_users_collection()`` on
                        first property access if omitted.
        """
        self._collection: Optional[Collection] = collection

    @property
    def users(self) -> Collection:
        """Resolve and cache the users collection on first access."""
        if self._collection is None:
            self._collection = get_users_collection()
        return self._collection

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_public(doc: dict) -> dict:
        """
        Convert a raw MongoDB document to a public-safe dict.

        - Converts ``_id`` ObjectId to string ``user_id``.
        - Removes ``password_hash``.
        - Formats ``datetime`` fields to ISO 8601 UTC strings.
        """
        result = dict(doc)
        result["user_id"] = str(result.pop("_id"))
        result.pop("password_hash", None)
        for field in ("created_at", "updated_at"):
            if isinstance(result.get(field), datetime):
                result[field] = result[field].strftime("%Y-%m-%dT%H:%M:%SZ")
        return result

    @staticmethod
    def _to_internal(doc: dict) -> dict:
        """
        Convert a raw MongoDB document to an internal dict.

        - Converts ``_id`` ObjectId to string ``user_id``.
        - KEEPS ``password_hash`` (required by the login handler for
          credential verification).
        - Formats ``datetime`` fields to ISO 8601 UTC strings.
        """
        result = dict(doc)
        result["user_id"] = str(result.pop("_id"))
        for field in ("created_at", "updated_at"):
            if isinstance(result.get(field), datetime):
                result[field] = result[field].strftime("%Y-%m-%dT%H:%M:%SZ")
        return result

    @staticmethod
    def _email_filter(email: str) -> dict:
        """
        Build a case-insensitive exact-match filter for the email field.

        Uses ``$regex`` with ``re.escape()`` to prevent special characters
        in caller-supplied email addresses from being treated as regex
        operators. Mirrors the convention in business_data_repository.py.
        """
        return {
            "email": {
                "$regex": f"^{re.escape(email)}$",
                "$options": "i",
            }
        }

    def _load_raw(self, user_id: str) -> dict:
        """
        Load the full MongoDB document by string user_id.

        Converts the string to a ``bson.ObjectId`` before querying.
        Returns the raw document (with ``_id``, ``password_hash``,
        and raw ``datetime`` fields) so callers can choose which
        conversion to apply.

        Args:
            user_id: String representation of the MongoDB ObjectId.

        Returns:
            Raw MongoDB document dict.

        Raises:
            ValueError:   If ``user_id`` is not a valid ObjectId format,
                          or if no document is found.
            RuntimeError: On any PyMongo failure.
        """
        try:
            oid = ObjectId(user_id)
        except InvalidId:
            raise ValueError(f"User '{user_id}' not found")

        try:
            doc = self.users.find_one({"_id": oid})
        except PyMongoError as exc:
            logger.error(
                "_load_raw('%s') failed: %s",
                user_id,
                exc,
            )
            raise RuntimeError(
                f"Failed to retrieve user '{user_id}': {exc}"
            ) from exc

        if doc is None:
            raise ValueError(f"User '{user_id}' not found")

        return doc

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def create_user(self, data: dict) -> dict:
        """
        Insert a new user document.

        Performs a case-insensitive pre-check on ``email`` to prevent
        duplicate accounts. ``created_at`` and ``updated_at`` are injected
        by this method — callers must NOT supply them.

        The caller is responsible for hashing the password before passing
        it as ``data["password_hash"]``. This repository never hashes.

        Args:
            data: Dict containing at minimum:
                  ``email``, ``password_hash``, ``role``, ``full_name``,
                  ``is_active``.

        Returns:
            Public user dict (``password_hash`` stripped, ``user_id`` set).

        Raises:
            ValueError:   If a user with the same email already exists.
            RuntimeError: On any PyMongo failure.
        """
        email: str = data["email"]

        try:
            existing = self.users.find_one(
                self._email_filter(email),
                {"_id": 1},
            )
        except PyMongoError as exc:
            logger.error(
                "create_user: pre-check for '%s' failed: %s",
                email,
                exc,
            )
            raise RuntimeError(
                f"Failed to create user '{email}': {exc}"
            ) from exc

        if existing is not None:
            raise ValueError(f"A user with email '{email}' already exists")

        now = datetime.now(timezone.utc)
        document: dict = {
            **data,
            "created_at": now,
            "updated_at": now,
        }

        try:
            result = self.users.insert_one(document)
        except PyMongoError as exc:
            logger.error(
                "create_user: insert for '%s' failed: %s",
                email,
                exc,
            )
            raise RuntimeError(
                f"Failed to create user '{email}': {exc}"
            ) from exc

        # insert_one injects the generated ObjectId into document["_id"].
        document["_id"] = result.inserted_id
        logger.debug("User '%s' created — id: %s", email, result.inserted_id)
        return self._to_public(document)

    def get_user_by_id(self, user_id: str) -> dict:
        """
        Return a public user dict by user_id (password_hash stripped).

        The primary lookup used by ``get_current_user()`` in
        ``dependencies.py`` on every authenticated request. The JWT ``sub``
        claim carries the string user_id that was assigned at creation.

        Args:
            user_id: String representation of the MongoDB ObjectId.

        Returns:
            Public user dict with ``user_id`` and no ``password_hash``.

        Raises:
            ValueError:   If the user is not found or user_id is not a
                          valid ObjectId string.
            RuntimeError: On any PyMongo failure.
        """
        doc = self._load_raw(user_id)
        return self._to_public(doc)

    def get_user_by_email(self, email: str) -> dict:
        """
        Return an INTERNAL user dict by email, including ``password_hash``.

        INTERNAL USE ONLY.

        Intended exclusively for the login endpoint to retrieve the stored
        hash for ``verify_password()``. The ``password_hash`` value MUST
        never appear in any HTTP response body — the login handler is
        responsible for this guarantee.

        Args:
            email: The user's login email address.

        Returns:
            Internal user dict with ``user_id`` and ``password_hash`` present.

        Raises:
            ValueError:   If no user with that email exists.
            RuntimeError: On any PyMongo failure.
        """
        try:
            doc = self.users.find_one(self._email_filter(email))
        except PyMongoError as exc:
            logger.error(
                "get_user_by_email: lookup for '%s' failed: %s",
                email,
                exc,
            )
            raise RuntimeError(
                f"Failed to retrieve user by email '{email}': {exc}"
            ) from exc

        if doc is None:
            raise ValueError(f"User with email '{email}' not found")

        return self._to_internal(doc)

    def list_users(self) -> list[dict]:
        """
        Return all user documents sorted by email ascending.

        Returns:
            List of public user dicts (no ``password_hash``).

        Raises:
            RuntimeError: On any PyMongo failure.
        """
        try:
            docs = list(
                self.users.find(
                    {},
                    sort=[("email", 1)],
                )
            )
        except PyMongoError as exc:
            logger.error("list_users failed: %s", exc)
            raise RuntimeError(f"Failed to list users: {exc}") from exc

        return [self._to_public(doc) for doc in docs]

    def update_user(self, user_id: str, updates: dict) -> dict:
        """
        Apply partial updates to an existing user document via ``$set``.

        Confirms the user exists before writing. Automatically refreshes
        ``updated_at``. Callers must pre-strip ``None`` values (see
        ``_clean_updates()`` in auth_routes.py).

        Args:
            user_id: String ObjectId of the user to update.
            updates: Dict of field–value pairs to apply. Must not contain
                     ``_id``, ``password_hash``, or ``email``.

        Returns:
            Public user dict after update (``password_hash`` stripped).

        Raises:
            ValueError:   If the user is not found.
            RuntimeError: On any PyMongo failure.
        """
        doc = self._load_raw(user_id)   # raises ValueError if missing

        if not updates:
            return self._to_public(doc)

        updates_with_timestamp = {
            **updates,
            "updated_at": datetime.now(timezone.utc),
        }

        try:
            self.users.update_one(
                {"_id": doc["_id"]},
                {"$set": updates_with_timestamp},
            )
        except PyMongoError as exc:
            logger.error(
                "update_user('%s') failed: %s",
                user_id,
                exc,
            )
            raise RuntimeError(
                f"Failed to update user '{user_id}': {exc}"
            ) from exc

        logger.debug(
            "User '%s' updated — fields: %s",
            user_id,
            list(updates),
        )
        # Re-fetch to guarantee the returned dict reflects the persisted state.
        return self.get_user_by_id(user_id)

    def activate_user(self, user_id: str) -> dict:
        """
        Set ``is_active = True`` for a user account.

        Args:
            user_id: String ObjectId of the user to activate.

        Returns:
            Public user dict after activation.

        Raises:
            ValueError:   If the user is not found.
            RuntimeError: On any PyMongo failure.
        """
        return self.update_user(user_id, {"is_active": True})

    def deactivate_user(self, user_id: str) -> dict:
        """
        Set ``is_active = False`` for a user account.

        Deactivated users are rejected at the ``get_current_active_user``
        dependency layer on every subsequent request, even if they still
        hold a valid unexpired JWT.

        Args:
            user_id: String ObjectId of the user to deactivate.

        Returns:
            Public user dict after deactivation.

        Raises:
            ValueError:   If the user is not found.
            RuntimeError: On any PyMongo failure.
        """
        return self.update_user(user_id, {"is_active": False})