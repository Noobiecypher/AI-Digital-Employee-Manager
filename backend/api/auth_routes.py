"""
auth_routes.py
==============
FastAPI APIRouter for authentication and system user management.

Registered in main.py under the '/auth' prefix:

    app.include_router(
        auth_router,
        prefix="/auth",
        tags=["authentication"],
    )

This router is completely isolated from routes.py (workflow router) and
business_routes.py (business data router). No workflow or business logic
is imported here.

Endpoint surface
----------------
    POST   /auth/login                       — public; issue JWT access token
    GET    /auth/me                          — any authenticated user; own profile
    POST   /auth/users                       — admin only; create system user
    GET    /auth/users                       — admin only; list all system users
    PUT    /auth/users/{user_id}             — admin only; update user
    PATCH  /auth/users/{user_id}/activate    — admin only; activate user account
    PATCH  /auth/users/{user_id}/deactivate  — admin only; deactivate user account

Authorization
-------------
All user-management endpoints are guarded by ``Depends(require_permission(...))``.
No route handler inspects ``current_user["role"]`` directly.

Passwords
---------
Passwords are hashed with ``hash_password()`` in this layer before any
data reaches the repository. The plain-text value never touches the DB.

Error contract  (mirrors business_routes.py exactly)
----------------------------------------------------
    401  UNAUTHORIZED          — invalid credentials / inactive account
    403  FORBIDDEN             — insufficient permissions
    404  ENTITY_NOT_FOUND      — user not found
    409  CONFLICT              — duplicate email on create
    422  VALIDATION_ERROR      — Pydantic rejected the request body
    500  INTERNAL_SERVER_ERROR — unexpected DB or server failure

All error responses share the same JSON envelope:
    {
        "error": {
            "code":    "<SCREAMING_SNAKE_CASE>",
            "message": "<human-readable string>",
            "field":   "<dotted.field.name> | null",
            "details": null
        }
    }
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from backend.api.auth_schemas import (
    CurrentUserResponse,
    LoginRequest,
    TokenResponse,
    UserCreateRequest,
    UserResponse,
    UserUpdateRequest,
)
from backend.auth.dependencies import get_current_active_user, require_permission
from backend.auth.permissions import Permission
from backend.auth.security import create_access_token, hash_password, verify_password
from backend.database.user_repository import UserRepository

logger = logging.getLogger(__name__)

auth_router = APIRouter()
_repo = UserRepository()


# ---------------------------------------------------------------------------
# Shared helpers (mirror business_routes.py exactly)
# ---------------------------------------------------------------------------

def error_response(
    status_code: int,
    code: str,
    message: str,
    field: str | None = None,
) -> HTTPException:
    """
    Build a structured HTTPException that matches the project error contract.

    Intentionally mirrors the identical helper in business_routes.py and
    routes.py to keep all three routers fully self-contained.

    Args:
        status_code: HTTP status code to return.
        code:        Machine-readable screaming-snake-case error code.
        message:     Human-readable description of the failure.
        field:       Optional dotted path to the offending request field.

    Returns:
        HTTPException ready to be raised by a route handler.
    """
    return HTTPException(
        status_code=status_code,
        detail={
            "error": {
                "code": code,
                "message": message,
                "field": field,
                "details": None,
            }
        },
    )


def _clean_updates(data: dict) -> dict:
    """
    Strip None-valued keys from an update dict before passing to the repo.

    None means "caller did not supply this field — leave it unchanged."
    Mirrors ``_clean_updates()`` in business_routes.py.
    """
    return {k: v for k, v in data.items() if v is not None}


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

@auth_router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and receive a JWT access token",
    description=(
        "Verify email and password against stored credentials. "
        "On success, returns a signed JWT access token valid for "
        "JWT_EXPIRE_MINUTES minutes. Inactive accounts are rejected."
    ),
)
async def login(body: LoginRequest) -> TokenResponse:
    """Authenticate a user and return a JWT access token."""

    # 1. Look up user by email.
    #    get_user_by_email returns the INTERNAL dict including password_hash.
    #    We must never forward this hash to any response.
    try:
        user = _repo.get_user_by_email(str(body.email))
    except ValueError:
        # Return the same message for missing email and wrong password to
        # prevent user-enumeration attacks.
        raise error_response(
            status.HTTP_401_UNAUTHORIZED,
            "UNAUTHORIZED",
            "Invalid email or password.",
        )
    except RuntimeError as exc:
        logger.error("login: DB error for '%s': %s", body.email, exc)
        raise error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_SERVER_ERROR",
            "Authentication failed due to a server error.",
        )

    # 2. Verify the supplied password against the stored bcrypt hash.
    if not verify_password(body.password, user["password_hash"]):
        raise error_response(
            status.HTTP_401_UNAUTHORIZED,
            "UNAUTHORIZED",
            "Invalid email or password.",
        )

    # 3. Reject inactive accounts before issuing a token.
    if not user.get("is_active", False):
        raise error_response(
            status.HTTP_401_UNAUTHORIZED,
            "UNAUTHORIZED",
            "This account has been deactivated. Contact an administrator.",
        )

    # 4. Issue a JWT. The 'sub' claim carries the string user_id
    #    (MongoDB ObjectId string) used by get_current_user() to reload
    #    the user on every subsequent request.
    token = create_access_token({"sub": user["user_id"]})
    return TokenResponse(access_token=token)


# ---------------------------------------------------------------------------
# Current user (self)
# ---------------------------------------------------------------------------

@auth_router.get(
    "/me",
    response_model=CurrentUserResponse,
    summary="Return the authenticated user's own profile",
    description=(
        "Returns the profile of the currently authenticated user. "
        "Accessible to any role with a valid, unexpired JWT. "
        "This is the only endpoint where non-admin roles can read "
        "a user document."
    ),
)
async def me(
    current_user: dict = Depends(get_current_active_user),
) -> CurrentUserResponse:
    """Return the currently authenticated user's profile."""
    return CurrentUserResponse(**current_user)


