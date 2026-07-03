"""
security.py
===========
Cryptographic primitives for the authentication layer.

All password-hashing and JWT operations are centralised here so that
algorithm choices and secret-key handling have a single point of
maintenance across the codebase.

Environment variables
---------------------
JWT_SECRET_KEY      — required; random string used to sign tokens.
JWT_ALGORITHM       — optional; JOSE algorithm identifier (default: 'HS256').
JWT_EXPIRE_MINUTES  — optional; token lifetime in minutes (default: 60).

Libraries
---------
python-jose[cryptography]  — JWT creation and validation.
passlib[bcrypt]            — bcrypt password hashing.

Public API
----------
    hash_password(plain)                → str
    verify_password(plain, hashed)      → bool
    create_access_token(data)           → str
    decode_token(token)                 → dict[str, Any]
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import ExpiredSignatureError, JWTError, jwt
from passlib.context import CryptContext

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level bcrypt context
# ---------------------------------------------------------------------------

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

_DEFAULT_ALGORITHM: str = "HS256"
_DEFAULT_EXPIRE_MINUTES: int = 60


# ---------------------------------------------------------------------------
# Private configuration helpers
# ---------------------------------------------------------------------------

def _get_secret_key() -> str:
    """
    Read JWT_SECRET_KEY from the environment.

    Raises:
        RuntimeError: If JWT_SECRET_KEY is absent or empty.
    """
    key: str | None = os.getenv("JWT_SECRET_KEY")
    if not key:
        raise RuntimeError(
            "JWT_SECRET_KEY environment variable is not set. "
            "Add JWT_SECRET_KEY to your .env file before starting the server."
        )
    return key


def _get_algorithm() -> str:
    """Return JWT_ALGORITHM from env, defaulting to 'HS256'."""
    return os.getenv("JWT_ALGORITHM", _DEFAULT_ALGORITHM)


def _get_expire_minutes() -> int:
    """
    Return JWT_EXPIRE_MINUTES from env, defaulting to 60.

    Logs a warning and falls back to the default if the env value cannot
    be parsed as an integer.
    """
    raw: str = os.getenv("JWT_EXPIRE_MINUTES", str(_DEFAULT_EXPIRE_MINUTES))
    try:
        return int(raw)
    except ValueError:
        logger.warning(
            "JWT_EXPIRE_MINUTES value '%s' is not a valid integer; "
            "falling back to %d minutes.",
            raw,
            _DEFAULT_EXPIRE_MINUTES,
        )
        return _DEFAULT_EXPIRE_MINUTES


# ---------------------------------------------------------------------------
# Password utilities
# ---------------------------------------------------------------------------

def hash_password(plain_password: str) -> str:
    """
    Hash a plain-text password using bcrypt.

    The resulting hash is safe to store in MongoDB. Never store or log
    the plain-text password.

    Args:
        plain_password: The raw password string provided by the user.

    Returns:
        bcrypt hash string suitable for database storage.
    """
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain-text password against a stored bcrypt hash.

    Constant-time comparison is performed internally by passlib to
    prevent timing-attack leakage.

    Args:
        plain_password:   Raw password string to check.
        hashed_password:  Stored bcrypt hash retrieved from the database.

    Returns:
        True if the password matches the hash, False otherwise.
    """
    return _pwd_context.verify(plain_password, hashed_password)


# ---------------------------------------------------------------------------
# JWT utilities
# ---------------------------------------------------------------------------

def create_access_token(data: dict[str, Any]) -> str:
    """
    Create a signed JWT access token.

    Merges the supplied ``data`` payload with an ``exp`` claim computed
    from JWT_EXPIRE_MINUTES. The ``sub`` claim in ``data`` should contain
    the string representation of the user's MongoDB _id (user_id).

    Args:
        data: Payload dict to encode. Must contain a ``'sub'`` claim
              identifying the user (e.g. ``{"sub": "64a1bc..."}``) .

    Returns:
        Compact signed JWT string.

    Raises:
        RuntimeError: If JWT_SECRET_KEY is not configured.
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=_get_expire_minutes())
    payload: dict[str, Any] = {**data, "exp": expire}

    return jwt.encode(
        payload,
        _get_secret_key(),
        algorithm=_get_algorithm(),
    )


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT access token.

    Verifies the signature and the ``exp`` claim. Does NOT verify the
    ``sub`` claim — callers are responsible for loading and validating
    the user from the database after calling this function.

    Args:
        token: Raw JWT string extracted from the Authorization header.

    Returns:
        Decoded payload dict (e.g. ``{"sub": "64a1bc...", "exp": ...}``).

    Raises:
        ValueError: If the token has expired or is otherwise invalid
                    (malformed, wrong key, unsupported algorithm, etc.).
    """
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            _get_secret_key(),
            algorithms=[_get_algorithm()],
        )
        return payload
    except ExpiredSignatureError as exc:
        raise ValueError("Token has expired.") from exc
    except JWTError as exc:
        raise ValueError(f"Invalid token: {exc}") from exc