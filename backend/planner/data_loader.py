import json
import os

from models import (
    HireEmployeeParams,
    OnboardEmployeeParams,
    SalesOutreachParams,
    PerformanceReviewParams,
)


# ==========================================================
# MOCK DATA LOCATION
# ==========================================================

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "mock_data"
)


# ==========================================================
# FILE HELPERS
# ==========================================================

def _load(filename: str) -> list[dict]:
    with open(
        os.path.join(DATA_DIR, filename),
        "r",
        encoding="utf-8"
    ) as f:
        return json.load(f)


def _save(filename: str, data: list[dict]) -> None:
    with open(
        os.path.join(DATA_DIR, filename),
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(data, f, indent=2)


# ==========================================================
# READ FUNCTIONS
# ==========================================================

def get_employee(employee_name: str) -> dict:

    employees = _load("employees.json")

    for emp in employees:
        if emp["employee_name"].lower() == employee_name.lower():
            return emp

    raise ValueError(
        f"Employee '{employee_name}' not found"
    )


def get_role_info(
    department: str,
    role: str
) -> dict:

    departments = _load("departments.json")

    for dept in departments:

        if dept["department"].lower() == department.lower():

            for r in dept["roles"]:

                if r["role"].lower() == role.lower():

                    return {
                        "experience_years": r["experience_years"],
                        "skills_required": r["skills_required"],
                        "location": dept["location"],
                        "rating_scale": dept["rating_scale"],
                        "salary_range": r.get(
                            "salary_range",
                            "To be decided"
                        ),
                        "onboarding_checklist": r.get(
                            "onboarding_checklist",
                            []
                        ),
                    }

    raise ValueError(
        f"Role '{role}' not found"
    )


def get_goals(
    employee_name: str,
    review_period: str
) -> dict:

    goals = _load("goals.json")

    for goal in goals:

        if (
            goal["employee_name"].lower()
            == employee_name.lower()
            and
            goal["review_period"].lower()
            == review_period.lower()
        ):

            return {
                "goals_set": goal["goals_set"],
                "goals_achieved": goal["goals_achieved"]
            }

    raise ValueError(
        f"Goals not found for '{employee_name}'"
    )


def get_product(product_name: str) -> dict:

    products = _load("products.json")

    if not product_name:
        return products[0]

    for product in products:

        if (
            product["product_name"].lower()
            == product_name.lower()
        ):
            return product

    raise ValueError(
        f"Product '{product_name}' not found"
    )


def get_candidates(role: str) -> list[dict]:

    candidates = _load("candidates.json")

    return [
        candidate
        for candidate in candidates
        if candidate["role_applied"].lower()
        == role.lower()
    ]


# ==========================================================
# WRITE FUNCTIONS
# ==========================================================

def add_employee(employee: dict) -> None:

    employees = _load("employees.json")

    employees.append(employee)

    _save(
        "employees.json",
        employees
    )


# ==========================================================
# PARAMETER ENRICHMENT
# ==========================================================

def enrich_hire_params(
    params: HireEmployeeParams
) -> HireEmployeeParams:

    role_info = get_role_info(
        params.department,
        params.role
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
    params: OnboardEmployeeParams
) -> OnboardEmployeeParams:

    employee = get_employee(
        params.employee_name
    )

    params.role = employee["role"]
    params.department = employee["department"]
    params.joining_date = employee["joining_date"]
    params.manager_name = employee["manager_name"]
    params.work_mode = employee["work_mode"]

    return params


def enrich_sales_params(
    params: SalesOutreachParams
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
    params: PerformanceReviewParams
) -> PerformanceReviewParams:

    employee = get_employee(
        params.employee_name
    )

    params.role = employee["role"]
    params.department = employee["department"]

    goals = get_goals(
        params.employee_name,
        params.review_period
    )

    params.goals_set = goals[
        "goals_set"
    ]

    params.goals_achieved = goals[
        "goals_achieved"
    ]

    role_info = get_role_info(
        employee["department"],
        employee["role"]
    )

    params.rating_scale = role_info[
        "rating_scale"
    ]

    return params