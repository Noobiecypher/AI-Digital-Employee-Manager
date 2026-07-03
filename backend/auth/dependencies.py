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
import os
from typing import Any, Callable
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from backend.auth.permissions import Permission, has_permission
from backend.auth.security import decode_token
from backend.database.user_repository import UserRepository

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=False)
_repo = UserRepository()

# ---------------------------------------------------------------------------
# Dev mock users — used when token starts with "mock_token_"
# Only active when ENVIRONMENT != "production"
# ---------------------------------------------------------------------------
_MOCK_USERS: dict[str, dict[str, Any]] = {
    "admin":     { "id": "1", "username": "admin",     "email": "admin@company.com",     "role": "admin",     "is_active": True },
    "manager":   { "id": "2", "username": "manager",   "email": "manager@company.com",   "role": "manager",   "is_active": True },
    "hr":        { "id": "3", "username": "hr",        "email": "hr@company.com",        "role": "hr",        "is_active": True },
    "employee":  { "id": "4", "username": "employee",  "email": "employee@company.com",  "role": "employee",  "is_active": True },
    "candidate": { "id": "5", "username": "candidate", "email": "candidate@company.com", "role": "candidate", "is_active": True },
}

def _is_mock_token(token: str) -> bool:
    env = os.getenv("ENVIRONMENT", "development").lower()
    return env != "production" and token.startswith("mock_token_")

def _resolve_mock_user(token: str) -> dict[str, Any] | None:
    # token shape: "mock_token_<role>"
    role = token[len("mock_token_"):]
    return _MOCK_USERS.get(role)

# ---------------------------------------------------------------------------
# Private error helpers
# ---------------------------------------------------------------------------
def _unauthorized(message: str) -> HTTPException:
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
    if credentials is None:
        raise _unauthorized("Authorization header is missing.")

    token = credentials.credentials

    # --- Dev mock bypass ---
    if _is_mock_token(token):
        mock_user = _resolve_mock_user(token)
        if mock_user is None:
            raise _unauthorized(f"Unknown mock role in token: '{token}'")
        logger.debug("Mock auth bypass — user: %s", mock_user["username"])
        return mock_user

    # --- Real JWT path ---
    try:
        payload = decode_token(token)
    except ValueError as exc:
        raise _unauthorized(str(exc))

    user_id: str | None = payload.get("sub")

    if not user_id:
        raise _unauthorized("Token payload is missing the 'sub' claim.")
    try:
        user = _repo.get_user_by_id(user_id)
    except ValueError:
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
    """
    async def _guard(
        current_user: dict[str, Any] = Depends(get_current_active_user),
    ) -> dict[str, Any]:
        if not has_permission(current_user.get("role", ""), permission):
            raise _forbidden(
                f"Role '{current_user.get('role')}' does not have "
                f"permission '{permission.value}'."
            )
        return current_user
    return _guard