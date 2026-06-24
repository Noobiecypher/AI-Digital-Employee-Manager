import re

from backend.models import (
    HireEmployeeParams,
    OnboardEmployeeParams,
    SalesOutreachParams,
    PerformanceReviewParams,
)

from backend.database.mongo import (
    get_employees_collection,
    get_roles_collection,
    get_goals_collection,
    get_products_collection,
    get_candidates_collection,
)


# ==========================================================
# READ FUNCTIONS
#
# Every function queries MongoDB directly on each call.
# No module-level state. No preloading. No caching.
# Frontend writes to MongoDB collections are immediately
# visible to the next function call.
#
# _id is excluded from every query result via {"_id": 0}
# projection so returned dicts are identical in shape to
# the original JSON-loaded dicts.
#
# Case-insensitive matching uses $regex with ^ and $ anchors
# + $options:"i" — mirrors the original .lower() comparisons
# exactly. re.escape() prevents special characters in caller-
# supplied strings from being interpreted as regex operators.
# ==========================================================

def get_employee(employee_name: str) -> dict:
    """
    Retrieve an employee document by employee name.

    Performs case-insensitive exact matching.

    Raises:
        ValueError: If employee is not found.
    """

    collection = get_employees_collection()

    employee = collection.find_one(
        {
            "employee_name": {
                "$regex": f"^{re.escape(employee_name)}$",
                "$options": "i",
            }
        },
        {"_id": 0},
    )

    if employee is None:
        raise ValueError(
            f"Employee '{employee_name}' not found"
        )

    return employee


def get_role_info(
    department: str,
    role: str,
) -> dict:

    collection = get_roles_collection()

    doc = collection.find_one(
        {
            "department": {
                "$regex": f"^{re.escape(department)}$",
                "$options": "i",
            },
            "role": {
                "$regex": f"^{re.escape(role)}$",
                "$options": "i",
            },
        },
        {"_id": 0},
    )

    if doc is None:
        raise ValueError(
            f"Role '{role}' not found"
        )

    return {
        "experience_years": doc["experience_years"],
        "skills_required":  doc["skills_required"],
        "location":         doc["location"],
        "rating_scale":     doc["rating_scale"],
        "salary_range":     doc.get(
            "salary_range",
            "To be decided"
        ),
        "onboarding_checklist": doc.get(
            "onboarding_checklist",
            []
        ),
    }


def get_goals(
    employee_name: str,
    review_period: str,
) -> dict:

    collection = get_goals_collection()

    goal = collection.find_one(
        {
            "employee_name": {
                "$regex": f"^{re.escape(employee_name)}$",
                "$options": "i",
            },
            "review_period": {
                "$regex": f"^{re.escape(review_period)}$",
                "$options": "i",
            },
        },
        {"_id": 0},
    )

    if goal is None:
        raise ValueError(
            f"Goals not found for '{employee_name}'"
        )

    return {
        "goals_set":      goal["goals_set"],
        "goals_achieved": goal["goals_achieved"],
    }


def get_product(product_name: str) -> dict:

    collection = get_products_collection()

    if not product_name:
        products = list(
            collection.find({}, {"_id": 0})
        )

        product = products[0] if products else None

    else:
        product = collection.find_one(
            {
                "product_name": {
                    "$regex": f"^{re.escape(product_name)}$",
                    "$options": "i",
                }
            },
            {"_id": 0},
        )

    if product is None:
        raise ValueError(
            f"Product '{product_name}' not found"
        )

    return product


def get_candidates(role: str) -> list[dict]:

    collection = get_candidates_collection()

    return list(
        collection.find(
            {
                "role_applied": {
                    "$regex": f"^{re.escape(role)}$",
                    "$options": "i",
                }
            },
            {"_id": 0},
        )
    )


# ==========================================================
# WRITE FUNCTIONS
# ==========================================================

def add_employee(employee: dict) -> None:
    """
    Persist a new employee document.

    Inserts a shallow copy so the caller's
    dictionary is never mutated by PyMongo.
    """

    collection = get_employees_collection()

    # Insert a shallow copy so pymongo's in-place _id injection
    # never mutates the caller's original dict — identical
    # externally-visible behaviour to the JSON append-and-save.
    collection.insert_one({**employee})


# ==========================================================
# PARAMETER ENRICHMENT
#
# These functions are unchanged from the JSON implementation.
# They call the same helper functions above; those helpers now
# query MongoDB instead of reading files. Agents see no
# difference.
# ==========================================================

def enrich_hire_params(
    params: HireEmployeeParams,
) -> HireEmployeeParams:

    role_info = get_role_info(
        params.department,
        params.role,
    )

    params.experience_years = role_info[
        "experience_years"
    ]

    params.skills_required = role_info[
        "skills_required"
    ]

    params.location = role_info[
        "location"
    ]

    params.salary_range = role_info[
        "salary_range"
    ]

    return params


def enrich_onboard_params(
    params: OnboardEmployeeParams,
) -> OnboardEmployeeParams:

    employee = get_employee(
        params.employee_name
    )

    params.role         = employee["role"]
    params.department   = employee["department"]
    params.joining_date = employee["joining_date"]
    params.manager_name = employee["manager_name"]
    params.work_mode    = employee["work_mode"]

    return params


def enrich_sales_params(
    params: SalesOutreachParams,
) -> SalesOutreachParams:

    product = get_product(
        params.product_name
    )

    params.product_name = product[
        "product_name"
    ]

    params.pain_points = product[
        "pain_points"
    ]

    return params


def enrich_review_params(
    params: PerformanceReviewParams,
) -> PerformanceReviewParams:

    employee = get_employee(
        params.employee_name
    )

    params.role       = employee["role"]
    params.department = employee["department"]

    goals = get_goals(
        params.employee_name,
        params.review_period,
    )

    params.goals_set      = goals["goals_set"]
    params.goals_achieved = goals["goals_achieved"]

    role_info = get_role_info(
        employee["department"],
        employee["role"],
    )

    params.rating_scale = role_info[
        "rating_scale"
    ]

    return params