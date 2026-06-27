"""
dependencies.py
===============
FastAPI dependency functions for authentication and authorisation.

These dependencies form the only bridge between the HTTP layer and the
auth/permission subsystem. All route handlers must use them — no route
handler should call decode_token() or has_permission() directly.

Public API
----------
    get_current_user(credentials)    — Extract Bearer token → load user dict.
    get_current_active_user(user)    — Assert user.is_active.
    require_permission(permission)   — Factory returning a Depends-compatible
                                       callable that guards a route.

Authorization contract
----------------------
Route handlers MUST use::

    Depends(require_permission(Permission.SOME_ACTION))

Route handlers MUST NEVER do::

    if current_user["role"] == "admin": ...

The returned dependency resolves to the active user dict so that handlers
can capture it for own-resource filtering if needed.

Error codes
-----------
    401 UNAUTHORIZED  — missing / expired / malformed token, or user
                        no longer exists, or account is deactivated.
    403 FORBIDDEN     — valid token but role lacks the required permission.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.auth.permissions import Permission, has_permission
from backend.auth.security import decode_token
from backend.database.user_repository import UserRepository

logger = logging.getLogger(__name__)

# HTTPBearer with auto_error=False so we can emit a structured 401 rather
# than FastAPI's default plain-text "Not authenticated" response.
_bearer = HTTPBearer(auto_error=False)

# Module-level repository singleton — mirrors the pattern used in
# business_routes.py and auth_routes.py.
_repo = UserRepository()


# ---------------------------------------------------------------------------
# Private error helpers — match the project error contract exactly
# ---------------------------------------------------------------------------

def _unauthorized(message: str) -> HTTPException:
    """Build a structured 401 HTTPException."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "error": {
                "code": "UNAUTHORIZED",
                "message": message,
                "field": None,
                "details": None,
            }
        },
        headers={"WWW-Authenticate": "Bearer"},
    )


def _forbidden(message: str) -> HTTPException:
    """Build a structured 403 HTTPException."""
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "error": {
                "code": "FORBIDDEN",
                "message": message,
                "field": None,
                "details": None,
            }
        },
    )


# ---------------------------------------------------------------------------
# Core dependencies
# ---------------------------------------------------------------------------

async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict[str, Any]:
    """
    Extract and validate the Bearer token; load the calling user from the DB.

    Steps
    -----
    1. Reject requests with no Authorization header (→ 401).
    2. Decode the JWT via ``decode_token()`` (→ 401 on expiry / bad sig).
    3. Extract the ``sub`` claim (the string user_id / MongoDB ObjectId).
    4. Load the user from MongoDB via ``UserRepository.get_user_by_id()``.
       Raises 401 if the user was deleted after the token was issued.

    Args:
        credentials: Injected by HTTPBearer; None when the header is absent.

    Returns:
        Public user dict (no password_hash) from UserRepository.

    Raises:
        HTTP 401: On any authentication failure.
    """
    if credentials is None:
        raise _unauthorized("Authorization header is missing.")

    try:
        payload = decode_token(credentials.credentials)
    except ValueError as exc:
        raise _unauthorized(str(exc))

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise _unauthorized("Token payload is missing the 'sub' claim.")

    try:
        user = _repo.get_user_by_id(user_id)
    except ValueError:
        # The token was valid but the user has since been deleted.
        raise _unauthorized("User account no longer exists.")
    except RuntimeError as exc:
        logger.error(
            "get_current_user: DB error loading sub='%s': %s",
            user_id,
            exc,
        )
        raise _unauthorized("Failed to load user.")

    return user


async def get_current_active_user(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Assert that the authenticated user's account is active.

    Sits between get_current_user and route handlers. Any route that
    requires an active account (all authenticated routes) should depend
    on this function rather than get_current_user directly.

    Args:
        current_user: Injected by get_current_user.

    Returns:
        The same user dict, unchanged.

    Raises:
        HTTP 401: If the account has been deactivated since token issuance.
    """
    if not current_user.get("is_active", False):
        raise _unauthorized("This account has been deactivated.")
    return current_user


# ---------------------------------------------------------------------------
# Permission guard factory
# ---------------------------------------------------------------------------

def require_permission(permission: Permission) -> Callable:
    """
    Return a FastAPI dependency that enforces ``permission`` on a route.

    Usage in route handlers::

        @router.get("/employees")
        async def list_employees(
            _: dict = Depends(require_permission(Permission.EMPLOYEES_READ)),
        ): ...

    The dependency resolves to the authenticated active user dict, which
    can be captured by the route handler for own-resource filtering::

        @router.get("/me/goals")
        async def my_goals(
            current_user: dict = Depends(
                require_permission(Permission.GOALS_READ)
            ),
        ):
            employee_name = current_user["full_name"]
            ...

    Args:
        permission: The ``Permission`` enum member required to access the route.

    Returns:
        An async callable suitable for use with ``Depends()``.

    Raises:
        HTTP 403: At request time if the user's role does not include
                  ``permission``.
    """

    async def _check_permission(
        current_user: dict[str, Any] = Depends(get_current_active_user),
    ) -> dict[str, Any]:
        if not has_permission(current_user["role"], permission):
            raise _forbidden(
                f"You do not have permission to perform this action "
                f"(required: '{permission.value}')."
            )
        return current_user

    # Give the inner function a unique __name__ so FastAPI's dependency
    # graph can distinguish between multiple require_permission() usages
    # within the same application.
    _check_permission.__name__ = f"require_{permission.value.replace(':', '_')}"

    return _check_permission