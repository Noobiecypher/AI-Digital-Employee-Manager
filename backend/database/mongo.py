"""
mongo.py
========
MongoDB client factory and connection management.

Single source of truth for the MongoClient and collection references.
All other database modules import from here — no direct MongoClient
construction elsewhere in the codebase.

Environment variables
---------------------
MONGO_URI        — required; full MongoDB connection string
MONGO_DB_NAME    — optional; defaults to 'ai_digital_employee'

Startup behaviour
-----------------
get_client() issues a lightweight 'ping' on first call so that
misconfiguration surfaces immediately (at application startup via
the FastAPI lifespan hook) rather than silently on the first query.

Thread safety
-------------
The module-level _client is set exactly once during the FastAPI
lifespan startup handler, before any request handlers or background
tasks are scheduled. No additional locking is required for MVP.
"""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.errors import ConfigurationError, ConnectionFailure

load_dotenv(override=True)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_client: MongoClient | None = None

_DEFAULT_DB_NAME: str = "ai_digital_employee"
_SERVER_SELECTION_TIMEOUT_MS: int = 5_000  # fail fast on misconfiguration


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_client() -> MongoClient:
    """
    Return the singleton MongoClient, initialising it on the first call.

    Reads connection settings from environment variables:
        MONGO_URI     — required; full MongoDB connection string.
        MONGO_DB_NAME — optional; database name (defaults to 'ai_digital_employee').

    A 'ping' command is issued on first connection to verify server
    availability before any real queries are attempted.

    Returns:
        Initialised MongoClient.

    Raises:
        RuntimeError: If MONGO_URI is not set, or if the server cannot
                      be reached within the configured timeout.
    """
    global _client

    if _client is not None:
        return _client

    uri: str | None = os.getenv("MONGO_URI")
    if not uri:
        raise RuntimeError(
            "MONGO_URI environment variable is not set. "
            "Add MONGO_URI to your .env file or environment before starting the server."
        )

    try:
        candidate: MongoClient = MongoClient(
            uri,
            serverSelectionTimeoutMS=_SERVER_SELECTION_TIMEOUT_MS,
        )
        # Verify the server is reachable — raises ConnectionFailure if not.
        candidate.admin.command("ping")
        _client = candidate
        logger.info("MongoDB connection established.")
    except (ConnectionFailure, ConfigurationError) as exc:
        # Do NOT cache a broken client — next call retries from scratch.
        raise RuntimeError(
            "Failed to connect to MongoDB. "
            "Check MONGO_URI and ensure the server is reachable. "
            f"Detail: {exc}"
        ) from exc

    return _client

def get_users_collection() -> Collection:
    """
    Return the users collection.

    Stores system user accounts for authentication and authorization.
    Completely separate from the business roles collection.
    """
    db_name: str = os.getenv("MONGO_DB_NAME", _DEFAULT_DB_NAME)
    return get_client()[db_name]["users"]

def get_workflows_collection() -> Collection:
    """
    Return the 'workflows' collection from the configured database.

    The database name is read from MONGO_DB_NAME (defaults to
    'ai_digital_employee'). MongoDB creates the collection automatically
    on the first write — no explicit creation step is required.

    Returns:
        pymongo Collection object for workflow documents.
    """
    db_name: str = os.getenv("MONGO_DB_NAME", _DEFAULT_DB_NAME)
    return get_client()[db_name]["workflows"]


# ---------------------------------------------------------------------------
# Data-layer collections — used by data_loader.py
# Each function follows the identical pattern as get_workflows_collection().
# Called fresh on every data_loader invocation — no caching.
# ---------------------------------------------------------------------------

def get_employees_collection() -> Collection:
    """
    Return the 'employees' collection from the configured database.

    Populated by seed_data.py from employees.json.
    Frontend CRUD operations write directly to this collection;
    every data_loader call fetches the latest state.

    Returns:
        pymongo Collection object for employee documents.
    """
    db_name: str = os.getenv("MONGO_DB_NAME", _DEFAULT_DB_NAME)
    return get_client()[db_name]["employees"]


def get_roles_collection() -> Collection:
    """
    Return the 'roles' collection from the configured database.

    Populated by seed_data.py, which flattens departments.json into
    one document per role, each carrying its parent department's
    location and rating_scale fields.

    Returns:
        pymongo Collection object for role documents.
    """
    db_name: str = os.getenv("MONGO_DB_NAME", _DEFAULT_DB_NAME)
    return get_client()[db_name]["roles"]


def get_goals_collection() -> Collection:
    """
    Return the 'goals' collection from the configured database.

    Populated by seed_data.py from goals.json.

    Returns:
        pymongo Collection object for goal documents.
    """
    db_name: str = os.getenv("MONGO_DB_NAME", _DEFAULT_DB_NAME)
    return get_client()[db_name]["goals"]


def get_goal_update_history_collection() -> Collection:
    """
    Return the 'goal_update_history' collection from
    the configured database.

    Stores every goal update review event
    (approved/rejected) for audit purposes.

    Returns:
        pymongo Collection object.
    """
    db_name: str = os.getenv(
        "MONGO_DB_NAME",
        _DEFAULT_DB_NAME,
    )

    return get_client()[db_name][
        "goal_update_history"
    ]

def get_products_collection() -> Collection:
    """
    Return the 'products' collection from the configured database.

    Populated by seed_data.py from products.json.

    Returns:
        pymongo Collection object for product documents.
    """
    db_name: str = os.getenv("MONGO_DB_NAME", _DEFAULT_DB_NAME)
    return get_client()[db_name]["products"]


def get_candidates_collection() -> Collection:
    """
    Return the 'candidates' collection from the configured database.

    Populated by seed_data.py from candidates.json.

    Returns:
        pymongo Collection object for candidate documents.
    """
    db_name: str = os.getenv("MONGO_DB_NAME", _DEFAULT_DB_NAME)
    return get_client()[db_name]["candidates"]


def get_reports_collection() -> Collection:
    """
    Return the 'reports' collection from the configured database.

    Populated by seed_data.py from reports.json.

    Returns:
        pymongo Collection object for report documents.
    """

    db_name: str = os.getenv(
        "MONGO_DB_NAME",
        _DEFAULT_DB_NAME
    )
    return get_client()[db_name]["reports"]


def close_client() -> None:
    """
    Close the MongoClient and release its connection pool.

    Intended for the FastAPI lifespan teardown hook.
    Safe to call even if the client was never initialised.
    """
    global _client

    if _client is not None:
        _client.close()
        _client = None
        logger.info("MongoDB connection closed.")