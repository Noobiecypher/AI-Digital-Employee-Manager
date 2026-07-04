"""
business_data_repository.py
===========================
BusinessDataRepository — MongoDB persistence for business data collections.

This is the ONLY module that reads from or writes to:
    employees   — full CRUD
    candidates  — full CRUD  (candidate_id auto-generated as UUID4)
    products    — full CRUD  (product_name is the business key)
    goals       — full CRUD
    roles       — full CRUD  (workflow configuration + enrichment data)

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
- role         — caller-supplied unique name used as the URL key.
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
product_name and role lookups use $regex / $options:"i"
(re.escape applied), mirroring the convention in data_loader.py.
employee_id lookups use exact string match (business keys are
treated as case-sensitive tokens).

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
from datetime import datetime, timezone
from typing import Optional

from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from backend.database.mongo import (
    get_candidates_collection,
    get_employees_collection,
    get_products_collection,
    get_roles_collection,
    get_goals_collection,
    get_goal_update_history_collection,
)

from backend.api.business_schemas import GoalStatus

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

    Methods — Roles
    ---------------
    list_roles()                → list[dict]
    get_role(role)              → dict
    create_role(data)           → dict
    update_role(role, updates)  → dict
    delete_role(role)           → None
    
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
        goal_update_history_collection: Optional[Collection] = None,
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
        self._goal_update_history: Optional[Collection] = goal_update_history_collection

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
    
    @property
    def goal_update_history(self) -> Collection:
        """
        Resolve and cache the goal update history
        collection on first access.
        """
        if self._goal_update_history is None:
            self._goal_update_history = (
                get_goal_update_history_collection()
            )

        return self._goal_update_history
    
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
    
    def find_entity_by_source_import_draft_id(
        self,
        draft_id: str,
    ) -> Optional[dict]:
        """
        Find the Candidate or Product materialized from one ImportDraft.

        This is an exact internal provenance lookup used only for
        import-operation idempotency. It is not business-level duplicate
        detection.

        Returns:
            None if no entity exists for the draft.

            Otherwise:
            {
                "target_business_entity": "candidate" | "product",
                "entity": {...},
            }

        Raises:
            RuntimeError: On MongoDB failure, or if the same draft ID
                          has materialized more than one business entity.
        """
        try:
            candidate = self.candidates.find_one(
                {"source_import_draft_id": draft_id},
                {"_id": 0},
            )
            product = self.products.find_one(
                {"source_import_draft_id": draft_id},
                {"_id": 0},
            )
        except PyMongoError as exc:
            logger.error(
                "Import provenance lookup failed for draft '%s': %s",
                draft_id,
                exc,
            )
            raise RuntimeError(
                f"Failed to look up business entity for import draft "
                f"'{draft_id}': {exc}"
            ) from exc

        if candidate is not None and product is not None:
            raise RuntimeError(
                f"Integrity/idempotency violation: import draft "
                f"'{draft_id}' materialized both a Candidate and a Product"
            )

        if candidate is not None:
            return {
                "target_business_entity": "candidate",
                "entity": candidate,
            }

        if product is not None:
            return {
                "target_business_entity": "product",
                "entity": product,
            }

        return None   


    def find_product_by_enrichment_draft_id(self, draft_id: str) -> Optional[dict]:
        """Return the Product already enriched by this draft, if any."""
        try:
            return self.products.find_one(
                {"source_enrichment_draft_ids": draft_id}, {"_id": 0}
            )
        except PyMongoError as exc:
            raise RuntimeError(
                f"Failed to check product enrichment provenance for '{draft_id}': {exc}"
            ) from exc

    def enrich_product_from_draft(
        self,
        product_name: str,
        final_data: dict,
        *,
        draft_id: str,
        document_id: str,
    ) -> dict:
        """Apply one reviewed Product final state exactly once."""
        current = self.get_product(product_name)
        if draft_id in current.get("source_enrichment_draft_ids", []):
            return current
        source_ids = list(dict.fromkeys([
            *(current.get("source_document_ids") or []), document_id,
        ]))
        enrichment_ids = list(dict.fromkeys([
            *(current.get("source_enrichment_draft_ids") or []), draft_id,
        ]))
        updates = {
            **final_data,
            "source_document_ids": source_ids,
            "source_enrichment_draft_ids": enrichment_ids,
        }
        try:
            result = self.products.update_one(
                {
                    **self._case_insensitive_filter("product_name", product_name),
                    "source_enrichment_draft_ids": {"$ne": draft_id},
                },
                {"$set": updates},
            )
        except PyMongoError as exc:
            raise RuntimeError(
                f"Failed to enrich product '{product_name}': {exc}"
            ) from exc
        if result.matched_count == 0:
            return self.get_product(product_name)
        return self.get_product(product_name)

    # ==================================================================
    # M6.6 — ENTITY-LINKED DOCUMENT ID RESOLUTION (read-only)
    # ==================================================================
    #
    # These three methods are the only entry points DocumentContextService
    # uses to discover which document IDs are trusted for a given business
    # entity. They do not validate documents themselves (existence, status,
    # type) — that is DocumentContextService's job. They only answer
    # "which document IDs does this business record currently claim?".

    def get_product_source_document_ids(self, product_name: str) -> list[str]:
        """
        Return the Product's approved source_document_ids (order preserved,
        as stored by enrich_product_from_draft). Empty list if the product
        has no linked documents.

        Raises:
            ValueError: If no product with that name exists.
        """
        product = self.get_product(product_name)
        return list(product.get("source_document_ids") or [])

    def get_goal_evidence_document_ids(
        self,
        employee_name: str,
        review_period: str,
    ) -> list[str]:
        """
        Return document IDs of all approved evidence attached to the exact
        Goal for employee_name + review_period (via document_evidence[]).
        Empty list if no evidence has been attached.

        Raises:
            ValueError: If no goal exists for employee_name + review_period.
        """
        goal = self.get_goal(employee_name, review_period)
        return [
            e["document_id"]
            for e in (goal.get("document_evidence") or [])
            if e.get("document_id")
        ]

    def get_candidate_source_document_ids(self, candidate_id: str) -> list[str]:
        """
        Return the Candidate's linked source/resume document IDs, if any.

        NOTE (M6.6 compatibility flag): the current candidate schema has no
        'source_document_ids' field populated by any importer in this
        codebase snapshot — only the future resume_filename/resume_url
        slots and the import-idempotency 'source_import_draft_id'. This
        method reads 'source_document_ids' defensively (returns [] if
        absent) so it activates automatically, with zero further M6.6
        changes, once the Business Import Service starts stamping that
        field on candidate creation (Candidate is create-only per M6.5).

        Raises:
            ValueError: If no candidate with that id exists.
        """
        candidate = self.get_candidate(candidate_id)
        return list(candidate.get("source_document_ids") or [])

    def add_goal_document_evidence(
        self,
        employee_name: str,
        review_period: str,
        evidence: dict,
    ) -> dict:
        """Append one approved evidence snapshot, idempotent by document_id."""
        self.get_goal(employee_name, review_period)
        document_id = evidence["document_id"]
        try:
            self.goals.update_one(
                {
                    **self._goal_filter(employee_name, review_period),
                    "document_evidence.document_id": {"$ne": document_id},
                },
                {"$push": {"document_evidence": evidence}},
            )
        except PyMongoError as exc:
            raise RuntimeError(
                f"Failed to attach document evidence to goals for "
                f"'{employee_name}' ({review_period}): {exc}"
            ) from exc
        return self.get_goal(employee_name, review_period)

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
    # ROLES 
    # ==================================================================

    def list_roles(self) -> list[dict]:
        """
        Return all role documents.

        Roles are stored as flat MongoDB documents and are used by
        workflow execution for parameter enrichment and validation.

        Returns:
            List of role documents sorted by department then role name.

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
        

    def get_role(self, role: str) -> dict:
        """
        Retrieve a single role document by role name.

        Role lookup is case-insensitive.

        Args:
            role: Role name.

        Returns:
            Role document without _id.

        Raises:
            ValueError: If the role does not exist.
            RuntimeError: On any PyMongo failure.
        """
        try:
            doc = self.roles.find_one(
                self._case_insensitive_filter("role", role),
                {"_id": 0},
            )
        except PyMongoError as exc:
            raise RuntimeError(
                f"Failed to retrieve role '{role}': {exc}"
            ) from exc

        if doc is None:
            raise ValueError(f"Role '{role}' not found")

        return doc


    def create_role(self, data: dict) -> dict:
        """
        Insert a new role document.

        Performs a case-insensitive uniqueness check on role.

        Args:
            data: Dict from RoleCreateRequest.model_dump().

        Returns:
            Inserted role document without _id.

        Raises:
            ValueError: If the role already exists.
            RuntimeError: On any PyMongo failure.
        """
        role = data["role"]

        existing = self.roles.find_one(
            self._case_insensitive_filter("role", role),
            {"_id": 0},
        )

        if existing is not None:
            raise ValueError(
                f"Role '{role}' already exists"
            )

        document = {**data}

        try:
            self.roles.insert_one(document)
        except PyMongoError as exc:
            raise RuntimeError(
                f"Failed to create role '{role}': {exc}"
            ) from exc

        return self._strip_id(document)
    

    def update_role(
        self,
        role: str,
        updates: dict,
    ) -> dict:
        
        """
        Apply partial updates to an existing role document.

        The role name is the immutable business key and must not
        appear in updates.

        Args:
            role: Role name.
            updates: Dict of field-value pairs to update.

        Returns:
            Updated role document without _id.

        Raises:
            ValueError: If the role does not exist.
            RuntimeError: On any PyMongo failure.
        """

        self.get_role(role)

        if not updates:
            return self.get_role(role)

        try:
            self.roles.update_one(
                self._case_insensitive_filter("role", role),
                {"$set": updates},
            )
        except PyMongoError as exc:
            raise RuntimeError(
                f"Failed to update role '{role}': {exc}"
            ) from exc

        return self.get_role(role)
    
    
    def delete_role(self, role: str) -> None:

        """
        Delete a role document by role name.

        Args:
            role: Role name.

        Raises:
            ValueError: If the role does not exist.
            RuntimeError: On any PyMongo failure.
        """

        self.get_role(role)

        try:
            self.roles.delete_one(
                self._case_insensitive_filter("role", role)
            )
        except PyMongoError as exc:
            raise RuntimeError(
                f"Failed to delete role '{role}': {exc}"
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
    

    def request_goal_achievement_update(
        self,
        employee_name: str,
        review_period: str,
        goals_achieved: list[str],
    ) -> dict:

        goal = self.get_goal(
            employee_name,
            review_period,
        )

        if (goal.get("status")== GoalStatus.PENDING_APPROVAL.value):
            raise ValueError(
                "A goal update request is already pending approval."
            )

        try:
            self.goals.update_one(
                self._goal_filter(
                    employee_name,
                    review_period,
                ),
                {
                    "$set": {
                        "pending_goal_update": {
                            "goals_achieved": goals_achieved
                        },
                        "status": GoalStatus.PENDING_APPROVAL.value,
                    }
                },
            )

        except PyMongoError as exc:
            raise RuntimeError(
                f"Failed to request goal update: {exc}"
            ) from exc

        return self.get_goal(
            employee_name,
            review_period,
        )
    
    def review_goal_update(
        self,
        employee_name: str,
        review_period: str,
        approval_status: str,
        approver: str,
        manager_comments: str | None = None,
    ) -> dict:

        goal = self.get_goal(
            employee_name,
            review_period,
        )

        pending = goal.get(
            "pending_goal_update"
        )

        history_document = {
        "employee_name": employee_name,
        "review_period": review_period,

        "requested_changes": pending,

        "review_status": approval_status,

        "reviewed_by": approver,

        "reviewed_at": (
            datetime.now(
                timezone.utc
            ).isoformat()
        ),

        "manager_comments": manager_comments,
    }

        if (
            goal.get("status")
            != GoalStatus.PENDING_APPROVAL.value
        ):
            raise ValueError(
                "No pending goal update exists."
            )

        if approval_status == "approved":

            existing_achievements = goal.get(
                "goals_achieved",
                []
            )

            new_achievements = pending.get(
                "goals_achieved",
                []
            )

            updated_achievements = list(
                dict.fromkeys(
                    existing_achievements + new_achievements
                )
            )

            updates = {
                "goals_achieved": updated_achievements,
                "status": GoalStatus.ACTIVE.value,
                "pending_goal_update": None,
                "approved_by": approver,
                "approved_at": (
                    datetime.now(
                        timezone.utc
                    ).isoformat()
                ),
                "manager_comments": manager_comments,
            }

        else:

            updates = {
                "status": GoalStatus.ACTIVE.value,
                "pending_goal_update": None,
                "approved_by": approver,
                "approved_at": (
                    datetime.now(
                        timezone.utc
                    ).isoformat()
                ),
                "manager_comments": manager_comments,
            }

        try:
            self.goal_update_history.insert_one(history_document)

            self.goals.update_one(
                self._goal_filter(
                    employee_name,
                    review_period,
                ),
                {
                    "$set": updates
                },
            )

        except PyMongoError as exc:
            raise RuntimeError(
                f"Failed to review goal update: {exc}"
            ) from exc

        return self.get_goal(
            employee_name,
            review_period,
        )
    
    def list_goal_update_history(
        self,
        employee_name: str,
        review_period: str,
    ) -> list[dict]:

        try:

            return list(
                self.goal_update_history.find(
                    self._goal_filter(
                        employee_name,
                        review_period,
                    ),
                    {"_id": 0},
                    sort=[
                        ("reviewed_at", -1)
                    ],
                )
            )

        except PyMongoError as exc:
            raise RuntimeError(
                f"Failed to retrieve goal history: {exc}"
            ) from exc

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