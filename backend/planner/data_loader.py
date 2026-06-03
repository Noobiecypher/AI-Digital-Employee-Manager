import json
import os

# Path to mock data folder
DATA_DIR = os.path.join(os.path.dirname(__file__), "mock_data")


def _load(filename: str) -> list[dict]:
    """Load a JSON file from mock_data folder."""
    with open(os.path.join(DATA_DIR, filename), "r") as f:
        return json.load(f)


# ─────────────────────────────────────────
# LOOKUP FUNCTIONS
# ─────────────────────────────────────────

def get_employee(employee_name: str) -> dict:
    """
    Fetch employee record by name.
    Raises ValueError if not found.
    """
    employees = _load("employees.json")
    for emp in employees:
        if emp["employee_name"].lower() == employee_name.lower():
            return emp
    raise ValueError(f"Employee '{employee_name}' not found in employees.json")


def get_role_info(department: str, role: str) -> dict:
    """
    Fetch role-specific info (experience_years, skills_required)
    from departments.json for a given department + role.
    Raises ValueError if department or role not found.
    """
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
                    }
            raise ValueError(f"Role '{role}' not found in department '{department}'")
    raise ValueError(f"Department '{department}' not found in departments.json")


def get_goals(employee_name: str, review_period: str) -> dict:
    """
    Fetch goals for an employee in a specific review period.
    Raises ValueError if not found.
    """
    goals = _load("goals.json")
    for g in goals:
        if (g["employee_name"].lower() == employee_name.lower()
                and g["review_period"].lower() == review_period.lower()):
            return {
                "goals_set": g["goals_set"],
                "goals_achieved": g["goals_achieved"],
            }
    raise ValueError(
        f"Goals for '{employee_name}' in period '{review_period}' not found in goals.json"
    )


def get_product(product_name: str) -> dict:
    """
    Fetch product info by name.
    Falls back to first product if name is empty.
    Raises ValueError if not found.
    """
    products = _load("products.json")
    if not product_name:
        return products[0]
    for p in products:
        if p["product_name"].lower() == product_name.lower():
            return p
    raise ValueError(f"Product '{product_name}' not found in products.json")


# ─────────────────────────────────────────
# WRITE FUNCTIONS
# These are called by Person 1/2 after
# workflows complete — NOT by the Planner.
# When a real DB is introduced, only the
# internals of these functions change.
# ─────────────────────────────────────────

def _save(filename: str, data: list[dict]) -> None:
    """Write updated data back to a JSON file."""
    with open(os.path.join(DATA_DIR, filename), "w") as f:
        json.dump(data, f, indent=2)


def add_employee(employee: dict) -> None:
    """
    Add a newly hired candidate to employees.json.
    Called at the end of the hire_employee workflow
    after offer is accepted and manager approves.

    Expected fields in employee dict:
      employee_name, role, department,
      joining_date, manager_name, work_mode

    Raises ValueError if employee already exists.
    """
    required_fields = ["employee_name", "role", "department",
                       "joining_date", "manager_name", "work_mode"]
    for field in required_fields:
        if field not in employee:
            raise ValueError(f"Missing required field '{field}' in employee data")

    employees = _load("employees.json")

    # Check for duplicates
    for emp in employees:
        if emp["employee_name"].lower() == employee["employee_name"].lower():
            raise ValueError(
                f"Employee '{employee['employee_name']}' already exists in employees.json"
            )

    employees.append(employee)
    _save("employees.json", employees)


def add_goals(goals: dict) -> None:
    """
    Add a new goals record for an employee and review period.
    Called when a new review cycle begins and goals are set.

    Expected fields in goals dict:
      employee_name, review_period, goals_set, goals_achieved

    Raises ValueError if record already exists for that
    employee + review_period combination.
    """
    required_fields = ["employee_name", "review_period",
                       "goals_set", "goals_achieved"]
    for field in required_fields:
        if field not in goals:
            raise ValueError(f"Missing required field '{field}' in goals data")

    all_goals = _load("goals.json")

    # Check for duplicates
    for g in all_goals:
        if (g["employee_name"].lower() == goals["employee_name"].lower()
                and g["review_period"].lower() == goals["review_period"].lower()):
            raise ValueError(
                f"Goals for '{goals['employee_name']}' in "
                f"'{goals['review_period']}' already exist in goals.json"
            )

    all_goals.append(goals)
    _save("goals.json", all_goals)
