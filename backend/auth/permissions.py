"""
permissions.py
==============
Single source of truth for system roles and permission-based authorisation.

Defines
-------
    SystemRole        — Enum of every valid system role (exactly five).
    Permission        — Enum of every granular permission in the system.
    ROLE_PERMISSIONS  — Mapping from each SystemRole to its frozenset of
                        permitted actions.
    has_permission()  — Helper consumed by auth dependencies to check access.

Authorization philosophy
------------------------
Route handlers MUST call ``has_permission()`` exclusively via
``Depends(require_permission(...))``. Route handlers MUST NEVER inspect
``current_user["role"]`` directly. This file is the only place where
role-to-permission relationships are defined.

System roles
------------
    admin      Full access to every permission in the system.
    manager    Broad read/write access; no delete or user management.
    hr         Candidate lifecycle + employee read/write; no products.
    employee   Own profile and own goals read-only (least-privilege).
    candidate  Own application data read-only (most-restricted).

Permission domains
------------------
    employees       CRUD for employee records.
    candidates      CRUD for candidate records.
    products        CRUD for product catalogue entries.
    goals           CRUD for performance goal records.
    business_roles  CRUD for HR business role definitions.
    workflows       Trigger and monitor workflow executions.
    analytics       Access reporting and analytics data.
    users           Admin-only system user account management.

Least-privilege notes
---------------------
- ``employee``  is granted EMPLOYEES_READ and EMPLOYEES_UPDATE so that
  own-profile and contact-info updates are possible; the service layer
  is responsible for enforcing that employees may only act on their
  own resource (fine-grained resource ownership is above this layer).
- ``candidate`` is granted only CANDIDATES_READ; own-resource enforcement
  is similarly delegated to the service layer.
"""

from __future__ import annotations

from enum import Enum


# ---------------------------------------------------------------------------
# System roles
# ---------------------------------------------------------------------------

class SystemRole(str, Enum):
    ADMIN     = "admin"
    MANAGER   = "manager"
    HR        = "hr"
    EMPLOYEE  = "employee"
    CANDIDATE = "candidate"


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------

class Permission(str, Enum):
    # ---- employees -------------------------------------------------------
    EMPLOYEES_READ   = "employees:read"
    EMPLOYEES_CREATE = "employees:create"
    EMPLOYEES_UPDATE = "employees:update"
    EMPLOYEES_DELETE = "employees:delete"

    # ---- candidates ------------------------------------------------------
    CANDIDATES_READ   = "candidates:read"
    CANDIDATES_CREATE = "candidates:create"
    CANDIDATES_UPDATE = "candidates:update"
    CANDIDATES_DELETE = "candidates:delete"

    # ---- products --------------------------------------------------------
    PRODUCTS_READ   = "products:read"
    PRODUCTS_CREATE = "products:create"
    PRODUCTS_UPDATE = "products:update"
    PRODUCTS_DELETE = "products:delete"

    # ---- goals -----------------------------------------------------------
    GOALS_READ   = "goals:read"
    GOALS_CREATE = "goals:create"
    GOALS_UPDATE = "goals:update"
    GOALS_DELETE = "goals:delete"

    # ---- business_roles --------------------------------------------------
    BUSINESS_ROLES_READ   = "business_roles:read"
    BUSINESS_ROLES_CREATE = "business_roles:create"
    BUSINESS_ROLES_UPDATE = "business_roles:update"
    BUSINESS_ROLES_DELETE = "business_roles:delete"

    # ---- workflows -------------------------------------------------------
    WORKFLOWS_READ    = "workflows:read"
    WORKFLOWS_CREATE  = "workflows:create"
    WORKFLOWS_APPROVE = "workflows:approve"

    # ---- analytics -------------------------------------------------------
    ANALYTICS_READ = "analytics:read"

    # ---- users (system account management — admin only) ------------------
    USERS_READ   = "users:read"
    USERS_CREATE = "users:create"
    USERS_UPDATE = "users:update"

    # ---- documents (Document Upload & AI Document Ingestion subsystem) ---
    DOCUMENTS_READ    = "documents:read"
    DOCUMENTS_UPLOAD  = "documents:upload"
    DOCUMENTS_PROCESS = "documents:process"
    DOCUMENTS_REVIEW  = "documents:review"
    DOCUMENTS_IMPORT  = "documents:import"
    DOCUMENTS_DELETE  = "documents:delete"


# ---------------------------------------------------------------------------
# Role → permission mapping
# ---------------------------------------------------------------------------

ROLE_PERMISSIONS: dict[SystemRole, frozenset[Permission]] = {

    SystemRole.ADMIN: frozenset(Permission),

    SystemRole.MANAGER: frozenset({
        Permission.EMPLOYEES_READ,
        Permission.EMPLOYEES_CREATE,
        Permission.EMPLOYEES_UPDATE,
        Permission.EMPLOYEES_DELETE,

        Permission.CANDIDATES_READ,
        Permission.CANDIDATES_CREATE,
        Permission.CANDIDATES_UPDATE,
        Permission.CANDIDATES_DELETE,

        Permission.PRODUCTS_READ,

        Permission.GOALS_READ,
        Permission.GOALS_CREATE,
        Permission.GOALS_UPDATE,
        Permission.GOALS_DELETE,

        Permission.BUSINESS_ROLES_READ,

        Permission.WORKFLOWS_READ,
        Permission.WORKFLOWS_CREATE,
        Permission.WORKFLOWS_APPROVE,

        Permission.ANALYTICS_READ,

        Permission.DOCUMENTS_READ,
        Permission.DOCUMENTS_UPLOAD,
        Permission.DOCUMENTS_PROCESS,
        Permission.DOCUMENTS_REVIEW,
        Permission.DOCUMENTS_IMPORT,
    }),

    SystemRole.HR: frozenset({
        Permission.EMPLOYEES_READ,
        Permission.EMPLOYEES_CREATE,
        Permission.EMPLOYEES_UPDATE,

        Permission.CANDIDATES_READ,
        Permission.CANDIDATES_CREATE,
        Permission.CANDIDATES_UPDATE,
        Permission.CANDIDATES_DELETE,

        Permission.GOALS_READ,
        Permission.GOALS_CREATE,
        Permission.GOALS_UPDATE,

        Permission.BUSINESS_ROLES_READ,

        Permission.WORKFLOWS_READ,
        Permission.WORKFLOWS_CREATE,
        Permission.WORKFLOWS_APPROVE,

        Permission.DOCUMENTS_READ,
        Permission.DOCUMENTS_UPLOAD,
        Permission.DOCUMENTS_PROCESS,
        Permission.DOCUMENTS_REVIEW,
        Permission.DOCUMENTS_IMPORT,
    }),

    SystemRole.EMPLOYEE: frozenset({
        Permission.EMPLOYEES_READ,
        Permission.GOALS_READ,
        Permission.GOALS_UPDATE,
    }),

    SystemRole.CANDIDATE: frozenset({
        Permission.CANDIDATES_READ,
    }),
}


# ---------------------------------------------------------------------------
# Public helper
# ---------------------------------------------------------------------------

def has_permission(role: SystemRole | str, permission: Permission) -> bool:
    if isinstance(role, str):
        try:
            role = SystemRole(role)
        except ValueError:
            return False
    return permission in ROLE_PERMISSIONS.get(role, frozenset())