# ---------------------------------------------------------------------------
# User administration (admin only)
# ---------------------------------------------------------------------------

@auth_router.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new system user (admin only)",
    description=(
        "Insert a new system user record. "
        "``email`` must be unique (case-insensitive). "
        "Returns 409 if the email is already registered. "
        "The plain-text password is hashed before persistence."
    ),
)
async def create_user(
    body: UserCreateRequest,
    _: dict = Depends(require_permission(Permission.USERS_CREATE)),
) -> UserResponse:
    """Create a new system user. Returns 409 if email already exists."""

    user_data = {
        "email":         str(body.email),
        "password_hash": hash_password(body.password),
        "full_name":     body.full_name,
        "role":          body.role.value,   # store the string value, not the enum
        "is_active":     True,

        "employee_id":   body.employee_id,
        "employee_name": body.employee_name,
        "candidate_id":  body.candidate_id,
    }

    try:
        user = _repo.create_user(user_data)
    except ValueError as exc:
        raise error_response(
            status.HTTP_409_CONFLICT,
            "CONFLICT",
            str(exc),
            "email",
        )
    except RuntimeError as exc:
        logger.error("create_user route error: %s", exc)
        raise error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_SERVER_ERROR",
            str(exc),
        )

    return UserResponse(**user)


@auth_router.get(
    "/users",
    response_model=list[UserResponse],
    summary="List all system users (admin only)",
    description=(
        "Return all registered system user accounts sorted by email. "
        "``password_hash`` is never included in any response."
    ),
)
async def list_users(
    _: dict = Depends(require_permission(Permission.USERS_READ)),
) -> list[UserResponse]:
    """List all system user accounts."""

    try:
        users = _repo.list_users()
    except RuntimeError as exc:
        logger.error("list_users route error: %s", exc)
        raise error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_SERVER_ERROR",
            str(exc),
        )

    return [UserResponse(**u) for u in users]


@auth_router.put(
    "/users/{user_id}",
    response_model=UserResponse,
    summary="Update a system user (admin only)",
    description=(
        "Partially update a user record. Only non-null fields are written. "
        "``email`` is the immutable login identifier and cannot be changed "
        "via this endpoint. Returns 404 if the user does not exist."
    ),
)
async def update_user(
    user_id: str,
    body: UserUpdateRequest,
    _: dict = Depends(require_permission(Permission.USERS_UPDATE)),
) -> UserResponse:
    """Partially update a system user. Returns 404 if not found."""

    # mode="json" converts SystemRole enum members to their string values
    # so MongoDB receives "manager" rather than <SystemRole.MANAGER: 'manager'>.
    updates = _clean_updates(body.model_dump(mode="json"))

    try:
        user = _repo.update_user(user_id, updates)
    except ValueError as exc:
        raise error_response(
            status.HTTP_404_NOT_FOUND,
            "ENTITY_NOT_FOUND",
            str(exc),
            "user_id",
        )
    except RuntimeError as exc:
        logger.error("update_user '%s' route error: %s", user_id, exc)
        raise error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_SERVER_ERROR",
            str(exc),
        )

    return UserResponse(**user)


@auth_router.patch(
    "/users/{user_id}/activate",
    response_model=UserResponse,
    summary="Activate a user account (admin only)",
    description=(
        "Set ``is_active = True`` on a user account. "
        "The user can log in immediately after activation."
    ),
)
async def activate_user(
    user_id: str,
    _: dict = Depends(require_permission(Permission.USERS_UPDATE)),
) -> UserResponse:
    """Activate a user account. Returns 404 if not found."""

    try:
        user = _repo.activate_user(user_id)
    except ValueError as exc:
        raise error_response(
            status.HTTP_404_NOT_FOUND,
            "ENTITY_NOT_FOUND",
            str(exc),
            "user_id",
        )
    except RuntimeError as exc:
        logger.error("activate_user '%s' route error: %s", user_id, exc)
        raise error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_SERVER_ERROR",
            str(exc),
        )

    return UserResponse(**user)


@auth_router.patch(
    "/users/{user_id}/deactivate",
    response_model=UserResponse,
    summary="Deactivate a user account (admin only)",
    description=(
        "Set ``is_active = False`` on a user account. "
        "Deactivated users holding a valid JWT are rejected at the "
        "``get_current_active_user`` dependency layer on their next request."
    ),
)
async def deactivate_user(
    user_id: str,
    _: dict = Depends(require_permission(Permission.USERS_UPDATE)),
) -> UserResponse:
    """Deactivate a user account. Returns 404 if not found."""

    try:
        user = _repo.deactivate_user(user_id)
    except ValueError as exc:
        raise error_response(
            status.HTTP_404_NOT_FOUND,
            "ENTITY_NOT_FOUND",
            str(exc),
            "user_id",
        )
    except RuntimeError as exc:
        logger.error("deactivate_user '%s' route error: %s", user_id, exc)
        raise error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_SERVER_ERROR",
            str(exc),
        )

    return UserResponse(**user)