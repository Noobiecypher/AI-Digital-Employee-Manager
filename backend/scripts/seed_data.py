#!/usr/bin/env python3
"""
seed_data.py
============
Seeds MongoDB collections from the mock JSON data files.

Usage
-----
    python -m backend.scripts.seed_data
    # or directly:
    python backend/scripts/seed_data.py

Behaviour
---------
- Reads every JSON source file from backend/mock_data/.
- Clears the target collection with delete_many({}) before inserting,
  making each run idempotent — safe to execute multiple times without
  producing duplicate documents.
- departments.json is flattened: each nested role becomes one document
  in the 'roles' collection, carrying its parent department's 'location'
  and 'rating_scale' fields alongside its own fields. This matches the
  query shape expected by data_loader.get_role_info().
- All other JSON files are inserted as-is (one array element per document).

Collections produced
--------------------
    employees   ← employees.json
    roles       ← departments.json  (flattened — one doc per role)
    goals       ← goals.json
    products    ← products.json
    candidates  ← candidates.json
    reports     ← reports.json
"""

import json
import os
import sys

# ---------------------------------------------------------------------------
# Path setup — allows running as a script from any working directory
# without requiring the package to be installed.
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_SCRIPTS_DIR)
_PROJECT_ROOT = os.path.dirname(_BACKEND_DIR)

if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from backend.database.mongo import (
    get_employees_collection,
    get_roles_collection,
    get_goals_collection,
    get_products_collection,
    get_candidates_collection,
    get_reports_collection,
)

# ---------------------------------------------------------------------------
# JSON source location
# ---------------------------------------------------------------------------

_DATA_DIR = os.path.join(_BACKEND_DIR, "mock_data")


def _load(filename: str) -> list[dict]:
    """Load a JSON file from the mock_data directory."""
    path = os.path.join(_DATA_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Seed functions — one per collection
# ---------------------------------------------------------------------------

def seed_employees() -> None:
    """
    Seed the 'employees' collection from employees.json.

    Clears the collection first so re-runs are safe.
    """
    data = _load("employees.json")
    col  = get_employees_collection()

    col.delete_many({})

    if data:
        col.insert_many(data)

    print(f"[employees]  seeded {len(data)} document(s).")


def seed_roles() -> None:
    """
    Seed the 'roles' collection by flattening departments.json.

    departments.json has a nested structure:
        [ { department, location, rating_scale, roles: [ {role, ...}, ... ] } ]

    Each nested role is expanded into a flat document:
        {
            department,        # from parent
            location,          # from parent
            rating_scale,      # from parent
            role,
            experience_years,
            skills_required,
            salary_range,      # defaults to "To be decided" if absent
            onboarding_checklist,  # defaults to [] if absent
        }

    This shape is queried directly by data_loader.get_role_info().
    Clears the collection first so re-runs are safe.
    """
    departments = _load("departments.json")
    col         = get_roles_collection()

    col.delete_many({})

    role_docs: list[dict] = []

    for dept in departments:
        for role in dept["roles"]:
            doc = {
                # Parent department fields
                "department":  dept["department"],
                "location":    dept["location"],
                "rating_scale": dept["rating_scale"],
                # Role-level fields
                "role":               role["role"],
                "experience_years":   role["experience_years"],
                "skills_required":    role["skills_required"],
                "salary_range":       role.get(
                    "salary_range",
                    "To be decided"
                ),
                "onboarding_checklist": role.get(
                    "onboarding_checklist",
                    []
                ),
            }
            role_docs.append(doc)

    if role_docs:
        col.insert_many(role_docs)

    print(f"[roles]      seeded {len(role_docs)} document(s) "
          f"from {len(departments)} department(s).")


def seed_goals() -> None:
    """
    Seed the 'goals' collection from goals.json.

    Clears the collection first so re-runs are safe.
    """
    data = _load("goals.json")
    col  = get_goals_collection()

    col.delete_many({})

    if data:
        col.insert_many(data)

    print(f"[goals]      seeded {len(data)} document(s).")


def seed_products() -> None:
    """
    Seed the 'products' collection from products.json.

    Clears the collection first so re-runs are safe.
    """
    data = _load("products.json")
    col  = get_products_collection()

    col.delete_many({})

    if data:
        col.insert_many(data)

    print(f"[products]   seeded {len(data)} document(s).")


def seed_candidates() -> None:
    """
    Seed the 'candidates' collection from candidates.json.

    Clears the collection first so re-runs are safe.
    """
    data = _load("candidates.json")
    col  = get_candidates_collection()

    col.delete_many({})

    if data:
        col.insert_many(data)

    print(f"[candidates] seeded {len(data)} document(s).")


def seed_reports() -> None:
    """
    Seed the 'reports' collection from reports.json.

    Clears the collection first so re-runs are safe.
    """
    data = _load("reports.json")
    col = get_reports_collection()

    col.delete_many({})

    if data:
        if isinstance(data, list):
            col.insert_many(data)
        else:
            col.insert_one(data)

    count = len(data) if isinstance(data, list) else 1

    print(
        f"[reports]    seeded {count} document(s)."
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_all() -> None:
    """Run all seed functions in dependency order."""
    print("Starting MongoDB seed...\n")

    seed_employees()
    seed_roles()
    seed_goals()
    seed_products()
    seed_candidates()
    seed_reports()

    print("\nSeeding complete.")

    print(
        "\nCollections seeded:\n"
        "- employees\n"
        "- roles\n"
        "- goals\n"
        "- products\n"
        "- candidates\n"
        "- reports"
    )


if __name__ == "__main__":
    run_all()
