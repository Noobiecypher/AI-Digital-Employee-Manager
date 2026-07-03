"""
business_routes.py
==================
FastAPI APIRouter for all business data CRUD endpoints.

Registered in main.py under the '/api' prefix:

    app.include_router(
        business_router,
        prefix="/api",
        tags=["business-data"],
    )

This router is completely isolated from routes.py (workflow router).
No workflow logic, no workflow imports, no shared mutable state.
All MongoDB access is delegated exclusively to BusinessDataRepository.

Endpoint surface
----------------
Employees  (5):  GET /api/employees
                 GET /api/employees/{employee_id}
                 POST /api/employees
                 PUT /api/employees/{employee_id}
                 DELETE /api/employees/{employee_id}

Candidates (5):  GET /api/candidates
                 GET /api/candidates/{candidate_id}
                 POST /api/candidates
                 PUT /api/candidates/{candidate_id}
                 DELETE /api/candidates/{candidate_id}

Products   (5):  GET /api/products
                 GET /api/products/{product_name}
                 POST /api/products
                 PUT /api/products/{product_name}
                 DELETE /api/products/{product_name}

Goals      (5):  GET /api/goals
                 GET /api/goals/{employee_name}/{review_period}
                 POST /api/goals
                 PUT /api/goals/{employee_name}/{review_period}
                 DELETE /api/goals/{employee_name}/{review_period}

Roles      (5):  GET /api/roles
                 GET /api/roles/{role}
                 POST /api/roles
                 PUT /api/roles/{role}
                 DELETE /api/roles/{role}

URL encoding note — Goals composite key
----------------------------------------
employee_name and review_period are passed as URL path segments.
Any spaces must be percent-encoded by the client:

    "Alice Johnson" → Alice%20Johnson
    "Q2 2026"       → Q2%202026

Full example:
    GET /api/goals/Alice%20Johnson/Q2%202026

FastAPI decodes these automatically before passing them to the handler.
review_period values containing literal forward-slashes are not supported
as path parameters; use only alphanumeric characters, spaces, and hyphens.

Error contract  (mirrors routes.py exactly)
-------------------------------------------
    404  ENTITY_NOT_FOUND     — requested entity does not exist
    409  CONFLICT             — duplicate business key on create
    422  VALIDATION_ERROR     — Pydantic rejected the request body
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

from fastapi import APIRouter, HTTPException, Response, status

from fastapi import Depends

from backend.auth.dependencies import require_permission
from backend.auth.permissions import Permission
from backend.auth.ownership import (
    can_access_employee,
    can_access_candidate,
    can_access_goal,
)

from backend.database.business_data_repository import BusinessDataRepository
from backend.api.business_schemas import (
    # Employees
    EmployeeCreateRequest,
    EmployeeUpdateRequest,
    EmployeeResponse,
    EmployeeListResponse,
    # Candidates
    CandidateCreateRequest,
    CandidateUpdateRequest,
    CandidateResponse,
    CandidateListResponse,
    # Products
    ProductCreateRequest,
    ProductUpdateRequest,
    ProductResponse,
    ProductListResponse,
    # Goals
    GoalCreateRequest,
    GoalUpdateRequest,
    GoalResponse,
    GoalAchievementUpdateRequest,
    GoalReviewRequest,
    GoalListResponse,
    GoalUpdateHistoryResponse,
    GoalUpdateHistoryListResponse,
    # Roles
    RoleCreateRequest,
    RoleUpdateRequest,
    RoleResponse,
    RoleListResponse,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Router and repository singletons.
# Collection resolution inside the repository is lazy — no DB call happens
# at import time, so the lifespan startup hook remains the single point of
# connection verification.
# ---------------------------------------------------------------------------

business_router = APIRouter()
_repo = BusinessDataRepository()


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def error_response(
    status_code: int,
    code: str,
    message: str,
    field: str | None = None,
) -> HTTPException:
    """
    Build a structured HTTPException that matches the project error contract.

    Intentionally duplicated from routes.py to keep both routers fully
    self-contained; importing across router modules would couple the
    workflow and business layers unnecessarily.

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
    Empty lists are intentional and are preserved: passing [] for a list
    field explicitly clears that list in the database via $set.

    Args:
        data: Raw dict produced by UpdateRequest.model_dump().

    Returns:
        Dict containing only keys whose values are not None.
    """
    return {k: v for k, v in data.items() if v is not None}


# ===========================================================================
# EMPLOYEES
# ===========================================================================

@business_router.get(
    "/employees",
    response_model=EmployeeListResponse,
    summary="List all employees",
    description=(
        "Return every employee document sorted by employee_id ascending. "
        "The `total` field reflects the full collection size."
    ),
)
async def list_employees(
    current_user: dict = Depends(
        require_permission(
            Permission.EMPLOYEES_READ
        )
    ),
) -> EmployeeListResponse:
    
    """Retrieve all employees from the employees collection."""
    try:
        employees = _repo.list_employees()
    except RuntimeError as exc:
        logger.error("list_employees route error: %s", exc)
        raise error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_SERVER_ERROR",
            str(exc),
        )
    
    if current_user["role"] == "employee":

        employees = [
            e
            for e in employees
            if (
                e["employee_id"]
                ==
                current_user.get("employee_id")
            )
        ]

    return EmployeeListResponse(
        total=len(employees),
        items=[EmployeeResponse(**e) for e in employees],
    )


@business_router.get(
    "/employees/{employee_id}",
    response_model=EmployeeResponse,
    summary="Get a single employee by ID",
    description=(
        "Return one employee document looked up by its business key "
        "(e.g. 'EMP001'). employee_id matching is case-sensitive."
    ),
)
async def get_employee(
    employee_id: str,
    current_user: dict = Depends(
        require_permission(
            Permission.EMPLOYEES_READ
        )
    ),
) -> EmployeeResponse:
    
    """Retrieve a single employee by business key."""

    if not can_access_employee(
        current_user,
        employee_id,
    ):
        raise error_response(
            status.HTTP_403_FORBIDDEN,
            "FORBIDDEN",
            "You may only access your own employee profile."
        )
    
    try:
        employee = _repo.get_employee(employee_id)
    except ValueError as exc:
        raise error_response(
            status.HTTP_404_NOT_FOUND,
            "ENTITY_NOT_FOUND",
            str(exc),
            "employee_id",
        )
    except RuntimeError as exc:
        logger.error("get_employee('%s') route error: %s", employee_id, exc)
        raise error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_SERVER_ERROR",
            str(exc),
        )

    return EmployeeResponse(**employee)


@business_router.post(
    "/employees",
    response_model=EmployeeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new employee",
    description=(
        "Insert a new employee record. `employee_id` must be unique across "
        "the collection (case-sensitive). Returns 409 if the id is already "
        "taken."
    ),
)
async def create_employee(
    body: EmployeeCreateRequest,
    _: dict = Depends(
        require_permission(
            Permission.EMPLOYEES_CREATE
        )
    ),
) -> EmployeeResponse:
    
    """Create a new employee. Returns 409 if employee_id already exists."""
    try:
        employee = _repo.create_employee(body.model_dump())
    except ValueError as exc:
        msg = str(exc)
        if "already exist" in msg:
            raise error_response(
                status.HTTP_409_CONFLICT,
                "CONFLICT",
                msg,
                "employee_id",
            )
        raise error_response(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "VALIDATION_ERROR",
            msg,
        )
    except RuntimeError as exc:
        logger.error("create_employee route error: %s", exc)
        raise error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_SERVER_ERROR",
            str(exc),
        )

    return EmployeeResponse(**employee)


@business_router.put(
    "/employees/{employee_id}",
    response_model=EmployeeResponse,
    summary="Update an employee",
    description=(
        "Partially update an employee record. Only supplied (non-null) fields "
        "are written; omitted fields are left untouched. `employee_id` is "
        "immutable and cannot be changed via this endpoint."
    ),
)
async def update_employee(
    employee_id: str,
    body: EmployeeUpdateRequest,
    _: dict = Depends(
        require_permission(
            Permission.EMPLOYEES_UPDATE
        )
    ),
) -> EmployeeResponse:
    
    """Partially update an existing employee. Returns 404 if not found."""
    updates = _clean_updates(body.model_dump())

    try:
        employee = _repo.update_employee(employee_id, updates)
    except ValueError as exc:
        raise error_response(
            status.HTTP_404_NOT_FOUND,
            "ENTITY_NOT_FOUND",
            str(exc),
            "employee_id",
        )
    except RuntimeError as exc:
        logger.error(
            "update_employee('%s') route error: %s",
            employee_id,
            exc,
        )
        raise error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_SERVER_ERROR",
            str(exc),
        )

    return EmployeeResponse(**employee)


@business_router.delete(
    "/employees/{employee_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an employee",
    description=(
        "Permanently remove an employee record by business key. "
        "Returns 204 No Content on success, 404 if the employee does not exist."
    ),
)
async def delete_employee(
    employee_id: str,
    _: dict = Depends(
        require_permission(
            Permission.EMPLOYEES_DELETE
        )
    ),
) -> Response:
    
    """Delete an employee by business key. Returns 204 on success."""
    try:
        _repo.delete_employee(employee_id)
    except ValueError as exc:
        raise error_response(
            status.HTTP_404_NOT_FOUND,
            "ENTITY_NOT_FOUND",
            str(exc),
            "employee_id",
        )
    except RuntimeError as exc:
        logger.error(
            "delete_employee('%s') route error: %s",
            employee_id,
            exc,
        )
        raise error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_SERVER_ERROR",
            str(exc),
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ===========================================================================
# CANDIDATES
# ===========================================================================

@business_router.get(
    "/candidates",
    response_model=CandidateListResponse,
    summary="List all candidates",
    description=(
        "Return every candidate document sorted by name ascending. "
        "Each response item includes resume extensibility fields "
        "(resume_filename, resume_url, resume_uploaded_at), which are null "
        "until the future resume-upload endpoint populates them."
    ),
)
async def list_candidates(
    current_user: dict = Depends(
        require_permission(
            Permission.CANDIDATES_READ
        )
),
) -> CandidateListResponse:
    
    """Retrieve all candidates from the candidates collection."""
    try:
        candidates = _repo.list_candidates()
    except RuntimeError as exc:
        logger.error("list_candidates route error: %s", exc)
        raise error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_SERVER_ERROR",
            str(exc),
        )
    
    if current_user["role"] == "candidate":

        candidates = [
            c
            for c in candidates
            if (
                c["candidate_id"]
                ==
                current_user.get("candidate_id")
            )
        ]

    return CandidateListResponse(
        total=len(candidates),
        items=[CandidateResponse(**c) for c in candidates],
    )


@business_router.get(
    "/candidates/{candidate_id}",
    response_model=CandidateResponse,
    summary="Get a single candidate by ID",
    description=(
        "Return one candidate document by its server-generated UUID4 "
        "candidate_id. The response includes resume extensibility fields."
    ),
)
async def get_candidate(
    candidate_id: str,
    current_user: dict = Depends(
        require_permission(
            Permission.CANDIDATES_READ
        )
    ),                    
) -> CandidateResponse:
    
    """Retrieve a single candidate by UUID candidate_id."""

    if not can_access_candidate(
        current_user,
        candidate_id,
    ):
        raise error_response(
            status.HTTP_403_FORBIDDEN,
            "FORBIDDEN",
            "You may only access your own candidate profile."
        )

    try:
        candidate = _repo.get_candidate(candidate_id)
    except ValueError as exc:
        raise error_response(
            status.HTTP_404_NOT_FOUND,
            "ENTITY_NOT_FOUND",
            str(exc),
            "candidate_id",
        )
    except RuntimeError as exc:
        logger.error(
            "get_candidate('%s') route error: %s",
            candidate_id,
            exc,
        )
        raise error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_SERVER_ERROR",
            str(exc),
        )

    return CandidateResponse(**candidate)


@business_router.post(
    "/candidates",
    response_model=CandidateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new candidate",
    description=(
        "Insert a new candidate record. A UUID4 candidate_id is generated "
        "server-side and returned in the response. Resume fields are "
        "initialised to null and can be populated later via the "
        "dedicated resume-upload endpoint."
    ),
)
async def create_candidate(
    body: CandidateCreateRequest,
    _: dict = Depends(
        require_permission(
            Permission.CANDIDATES_CREATE
        )
    ),
) -> CandidateResponse:
    
    """
    Create a new candidate. candidate_id is server-generated (UUID4).

    The response includes resume_filename, resume_url, and
    resume_uploaded_at — all null on creation, populated by the future
    POST /api/candidates/{candidate_id}/resume endpoint.
    """
    try:
        candidate = _repo.create_candidate(body.model_dump())
    except RuntimeError as exc:
        logger.error("create_candidate route error: %s", exc)
        raise error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_SERVER_ERROR",
            str(exc),
        )

    return CandidateResponse(**candidate)


@business_router.put(
    "/candidates/{candidate_id}",
    response_model=CandidateResponse,
    summary="Update a candidate",
    description=(
        "Partially update a candidate record. Only non-null fields are "
        "written. The following fields are intentionally excluded from "
        "updates: `candidate_id` (immutable UUID), `match_score` "
        "(managed by the recruitment workflow agent), and `resume_*` "
        "fields (managed by the future resume-upload endpoint)."
    ),
)
async def update_candidate(
    candidate_id: str,
    body: CandidateUpdateRequest,
    _: dict = Depends(
        require_permission(
            Permission.CANDIDATES_UPDATE
        )
    ),
) -> CandidateResponse:
    """Partially update an existing candidate. Returns 404 if not found."""
    updates = _clean_updates(body.model_dump())

    try:
        candidate = _repo.update_candidate(candidate_id, updates)
    except ValueError as exc:
        raise error_response(
            status.HTTP_404_NOT_FOUND,
            "ENTITY_NOT_FOUND",
            str(exc),
            "candidate_id",
        )
    except RuntimeError as exc:
        logger.error(
            "update_candidate('%s') route error: %s",
            candidate_id,
            exc,
        )
        raise error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_SERVER_ERROR",
            str(exc),
        )

    return CandidateResponse(**candidate)


@business_router.delete(
    "/candidates/{candidate_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a candidate",
    description=(
        "Permanently remove a candidate record by UUID candidate_id. "
        "Returns 204 No Content on success."
    ),
)
async def delete_candidate(
    candidate_id: str,
    _: dict = Depends(
        require_permission(
            Permission.CANDIDATES_DELETE
        )
    ),
) -> Response:
    """Delete a candidate by UUID. Returns 204 on success."""
    try:
        _repo.delete_candidate(candidate_id)
    except ValueError as exc:
        raise error_response(
            status.HTTP_404_NOT_FOUND,
            "ENTITY_NOT_FOUND",
            str(exc),
            "candidate_id",
        )
    except RuntimeError as exc:
        logger.error(
            "delete_candidate('%s') route error: %s",
            candidate_id,
            exc,
        )
        raise error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_SERVER_ERROR",
            str(exc),
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ===========================================================================
# PRODUCTS
# ===========================================================================

@business_router.get(
    "/products",
    response_model=ProductListResponse,
    summary="List all products",
    description=(
        "Return every product document sorted by product_name ascending. "
        "Products are also consumed by the sales_outreach workflow for "
        "pain-point enrichment — changes here are immediately visible to "
        "the next workflow run."
    ),
)
async def list_products(
    _: dict = Depends(
        require_permission(
            Permission.PRODUCTS_READ
        )
),
) -> ProductListResponse:
    """Retrieve all products from the products collection."""
    try:
        products = _repo.list_products()
    except RuntimeError as exc:
        logger.error("list_products route error: %s", exc)
        raise error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_SERVER_ERROR",
            str(exc),
        )

    return ProductListResponse(
        total=len(products),
        items=[ProductResponse(**p) for p in products],
    )


@business_router.get(
    "/products/{product_name}",
    response_model=ProductResponse,
    summary="Get a single product by name",
    description=(
        "Return one product document. `product_name` lookup is "
        "case-insensitive, mirroring the convention used by "
        "data_loader.get_product(). URL-encode spaces as %20."
    ),
)
async def get_product(
    product_name: str,
    _: dict = Depends(
        require_permission(
            Permission.PRODUCTS_READ
        )
    ),
) -> ProductResponse:
    """Retrieve a single product by product_name (case-insensitive)."""
    try:
        product = _repo.get_product(product_name)
    except ValueError as exc:
        raise error_response(
            status.HTTP_404_NOT_FOUND,
            "ENTITY_NOT_FOUND",
            str(exc),
            "product_name",
        )
    except RuntimeError as exc:
        logger.error(
            "get_product('%s') route error: %s",
            product_name,
            exc,
        )
        raise error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_SERVER_ERROR",
            str(exc),
        )

    return ProductResponse(**product)


@business_router.post(
    "/products",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new product",
    description=(
        "Insert a new product record. `product_name` must be unique "
        "(case-insensitive). Returns 409 if a product with the same "
        "name already exists."
    ),
)
async def create_product(
    body: ProductCreateRequest,
    _: dict = Depends(
        require_permission(
            Permission.PRODUCTS_CREATE
        )
    ),
) -> ProductResponse:
    """Create a new product. Returns 409 if product_name already exists."""
    try:
        product = _repo.create_product(body.model_dump())
    except ValueError as exc:
        msg = str(exc)
        if "already exist" in msg:
            raise error_response(
                status.HTTP_409_CONFLICT,
                "CONFLICT",
                msg,
                "product_name",
            )
        raise error_response(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "VALIDATION_ERROR",
            msg,
        )
    except RuntimeError as exc:
        logger.error("create_product route error: %s", exc)
        raise error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_SERVER_ERROR",
            str(exc),
        )

    return ProductResponse(**product)


@business_router.put(
    "/products/{product_name}",
    response_model=ProductResponse,
    summary="Update a product",
    description=(
        "Partially update a product record. Only non-null fields are "
        "written. `product_name` is the immutable URL key and cannot be "
        "changed via this endpoint. Pass `[]` for list fields to clear them."
    ),
)
async def update_product(
    product_name: str,
    body: ProductUpdateRequest,
    _: dict = Depends(
        require_permission(
            Permission.PRODUCTS_UPDATE
        )
    ),
) -> ProductResponse:
    """Partially update an existing product. Returns 404 if not found."""
    updates = _clean_updates(body.model_dump())

    try:
        product = _repo.update_product(product_name, updates)
    except ValueError as exc:
        raise error_response(
            status.HTTP_404_NOT_FOUND,
            "ENTITY_NOT_FOUND",
            str(exc),
            "product_name",
        )
    except RuntimeError as exc:
        logger.error(
            "update_product('%s') route error: %s",
            product_name,
            exc,
        )
        raise error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_SERVER_ERROR",
            str(exc),
        )

    return ProductResponse(**product)


@business_router.delete(
    "/products/{product_name}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a product",
    description=(
        "Permanently remove a product record. Returns 204 No Content on "
        "success. Warning: deleting a product that is referenced by active "
        "sales_outreach workflows will cause those workflows to fail on "
        "the enrichment step."
    ),
)
async def delete_product(
    product_name: str,
    _: dict = Depends(
        require_permission(
            Permission.PRODUCTS_DELETE
        )
    ),
) -> Response:
    """Delete a product by name. Returns 204 on success."""
    try:
        _repo.delete_product(product_name)
    except ValueError as exc:
        raise error_response(
            status.HTTP_404_NOT_FOUND,
            "ENTITY_NOT_FOUND",
            str(exc),
            "product_name",
        )
    except RuntimeError as exc:
        logger.error(
            "delete_product('%s') route error: %s",
            product_name,
            exc,
        )
        raise error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_SERVER_ERROR",
            str(exc),
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ===========================================================================
# GOALS
# ===========================================================================

@business_router.get(
    "/goals",
    response_model=GoalListResponse,
    summary="List all goals",
    description=(
        "Return every goal document across all employees and review periods, "
        "sorted by employee_name then review_period ascending."
    ),
)
async def list_goals(
    current_user: dict = Depends(
        require_permission(
            Permission.GOALS_READ
        )
),
) -> GoalListResponse:
    """Retrieve all goal documents from the goals collection."""
    try:
        goals = _repo.list_goals()
    except RuntimeError as exc:
        logger.error("list_goals route error: %s", exc)
        raise error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_SERVER_ERROR",
            str(exc),
        )
    
    if current_user["role"] == "employee":

        goals = [
            g
            for g in goals
            if (
                g["employee_name"].lower()
                ==
                current_user.get(
                    "employee_name",
                    ""
                ).lower()
            )
        ]

    return GoalListResponse(
        total=len(goals),
        items=[GoalResponse(**g) for g in goals],
    )


@business_router.get(
    "/goals/{employee_name}/{review_period}",
    response_model=GoalResponse,
    summary="Get goals for an employee and review period",
    description=(
        "Return the goal document for a specific employee / review-period "
        "combination. Both path segments are matched case-insensitively. "
        "URL-encode spaces as %20 — e.g. "
        "`GET /api/goals/Alice%20Johnson/Q2%202026`. "
        "review_period values containing forward-slashes are not supported."
    ),
)
async def get_goal(
    employee_name: str,
    review_period: str,
    current_user: dict = Depends(
        require_permission(
            Permission.GOALS_READ
        )
    ),
) -> GoalResponse:
    """
    Retrieve goals for a specific employee and review period.

    Both path parameters are URL-decoded by FastAPI before lookup.
    The repository applies case-insensitive matching, so
    'alice johnson' and 'Alice Johnson' resolve to the same document.
    """
    if not can_access_goal(
        current_user,
        employee_name,
    ):
        raise error_response(
            status.HTTP_403_FORBIDDEN,
            "FORBIDDEN",
            "You may only access your own goals."
        )
    try:
        goal = _repo.get_goal(employee_name, review_period)
    except ValueError as exc:
        raise error_response(
            status.HTTP_404_NOT_FOUND,
            "ENTITY_NOT_FOUND",
            str(exc),
        )
    except RuntimeError as exc:
        logger.error(
            "get_goal('%s', '%s') route error: %s",
            employee_name,
            review_period,
            exc,
        )
        raise error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_SERVER_ERROR",
            str(exc),
        )

    return GoalResponse(**goal)


@business_router.post(
    "/goals",
    response_model=GoalResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a goal record",
    description=(
        "Insert a new goal document. The composite key "
        "(employee_name, review_period) must be unique. Returns 409 if a "
        "goal document for the same employee and period already exists. "
        "Goals created here are immediately visible to the "
        "performance_review workflow."
    ),
)
async def create_goal(
    body: GoalCreateRequest,
    _: dict = Depends(
        require_permission(
            Permission.GOALS_CREATE
        )
    ),
) -> GoalResponse:
    """
    Create a goal record for an employee / review-period combination.

    Returns 409 if goals for this employee and period already exist.
    The document shape matches data_loader.get_goals() exactly, so the
    performance_review workflow can consume it without any transformation.
    """
    try:
        goal = _repo.create_goal(body.model_dump())
    except ValueError as exc:
        msg = str(exc)
        if "already exist" in msg:
            raise error_response(
                status.HTTP_409_CONFLICT,
                "CONFLICT",
                msg,
            )
        raise error_response(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "VALIDATION_ERROR",
            msg,
        )
    except RuntimeError as exc:
        logger.error("create_goal route error: %s", exc)
        raise error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_SERVER_ERROR",
            str(exc),
        )

    return GoalResponse(**goal)


@business_router.put(
    "/goals/{employee_name}/{review_period}",
    response_model=GoalResponse,
    summary="Update goals for an employee and review period",
    description=(
        "Partially update a goal document. Only `goals_set` and "
        "`goals_achieved` may be changed — the composite key "
        "(employee_name, review_period) is immutable. "
        "Omit a field to leave it unchanged; pass `[]` to clear it. "
        "URL-encode spaces as %20."
    ),
)
async def update_goal(
    employee_name: str,
    review_period: str,
    body: GoalUpdateRequest,
    _: dict = Depends(
        require_permission(
            Permission.GOALS_UPDATE
        )
    ),
) -> GoalResponse:
    """
    Partially update goals for an employee / review-period combination.

    Partial update semantics:
      - Omit field (null)   → field unchanged in DB
      - Pass []             → field cleared (list set to empty)
      - Pass non-empty list → field fully replaced
    """
    updates = _clean_updates(body.model_dump())

    try:
        goal = _repo.update_goal(employee_name, review_period, updates)
    except ValueError as exc:
        raise error_response(
            status.HTTP_404_NOT_FOUND,
            "ENTITY_NOT_FOUND",
            str(exc),
        )
    except RuntimeError as exc:
        logger.error(
            "update_goal('%s', '%s') route error: %s",
            employee_name,
            review_period,
            exc,
        )
        raise error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_SERVER_ERROR",
            str(exc),
        )

    return GoalResponse(**goal)

@business_router.post(
    "/goals/{employee_name}/{review_period}/request-update",
    response_model=GoalResponse,
)
async def request_goal_achievement_update(
    employee_name: str,
    review_period: str,
    body: GoalAchievementUpdateRequest,
    current_user: dict = Depends(
        require_permission(
            Permission.GOALS_UPDATE
        )
    ),
):

    if not can_access_goal(
        current_user,
        employee_name,
    ):
        raise error_response(
            status.HTTP_403_FORBIDDEN,
            "FORBIDDEN",
            "You may only update your own goals.",
        )



    try:

        goal = _repo.request_goal_achievement_update(
            employee_name,
            review_period,
            body.goals_achieved,
        )

    except ValueError as exc:
        raise error_response(
            status.HTTP_404_NOT_FOUND,
            "ENTITY_NOT_FOUND",
            str(exc),
        )

    except RuntimeError as exc:
        raise error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_SERVER_ERROR",
            str(exc),
        )

    return GoalResponse(**goal)

@business_router.post(
    "/goals/{employee_name}/{review_period}/review",
    response_model=GoalResponse,
)
async def review_goal_update(
    employee_name: str,
    review_period: str,
    body: GoalReviewRequest,
    current_user: dict = Depends(
        require_permission(
            Permission.GOALS_UPDATE
        )
    ),
):

    if current_user["role"] not in [
        "manager",
        "admin",
        "hr",
    ]:
        raise error_response(
            status.HTTP_403_FORBIDDEN,
            "FORBIDDEN",
            "Only managers, HR and admins may review goal updates.",
        )

    try:

        goal = _repo.review_goal_update(
            employee_name=employee_name,
            review_period=review_period,
            approval_status=body.approval_status,
            approver=current_user["full_name"],
            manager_comments=body.manager_comments,
        )

    except ValueError as exc:
        raise error_response(
            status.HTTP_404_NOT_FOUND,
            "ENTITY_NOT_FOUND",
            str(exc),
        )

    except RuntimeError as exc:
        raise error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_SERVER_ERROR",
            str(exc),
        )

    return GoalResponse(**goal)


@business_router.get(
    "/goals/{employee_name}/{review_period}/history",
    response_model=
    GoalUpdateHistoryListResponse,
    summary="Get goal update history",
)
async def list_goal_update_history(
    employee_name: str,
    review_period: str,
    current_user: dict = Depends(
        require_permission(
            Permission.GOALS_READ
        )
    ),
):

    if not can_access_goal(
        current_user,
        employee_name,
    ):
        raise error_response(
            status.HTTP_403_FORBIDDEN,
            "FORBIDDEN",
            "You may only access your own goal history."
        )

    try:

        history = (
            _repo.list_goal_update_history(
                employee_name,
                review_period,
            )
        )

    except RuntimeError as exc:
        raise error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_SERVER_ERROR",
            str(exc),
        )

    return GoalUpdateHistoryListResponse(
        total=len(history),
        items=[
            GoalUpdateHistoryResponse(
                **item
            )
            for item in history
        ],
    )


@business_router.delete(
    "/goals/{employee_name}/{review_period}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete goals for an employee and review period",
    description=(
        "Permanently remove a goal document by composite key. "
        "Returns 204 No Content on success. "
        "URL-encode spaces as %20."
    ),
)
async def delete_goal(
    employee_name: str,
    review_period: str,
    _: dict = Depends(
        require_permission(
            Permission.GOALS_DELETE
        )
    ),
) -> Response:
    """Delete a goal document by composite key. Returns 204 on success."""
    try:
        _repo.delete_goal(employee_name, review_period)
    except ValueError as exc:
        raise error_response(
            status.HTTP_404_NOT_FOUND,
            "ENTITY_NOT_FOUND",
            str(exc),
        )
    except RuntimeError as exc:
        logger.error(
            "delete_goal('%s', '%s') route error: %s",
            employee_name,
            review_period,
            exc,
        )
        raise error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_SERVER_ERROR",
            str(exc),
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ===========================================================================
# ROLES
# ===========================================================================

@business_router.get(
    "/roles",
    response_model=RoleListResponse,
    summary="List all roles",
    description=(
        "Return every role document sorted by department then role name "
        "ascending. Roles are used by the workflow engine for "
        "parameter enrichment and can be managed through the CRUD API. "
        "Changes made here are immediately visible to future workflow runs."
    ),
)
async def list_roles(
    _: dict = Depends(
        require_permission(
            Permission.BUSINESS_ROLES_READ
        )
    ),
) -> RoleListResponse:
    """Retrieve all role documents."""
    try:
        roles = _repo.list_roles()
    except RuntimeError as exc:
        logger.error("list_roles route error: %s", exc)
        raise error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_SERVER_ERROR",
            str(exc),
        )

    return RoleListResponse(
        total=len(roles),
        items=[RoleResponse(**r) for r in roles],
    )


@business_router.post(
    "/roles",
    response_model=RoleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new role",
    description=(
        "Insert a new role document. The role name acts as the "
        "business key and must be unique (case-insensitive). "
        "New roles become immediately available to workflow execution."
    ),
)
async def create_role(
    body: RoleCreateRequest,
    _: dict = Depends(
        require_permission(
            Permission.BUSINESS_ROLES_CREATE
        )
    ),
) -> RoleResponse:

    try:
        role = _repo.create_role(body.model_dump())

    except ValueError as exc:
        raise error_response(
            status.HTTP_409_CONFLICT,
            "CONFLICT",
            str(exc),
            "role",
        )

    except RuntimeError as exc:
        raise error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_SERVER_ERROR",
            str(exc),
        )

    return RoleResponse(**role)


@business_router.get(
    "/roles/{role}",
    response_model=RoleResponse,
    summary="Get a single role by name",
    description=(
        "Return one role document by role name. "
        "Role lookup is case-insensitive. "
        "URL-encode spaces as %20."
    ), 
)
async def get_role(
    role: str,
    _: dict = Depends(
        require_permission(
            Permission.BUSINESS_ROLES_READ
        )
    ),
) -> RoleResponse:

    try:
        role_doc = _repo.get_role(role)

    except ValueError as exc:
        raise error_response(
            status.HTTP_404_NOT_FOUND,
            "ENTITY_NOT_FOUND",
            str(exc),
            "role",
        )

    except RuntimeError as exc:
        raise error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_SERVER_ERROR",
            str(exc),
        )

    return RoleResponse(**role_doc)


@business_router.put(
    "/roles/{role}",
    response_model=RoleResponse,
    summary="Update a role",
    description=(
        "Partially update a role document. "
        "Only non-null fields are written. "
        "The role name is the immutable business key and "
        "cannot be changed via this endpoint."
    ),    
)
async def update_role(
    role: str,
    body: RoleUpdateRequest,
    _: dict = Depends(
        require_permission(
            Permission.BUSINESS_ROLES_UPDATE
        )
    ),
) -> RoleResponse:

    updates = _clean_updates(body.model_dump())

    try:
        role_doc = _repo.update_role(
            role,
            updates,
        )

    except ValueError as exc:
        raise error_response(
            status.HTTP_404_NOT_FOUND,
            "ENTITY_NOT_FOUND",
            str(exc),
            "role",
        )

    except RuntimeError as exc:
        raise error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_SERVER_ERROR",
            str(exc),
        )

    return RoleResponse(**role_doc)


@business_router.delete(
    "/roles/{role}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a role",
    description=(
        "Permanently remove a role document by role name. "
        "Returns 204 No Content on success. "
        "Warning: deleting roles referenced by active workflows "
        "may cause future workflow executions to fail."
    ),
)
async def delete_role(
    role: str,
    _: dict = Depends(
        require_permission(
            Permission.BUSINESS_ROLES_DELETE
        )
    ),
) -> Response:

    try:
        _repo.delete_role(role)

    except ValueError as exc:
        raise error_response(
            status.HTTP_404_NOT_FOUND,
            "ENTITY_NOT_FOUND",
            str(exc),
            "role",
        )

    except RuntimeError as exc:
        raise error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_SERVER_ERROR",
            str(exc),
        )

    return Response(
        status_code=status.HTTP_204_NO_CONTENT
    )
