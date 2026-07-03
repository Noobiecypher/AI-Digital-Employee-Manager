"""
auth_schemas.py
===============
Pydantic request / response schemas for the authentication and
system user-management endpoints.

Used exclusively by ``auth_routes.py``. Workflow and business routes are
completely unaffected — they continue to use ``schemas.py`` and
``business_schemas.py`` respectively.

Design principles
-----------------
Request schemas  — ``ConfigDict(extra="forbid")``
    Strict: any unknown field in the JSON body causes an immediate 422,
    preventing silent data loss or field injection.

Response schemas — ``ConfigDict(extra="ignore")``
    Lenient: extra fields present in MongoDB documents that are not
    modelled here are silently dropped. This stabilises the API contract
    against future document additions.

Immutable fields
----------------
``email`` is intentionally absent from ``UserUpdateRequest`` — it serves as
the login identifier and cannot be changed via the CRUD endpoint. Password
rotation endpoints are out of scope for this implementation.

Schema index
------------
    LoginRequest        — POST /auth/login body
    TokenResponse       — POST /auth/login response
    UserCreateRequest   — POST /auth/users body (admin only)
    UserUpdateRequest   — PUT  /auth/users/{user_id} body (admin only)
    UserResponse        — Admin user-management endpoint responses
    CurrentUserResponse — GET  /auth/me response
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from backend.auth.permissions import SystemRole


# ==============================================================
# AUTHENTICATION
# ==============================================================

class LoginRequest(BaseModel):
    """
    Payload for POST /auth/login.

    Uses ``email`` as the login identifier to match the users collection
    schema and ``UserRepository.get_user_by_email()`` contract.
    """

    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(
        ...,
        description="Registered email address used as the login identifier.",
        examples=["alice@example.com"],
    )
    password: str = Field(
        ...,
        min_length=1,
        description=(
            "Plain-text password for credential verification. "
            "Never stored or logged; verified against the bcrypt hash."
        ),
    )


class TokenResponse(BaseModel):
    """
    Response returned by POST /auth/login on successful authentication.

    The ``access_token`` must be included in subsequent requests as::

        Authorization: Bearer <access_token>
    """

    model_config = ConfigDict(extra="ignore")

    access_token: str = Field(
        description=(
            "Signed JWT access token. "
            "Include as 'Authorization: Bearer <token>' on protected routes."
        ),
    )
    token_type: str = Field(
        default="bearer",
        description="OAuth2-compatible token type identifier.",
    )


# ==============================================================
# USER ADMINISTRATION (admin only)
# ==============================================================

class UserCreateRequest(BaseModel):
    """
    Payload for POST /auth/users (admin only).

    ``password`` is accepted as plain-text here. ``auth_routes.py`` calls
    ``hash_password()`` and stores only the hash — the plain-text value
    is never persisted or logged.
    """

    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(
        ...,
        description=(
            "Unique email address used as the login identifier. "
            "Case-insensitive — 'User@Example.com' and 'user@example.com' "
            "are treated as the same account."
        ),
        examples=["bob@example.com"],
    )
    password: str = Field(
        ...,
        min_length=8,
        description=(
            "Plain-text password. Minimum 8 characters. "
            "Stored as a bcrypt hash — never in plain text."
        ),
    )
    full_name: str = Field(
        ...,
        min_length=1,
        max_length=120,
        description="Display name for the user.",
        examples=["Bob Smith"],
    )
    role: SystemRole = Field(
        ...,
        description=(
            "System role assigned to this user. "
            "Determines which permissions the user holds. "
            "Exactly one role per user."
        ),
        examples=["manager"],
    )
    employee_id: str | None = None
    employee_name: str | None = None
    candidate_id: str | None = None

class UserUpdateRequest(BaseModel):
    """
    Payload for PUT /auth/users/{user_id} (admin only).

    All fields are optional; only non-None values are written as a
    ``$set`` patch. ``email`` is the immutable login identifier and is
    absent from this schema intentionally.
    """

    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
        description="Updated display name.",
    )
    role: SystemRole | None = Field(
        default=None,
        description=(
            "Updated system role. "
            "Takes effect immediately on the next authenticated request."
        ),
    )
    employee_id: str | None = None
    employee_name: str | None = None
    candidate_id: str | None = None

# ==============================================================
# RESPONSE MODELS
# ==============================================================

class UserResponse(BaseModel):
    """
    User document returned by admin user-management endpoints.

    ``password_hash`` is never included. The ``user_id`` field is the
    string representation of the MongoDB ``_id`` ObjectId, produced by
    ``UserRepository._to_public()``.
    """

    model_config = ConfigDict(extra="ignore")

    user_id: str = Field(
        description="String representation of the MongoDB _id ObjectId."
    )
    email: str
    full_name: str
    role: SystemRole
    is_active: bool
    created_at: str | None = Field(
        default=None,
        description="ISO 8601 UTC creation timestamp."
        )
    updated_at: str | None = Field(
        default=None,
        description="ISO 8601 UTC last-modified timestamp."
        )
    employee_id: str | None = None
    employee_name: str | None = None
    candidate_id: str | None = None

class CurrentUserResponse(BaseModel):
    """
    Response for GET /auth/me.

    Returns the authenticated user's own profile information.
    Accessible to any role with a valid JWT — the only endpoint where
    non-admin users can inspect a user document.
    """

    model_config = ConfigDict(extra="ignore")

    user_id: str = Field(
        description="String representation of the MongoDB _id ObjectId."
    )
    email: str
    full_name: str
    role: SystemRole
    is_active: bool
    employee_id: str | None = None
    employee_name: str | None = None
    candidate_id: str | None = None