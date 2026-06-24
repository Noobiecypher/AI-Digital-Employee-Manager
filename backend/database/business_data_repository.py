"""
business_data_repository.py
===========================
BusinessDataRepository — MongoDB persistence for business data collections.

This is the ONLY module that reads from or writes to:
    employees   — full CRUD
    candidates  — full CRUD  (candidate_id auto-generated as UUID4)
    products    — full CRUD  (product_name is the business key)
    goals       — full CRUD
    roles       — read-only  (managed by seed_data.py)

No other module constructs queries or touches these collections directly.

Layering contract
-----------------
    API business routes  →  BusinessDataRepository  →  MongoDB

The repository speaks exclusively in plain dicts and raises ValueError
for missing entities. It has no knowledge of HTTP, FastAPI, or frontend
response shapes.

MongoDB conventions
-------------------
- _id is NEVER exposed: every query uses {"_id": 0} projection, and
  every insert strips the injected _id before returning.
- employee_id  — caller-supplied business key (e.g. "EMP001").
- candidate_id — UUID4 string generated server-side on insert.
- product_name — caller-supplied unique name used as the URL key.
- No direct MongoClient construction; all collections resolved via mongo.py.

Resume extensibility
--------------------
create_candidate() injects three null fields into every new document:
    resume_filename, resume_url, resume_uploaded_at
These are populated by the future resume-upload endpoint:
    POST   /candidates/{candidate_id}/resume
    GET    /candidates/{candidate_id}/resume
    DELETE /candidates/{candidate_id}/resume
No schema migration is required when that feature ships.

Case-insensitive matching
-------------------------
product_name lookups use $regex / $options:"i" (re.escape applied),
mirroring the convention in data_loader.py. employee_id lookups use
exact string match (business keys are treated as case-sensitive tokens).

Dependency injection
--------------------
All five collections can be injected at construction time for unit tests:

    from mongomock import MongoClient as MockClient
    db = MockClient()["test"]
    repo = BusinessDataRepository(
        employees_collection=db["employees"],
        candidates_collection=db["candidates"],
        products_collection=db["products"],
        roles_collection=db["roles"],
        goals_collection=db["goals"],
    )

Omit any collection to have it resolved lazily via mongo.py on first use.

Recommended indexes (run once during provisioning)
---------------------------------------------------
    db.employees.create_index("employee_id", unique=True)
    db.candidates.create_index("candidate_id", unique=True)
    db.products.create_index("product_name")
    db.roles.create_index([("department", 1), ("role", 1)])
    db.goals.create_index([("employee_name", 1), ("review_period", 1)],unique=True)
    
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import Optional

from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from backend.database.mongo import (
    get_candidates_collection,
    get_employees_collection,
    get_products_collection,
    get_roles_collection,
    get_goals_collection,
)

logger = logging.getLogger(__name__)


class BusinessDataRepository:
    """
    All MongoDB CRUD operations for business data collections.

    Methods — Employees
    -------------------
    list_employees()                        → list[dict]
    get_employee(employee_id)               → dict
    create_employee(data)                   → dict
    update_employee(employee_id, updates)   → dict
    delete_employee(employee_id)            → None

    Methods — Candidates
    --------------------
    list_candidates()                         → list[dict]
    get_candidate(candidate_id)               → dict
    create_candidate(data)                    → dict
    update_candidate(candidate_id, updates)   → dict
    delete_candidate(candidate_id)            → None

    Methods — Products
    ------------------
    list_products()                           → list[dict]
    get_product(product_name)                 → dict
    create_product(data)                      → dict
    update_product(product_name, updates)     → dict
    delete_product(product_name)              → None

    Methods — Roles (read-only)
    ---------------------------
    list_roles()                              → list[dict]
    
    Methods — Goals
    ----------------
    list_goals()                                       → list[dict]
    get_goal(employee_name, review_period)             → dict
    create_goal(data)                                  → dict
    update_goal(employee_name, review_period, updates) → dict
    delete_goal(employee_name, review_period)          → None
    """

    def __init__(
        self,
        employees_collection: Optional[Collection] = None,
        candidates_collection: Optional[Collection] = None,
        products_collection: Optional[Collection] = None,
        roles_collection: Optional[Collection] = None,
        goals_collection: Optional[Collection] = None,
    ) -> None:
        """
        Args:
            employees_collection:  Injected pymongo Collection for employees.
                                   Resolved lazily via mongo.py if omitted.
            candidates_collection: Injected pymongo Collection for candidates.
                                   Resolved lazily via mongo.py if omitted.
            products_collection:   Injected pymongo Collection for products.
                                   Resolved lazily via mongo.py if omitted.
            roles_collection:      Injected pymongo Collection for roles.
                                   Resolved lazily via mongo.py if omitted.
            goals_collection:      Injected pymongo Collection for goals.
                                   Resolved lazily via mongo.py if omitted.                       
        """
        self._employees: Optional[Collection] = employees_collection
        self._candidates: Optional[Collection] = candidates_collection
        self._products: Optional[Collection] = products_collection
        self._roles: Optional[Collection] = roles_collection
        self._goals: Optional[Collection] = goals_collection

    # ------------------------------------------------------------------
    # Collection properties — lazy resolution via mongo.py getters.
    # Mirrors the @property pattern in WorkflowRepository.
    # ------------------------------------------------------------------

    @property
    def employees(self) -> Collection:
        """Resolve and cache the employees collection on first access."""
        if self._employees is None:
            self._employees = get_employees_collection()
        return self._employees

    @property
    def candidates(self) -> Collection:
        """Resolve and cache the candidates collection on first access."""
        if self._candidates is None:
            self._candidates = get_candidates_collection()
        return self._candidates

    @property
    def products(self) -> Collection:
        """Resolve and cache the products collection on first access."""
        if self._products is None:
            self._products = get_products_collection()
        return self._products

    @property
    def roles(self) -> Collection:
        """Resolve and cache the roles collection on first access."""
        if self._roles is None:
            self._roles = get_roles_collection()
        return self._roles
    
    @property
    def goals(self) -> Collection:
        """Resolve and cache the goals collection on first access."""
        if self._goals is None:
            self._goals = get_goals_collection()
        return self._goals
    
    # ==================================================================
    # PRIVATE HELPERS
    # ==================================================================

    @staticmethod
    def _case_insensitive_filter(field: str, value: str) -> dict:
        """
        Build a case-insensitive exact-match MongoDB filter.

        Uses $regex with re.escape() to prevent special characters
        in caller-supplied strings from being treated as regex operators.
        Mirrors the convention established in data_loader.py.

        Args:
            field: MongoDB document field name.
            value: The value to match (case-insensitive).

        Returns:
            PyMongo filter dict suitable for find_one / find / update_one.
        """
        return {
            field: {
                "$regex": f"^{re.escape(value)}$",
                "$options": "i",
            }
        }
    
    @staticmethod
    def _goal_filter(
        employee_name: str,
        review_period: str,
    ) -> dict:
        """Case-insensitive filter for goal documents."""
        return {
            "employee_name": {
                "$regex": f"^{re.escape(employee_name)}$",
                "$options": "i",
            },
            "review_period": {
                "$regex": f"^{re.escape(review_period)}$",
                "$options": "i",
            },
        }
    
    @staticmethod
    def _strip_id(document: dict) -> dict:
        """
        Return a copy of `document` with the '_id' key removed.

        Used after insert_one() to prevent PyMongo's in-place _id
        injection from leaking internal Mongo structure to callers.
        """
        return {k: v for k, v in document.items() if k != "_id"}

    # ==================================================================
    # EMPLOYEES
    # ==================================================================

    def list_employees(self) -> list[dict]:
        """
        Return all employee documents, sorted by employee_id ascending.

        Returns:
            List of employee dicts with _id excluded.

        Raises:
            RuntimeError: On any PyMongo failure.
        """
        try:
            return list(
                self.employees.find(
                    {},
                    {"_id": 0},
                    sort=[("employee_id", 1)],
                )
            )
        except PyMongoError as exc:
            logger.error("list_employees failed: %s", exc)
            raise RuntimeError(
                f"Failed to list employees: {exc}"
            ) from exc

    def get_employee(self, employee_id: str) -> dict:
        """
        Return a single employee by business key.

        employee_id matching is case-sensitive (EMP001 ≠ emp001)
        to preserve the business key convention.

        Args:
            employee_id: Business identifier (e.g. "EMP001").

        Returns:
            Employee dict with _id excluded.

        Raises:
            ValueError:   If no employee with that id exists.
            RuntimeError: On any PyMongo failure.
        """
        try:
            doc = self.employees.find_one(
                {"employee_id": employee_id},
                {"_id": 0},
            )
        except PyMongoError as exc:
            logger.error(
                "get_employee('%s') failed: %s",
                employee_id,
                exc,
            )
            raise RuntimeError(
                f"Failed to retrieve employee '{employee_id}': {exc}"
            ) from exc

        if doc is None:
            raise ValueError(f"Employee '{employee_id}' not found")

        return doc

    def create_employee(self, data: dict) -> dict:
        """
        Insert a new employee document.

        Performs a pre-insert uniqueness check on employee_id so the
        caller receives a clear ValueError (→ 409 Conflict) rather
        than a raw PyMongo DuplicateKeyError.

        Args:
            data: Dict produced from EmployeeCreateRequest.model_dump().
                  Must contain 'employee_id' as the unique business key.

        Returns:
            The inserted employee dict (without _id).

        Raises:
            ValueError:   If an employee with the same employee_id exists.
            RuntimeError: On any PyMongo failure.
        """
        employee_id: str = data["employee_id"]

        # Pre-check uniqueness before insert.
        try:
            existing = self.employees.find_one(
                {"employee_id": employee_id},
                {"_id": 0},
            )
        except PyMongoError as exc:
            logger.error(
                "create_employee pre-check failed for '%s': %s",
                employee_id,
                exc,
            )
            raise RuntimeError(
                f"Failed to create employee '{employee_id}': {exc}"
            ) from exc

        if existing is not None:
            raise ValueError(
                f"Employee with id '{employee_id}' already exists"
            )

        document = {**data}

        try:
            self.employees.insert_one(document)
        except PyMongoError as exc:
            logger.error(
                "create_employee insert failed for '%s': %s",
                employee_id,
                exc,
            )
            raise RuntimeError(
                f"Failed to create employee '{employee_id}': {exc}"
            ) from exc

        logger.debug("Employee '%s' created.", employee_id)
        return self._strip_id(document)

    def update_employee(
        self,
        employee_id: str,
        updates: dict,
    ) -> dict:
        """
        Apply partial updates to an existing employee via $set.

        Only keys present in `updates` are written; all unspecified
        fields are left untouched. Callers must strip None values before
        calling (business_routes._clean_updates handles this).
        employee_id is the immutable business key and is never written.

        Args:
            employee_id: Business identifier of the employee to update.
            updates:     Dict of field-value pairs to apply.
                         Should not contain 'employee_id'.

        Returns:
            The full updated employee dict (without _id).

        Raises:
            ValueError:   If no employee with that id exists.
            RuntimeError: On any PyMongo failure.
        """
        # Confirm existence first — surfaces 404 before attempting write.
        self.get_employee(employee_id)

        if not updates:
            # Nothing to write — return current state unchanged.
            return self.get_employee(employee_id)

        try:
            self.employees.update_one(
                {"employee_id": employee_id},
                {"$set": updates},
            )
        except PyMongoError as exc:
            logger.error(
                "update_employee('%s') failed: %s",
                employee_id,
                exc,
            )
            raise RuntimeError(
                f"Failed to update employee '{employee_id}': {exc}"
            ) from exc

        logger.debug(
            "Employee '%s' updated — fields: %s",
            employee_id,
            list(updates),
        )
        # Re-fetch to guarantee the returned dict reflects the DB state.
        return self.get_employee(employee_id)

    def delete_employee(self, employee_id: str) -> None:
        """
        Delete an employee by business key.

        Confirms existence before deleting so the caller always receives
        a ValueError (→ 404) when the entity is missing, rather than a
        silent no-op from delete_one.

        Args:
            employee_id: Business identifier of the employee to delete.

        Raises:
            ValueError:   If no employee with that id exists.
            RuntimeError: On any PyMongo failure.
        """
        self.get_employee(employee_id)  # raises ValueError if missing

        try:
            self.employees.delete_one({"employee_id": employee_id})
        except PyMongoError as exc:
            logger.error(
                "delete_employee('%s') failed: %s",
                employee_id,
                exc,
            )
            raise RuntimeError(
                f"Failed to delete employee '{employee_id}': {exc}"
            ) from exc

        logger.debug("Employee '%s' deleted.", employee_id)

    # ==================================================================
    # CANDIDATES
    # ==================================================================

    def list_candidates(self) -> list[dict]:
        """
        Return all candidate documents, sorted by name ascending.

        Returns:
            List of candidate dicts with _id excluded.
            Each document includes resume extensibility fields
            (resume_filename, resume_url, resume_uploaded_at), which
            will be non-null once the future upload endpoint is used.

        Raises:
            RuntimeError: On any PyMongo failure.
        """
        try:
            return list(
                self.candidates.find(
                    {},
                    {"_id": 0},
                    sort=[("name", 1)],
                )
            )
        except PyMongoError as exc:
            logger.error("list_candidates failed: %s", exc)
            raise RuntimeError(
                f"Failed to list candidates: {exc}"
            ) from exc

    def get_candidate(self, candidate_id: str) -> dict:
        """
        Return a single candidate by UUID candidate_id.

        Args:
            candidate_id: UUID4 string assigned on creation.

        Returns:
            Candidate dict with _id excluded (includes resume fields).

        Raises:
            ValueError:   If no candidate with that id exists.
            RuntimeError: On any PyMongo failure.
        """
        try:
            doc = self.candidates.find_one(
                {"candidate_id": candidate_id},
                {"_id": 0},
            )
        except PyMongoError as exc:
            logger.error(
                "get_candidate('%s') failed: %s",
                candidate_id,
                exc,
            )
            raise RuntimeError(
                f"Failed to retrieve candidate '{candidate_id}': {exc}"
            ) from exc

        if doc is None:
            raise ValueError(f"Candidate '{candidate_id}' not found")

        return doc

    def create_candidate(self, data: dict) -> dict:
        """
        Insert a new candidate document, generating a UUID4 candidate_id.

        The candidate_id is generated here and injected into the document
        before insertion so the caller always receives it in the response.

        Resume extensibility
        --------------------
        Three null fields are written to every new candidate document:
            resume_filename      — original file name once uploaded
            resume_url           — pre-signed / permanent retrieval URL
            resume_uploaded_at   — ISO 8601 UTC timestamp of last upload

        These fields are populated by the future endpoint:
            POST /candidates/{candidate_id}/resume

        By reserving them now, the frontend response contract is stable
        and no data migration is required when that feature ships.

        Args:
            data: Dict produced from CandidateCreateRequest.model_dump().
                  Must NOT contain 'candidate_id' (it is generated here).

        Returns:
            The inserted candidate dict with candidate_id set (no _id).

        Raises:
            RuntimeError: On any PyMongo failure.
        """
        document: dict = {
            # Generated UUID4 — never caller-supplied.
            "candidate_id": str(uuid.uuid4()),
            # Resume extensibility slots — null until upload endpoint populates them.
            "resume_filename": None,
            "resume_url": None,
            "resume_uploaded_at": None,
            # Caller-supplied fields (name, role_applied, skills, …).
            **data,
        }

        try:
            self.candidates.insert_one(document)
        except PyMongoError as exc:
            logger.error("create_candidate insert failed: %s", exc)
            raise RuntimeError(
                f"Failed to create candidate: {exc}"
            ) from exc

        logger.debug(
            "Candidate '%s' created — name: %s, role: %s",
            document["candidate_id"],
            data.get("name", ""),
            data.get("role_applied", ""),
        )
        return self._strip_id(document)

    def update_candidate(
        self,
        candidate_id: str,
        updates: dict,
    ) -> dict:
        """
        Apply partial updates to an existing candidate via $set.

        candidate_id is immutable. match_score is intentionally excluded
        from the CRUD update surface — it is managed by the workflow engine
        (recruitment agent) and must not be overwritten by frontend edits.

        Resume fields (resume_filename, resume_url, resume_uploaded_at)
        are updated only by the dedicated resume-upload endpoint, not here.

        Args:
            candidate_id: UUID4 of the candidate to update.
            updates:      Dict of mutable fields (None values pre-stripped).

        Returns:
            The full updated candidate dict (without _id).

        Raises:
            ValueError:   If no candidate with that id exists.
            RuntimeError: On any PyMongo failure.
        """
        self.get_candidate(candidate_id)  # raises ValueError if missing

        if not updates:
            return self.get_candidate(candidate_id)

        try:
            self.candidates.update_one(
                {"candidate_id": candidate_id},
                {"$set": updates},
            )
        except PyMongoError as exc:
            logger.error(
                "update_candidate('%s') failed: %s",
                candidate_id,
                exc,
            )
            raise RuntimeError(
                f"Failed to update candidate '{candidate_id}': {exc}"
            ) from exc

        logger.debug(
            "Candidate '%s' updated — fields: %s",
            candidate_id,
            list(updates),
        )
        return self.get_candidate(candidate_id)

    def delete_candidate(self, candidate_id: str) -> None:
        """
        Delete a candidate by UUID.

        Args:
            candidate_id: UUID4 of the candidate to delete.

        Raises:
            ValueError:   If no candidate with that id exists.
            RuntimeError: On any PyMongo failure.
        """
        self.get_candidate(candidate_id)  # raises ValueError if missing

        try:
            self.candidates.delete_one({"candidate_id": candidate_id})
        except PyMongoError as exc:
            logger.error(
                "delete_candidate('%s') failed: %s",
                candidate_id,
                exc,
            )
            raise RuntimeError(
                f"Failed to delete candidate '{candidate_id}': {exc}"
            ) from exc

        logger.debug("Candidate '%s' deleted.", candidate_id)

    # ==================================================================
    # PRODUCTS
    # ==================================================================

    def list_products(self) -> list[dict]:
        """
        Return all product documents, sorted by product_name ascending.

        Returns:
            List of product dicts with _id excluded.

        Raises:
            RuntimeError: On any PyMongo failure.
        """
        try:
            return list(
                self.products.find(
                    {},
                    {"_id": 0},
                    sort=[("product_name", 1)],
                )
            )
        except PyMongoError as exc:
            logger.error("list_products failed: %s", exc)
            raise RuntimeError(
                f"Failed to list products: {exc}"
            ) from exc

    def get_product(self, product_name: str) -> dict:
        """
        Return a single product by product_name (case-insensitive exact match).

        Uses $regex with re.escape() — mirrors data_loader.get_product().
        This means workflows that look up "HRTech Pro" will still find a
        document created as "hrtech pro" via the CRUD API.

        Args:
            product_name: Business identifier for the product.

        Returns:
            Product dict with _id excluded.

        Raises:
            ValueError:   If no product with that name exists.
            RuntimeError: On any PyMongo failure.
        """
        try:
            doc = self.products.find_one(
                self._case_insensitive_filter("product_name", product_name),
                {"_id": 0},
            )
        except PyMongoError as exc:
            logger.error(
                "get_product('%s') failed: %s",
                product_name,
                exc,
            )
            raise RuntimeError(
                f"Failed to retrieve product '{product_name}': {exc}"
            ) from exc

        if doc is None:
            raise ValueError(f"Product '{product_name}' not found")

        return doc

    def create_product(self, data: dict) -> dict:
        """
        Insert a new product document.

        Pre-checks for duplicate product_name (case-insensitive) so the
        caller receives a ValueError (→ 409 Conflict) rather than a raw
        PyMongo error.

        Args:
            data: Dict from ProductCreateRequest.model_dump().
                  Must contain 'product_name' as the unique key.

        Returns:
            The inserted product dict (without _id).

        Raises:
            ValueError:   If a product with the same name already exists.
            RuntimeError: On any PyMongo failure.
        """
        product_name: str = data["product_name"]

        try:
            existing = self.products.find_one(
                self._case_insensitive_filter("product_name", product_name),
                {"_id": 0},
            )
        except PyMongoError as exc:
            logger.error(
                "create_product pre-check failed for '%s': %s",
                product_name,
                exc,
            )
            raise RuntimeError(
                f"Failed to create product '{product_name}': {exc}"
            ) from exc

        if existing is not None:
            raise ValueError(
                f"Product '{product_name}' already exists"
            )

        document = {**data}

        try:
            self.products.insert_one(document)
        except PyMongoError as exc:
            logger.error(
                "create_product insert failed for '%s': %s",
                product_name,
                exc,
            )
            raise RuntimeError(
                f"Failed to create product '{product_name}': {exc}"
            ) from exc

        logger.debug("Product '%s' created.", product_name)
        return self._strip_id(document)

    def update_product(
        self,
        product_name: str,
        updates: dict,
    ) -> dict:
        """
        Apply partial updates to an existing product via $set.

        product_name is the immutable business key and must not appear
        in `updates` — the route layer enforces this via the schema.

        Args:
            product_name: Business identifier of the product to update.
            updates:      Dict of field-value pairs to apply (None-stripped).

        Returns:
            The full updated product dict (without _id).

        Raises:
            ValueError:   If no product with that name exists.
            RuntimeError: On any PyMongo failure.
        """
        self.get_product(product_name)  # raises ValueError if missing

        if not updates:
            return self.get_product(product_name)

        try:
            self.products.update_one(
                self._case_insensitive_filter("product_name", product_name),
                {"$set": updates},
            )
        except PyMongoError as exc:
            logger.error(
                "update_product('%s') failed: %s",
                product_name,
                exc,
            )
            raise RuntimeError(
                f"Failed to update product '{product_name}': {exc}"
            ) from exc

        logger.debug(
            "Product '%s' updated — fields: %s",
            product_name,
            list(updates),
        )
        return self.get_product(product_name)

    def delete_product(self, product_name: str) -> None:
        """
        Delete a product by product_name.

        Args:
            product_name: Business identifier of the product to delete.

        Raises:
            ValueError:   If no product with that name exists.
            RuntimeError: On any PyMongo failure.
        """
        self.get_product(product_name)  # raises ValueError if missing

        try:
            self.products.delete_one(
                self._case_insensitive_filter("product_name", product_name)
            )
        except PyMongoError as exc:
            logger.error(
                "delete_product('%s') failed: %s",
                product_name,
                exc,
            )
            raise RuntimeError(
                f"Failed to delete product '{product_name}': {exc}"
            ) from exc

        logger.debug("Product '%s' deleted.", product_name)

    # ==================================================================
    # ROLES  (read-only)
    # ==================================================================

    def list_roles(self) -> list[dict]:
        """
        Return all role documents, sorted by department then role ascending.

        Roles are read-only from the CRUD perspective — they are seeded by
        seed_data.py and consumed by data_loader.py for workflow parameter
        enrichment. This method exists solely to power the GET /roles
        endpoint for frontend dropdowns and form validation.

        Returns:
            List of role dicts with _id excluded.

        Raises:
            RuntimeError: On any PyMongo failure.
        """
        try:
            return list(
                self.roles.find(
                    {},
                    {"_id": 0},
                    sort=[
                        ("department", 1),
                        ("role", 1),
                    ],
                )
            )
        except PyMongoError as exc:
            logger.error("list_roles failed: %s", exc)
            raise RuntimeError(
                f"Failed to list roles: {exc}"
            ) from exc
        

    # ==================================================================
    # GOALS
    # ==================================================================

    def list_goals(self) -> list[dict]:
        """
        Return all goal documents, sorted by employee_name and
        review_period ascending.

        Returns:
            List of goal dicts with _id excluded.

        Raises:
            RuntimeError: On any PyMongo failure.
        """
        try:
            return list(
                self.goals.find(
                    {},
                    {"_id": 0},
                    sort=[
                        ("employee_name", 1),
                        ("review_period", 1),
                    ],
                )
            )
        except PyMongoError as exc:
            logger.error("list_goals failed: %s", exc)
            raise RuntimeError(
                f"Failed to list goals: {exc}"
            ) from exc


    def get_goal(
        self,
        employee_name: str,
        review_period: str,
    ) -> dict:
        """
        Return a single goal document identified by employee_name and
        review_period (case-insensitive exact match).

        Uses $regex with re.escape() — mirrors data_loader.get_goals().

        Args:
            employee_name: Employee whose goals are being retrieved.
            review_period: Review cycle (e.g. "Q2 2026").

        Returns:
            Goal document with _id excluded.

        Raises:
            ValueError:   If no goals exist for the employee and review period.
            RuntimeError: On any PyMongo failure.
        """
        try:
            doc = self.goals.find_one(
                self._goal_filter(
                    employee_name,
                    review_period,
                ),
                {"_id": 0},
            )

        except PyMongoError as exc:
            logger.error(
                "get_goal('%s', '%s') failed: %s",
                employee_name,
                review_period,
                exc,
            )

            raise RuntimeError(
                f"Failed to retrieve goals for '{employee_name}' "
                f"({review_period}): {exc}"
            ) from exc

        if doc is None:
            raise ValueError(
                f"Goals not found for '{employee_name}' "
                f"({review_period})"
            )

        return doc


    def create_goal(self, data: dict) -> dict:
        """
        Insert a new goal document.

        Pre-checks for duplicate goals using employee_name and
        review_period (case-insensitive) so the caller receives a
        ValueError (→ 409 Conflict) rather than a raw PyMongo error.

        Args:
            data: Dict from GoalCreateRequest.model_dump().
                Must contain 'employee_name' and 'review_period'
                as the unique business key.

        Returns:
            The inserted goal document (without _id).

        Raises:
            ValueError:   If goals for the same employee and review
                        period already exist.
            RuntimeError: On any PyMongo failure.
        """
        employee_name: str = data["employee_name"]
        review_period: str = data["review_period"]

        try:
            existing = self.goals.find_one(
                self._goal_filter(
                    employee_name,
                    review_period,
                ),
                {"_id": 0},
            )

        except PyMongoError as exc:
            logger.error(
                "create_goal pre-check failed for '%s' (%s): %s",
                employee_name,
                review_period,
                exc,
            )

            raise RuntimeError(
                f"Failed to create goals for '{employee_name}' "
                f"({review_period}): {exc}"
            ) from exc

        if existing is not None:
            raise ValueError(
                f"Goals for '{employee_name}' "
                f"({review_period}) already exist"
            )

        document = {**data}

        try:
            self.goals.insert_one(document)

        except PyMongoError as exc:
            logger.error(
                "create_goal insert failed for '%s' (%s): %s",
                employee_name,
                review_period,
                exc,
            )

            raise RuntimeError(
                f"Failed to create goals for '{employee_name}' "
                f"({review_period}): {exc}"
            ) from exc

        logger.debug(
            "Goals created for '%s' (%s).",
            employee_name,
            review_period,
        )

        return self._strip_id(document)


    def update_goal(
        self,
        employee_name: str,
        review_period: str,
        updates: dict,
    ) -> dict:
        """
        Apply partial updates to an existing goal document via $set.

        employee_name and review_period together form the immutable
        business key and must not appear in `updates` — the route
        layer enforces this via the schema.

        Args:
            employee_name: Employee whose goals are being updated.
            review_period: Review cycle identifier (e.g. "Q2 2026").
            updates:       Dict of field-value pairs to apply
                        (None-stripped).

        Returns:
            The full updated goal document (without _id).

        Raises:
            ValueError:   If no goal document exists for the employee
                        and review period.
            RuntimeError: On any PyMongo failure.
        """
        self.get_goal(
            employee_name,
            review_period,
        )

        if not updates:
            return self.get_goal(
                employee_name,
                review_period,
            )

        try:
            self.goals.update_one(
                self._goal_filter(
                    employee_name,
                    review_period,
                ),
                {"$set": updates},
            )

        except PyMongoError as exc:
            logger.error(
                "update_goal('%s', '%s') failed: %s",
                employee_name,
                review_period,
                exc,
            )

            raise RuntimeError(
                f"Failed to update goals for '{employee_name}' "
                f"({review_period}): {exc}"
            ) from exc

        logger.debug(
            "Goals for '%s' (%s) updated — fields: %s",
            employee_name,
            review_period,
            list(updates),
        )

        return self.get_goal(
            employee_name,
            review_period,
        )


    def delete_goal(
        self,
        employee_name: str,
        review_period: str,
    ) -> None:
        """
        Delete a goal document identified by employee_name and
        review_period.

        Args:
            employee_name: Employee whose goals are to be deleted.
            review_period: Review cycle identifier.

        Raises:
            ValueError:   If no matching goal document exists.
            RuntimeError: On any PyMongo failure.
        """
        self.get_goal(
            employee_name,
            review_period,
        )

        try:
            self.goals.delete_one(
                self._goal_filter(
                    employee_name,
                    review_period,
                )
            )

        except PyMongoError as exc:
            logger.error(
                "delete_goal('%s', '%s') failed: %s",
                employee_name,
                review_period,
                exc,
            )

            raise RuntimeError(
                f"Failed to delete goals for '{employee_name}' "
                f"({review_period}): {exc}"
            ) from exc

        logger.debug(
            "Goals for '%s' (%s) deleted.",
            employee_name,
            review_period,
        )