"""
business_schemas.py
===================
Pydantic request / response schemas for the business data CRUD APIs.

Used exclusively by business_routes.py. Workflow routes (routes.py) are
completely unaffected — they use only the schemas in schemas.py.

Design principles
-----------------
Request schemas  — ConfigDict(extra="forbid")
    Strict: any unknown field in the JSON body causes a 422 immediately,
    preventing silent data loss or accidental field injection.

Response schemas — ConfigDict(extra="ignore")
    Lenient: fields present in existing MongoDB seed documents that are
    not modelled here are silently dropped. This lets the API stabilise
    without being broken by future seed-data additions.

Update schemas   — all fields Optional / None
    Only supplied (non-None) values are forwarded to the repository as a
    $set patch. None fields are stripped by _clean_updates() in the route
    layer before the repository is called.  Empty lists ARE forwarded
    (they deliberately clear a list field).

Immutable keys
--------------
These identifier fields are intentionally absent from every Update schema:
    EmployeeUpdateRequest  — employee_id
    CandidateUpdateRequest — candidate_id, match_score (workflow-managed)
    ProductUpdateRequest   — product_name
    GoalUpdateRequest      — employee_name, review_period
    RoleUpdateRequest      — role

Resume extensibility
--------------------
CandidateResponse carries three nullable resume fields:
    resume_filename, resume_url, resume_uploaded_at
All are null on creation. The future upload endpoints will populate them:
    POST   /candidates/{candidate_id}/resume
    GET    /candidates/{candidate_id}/resume
    DELETE /candidates/{candidate_id}/resume
No schema change is required when those endpoints ship.

Schema index
------------
  Employees  : EmployeeCreateRequest, EmployeeUpdateRequest,
               EmployeeResponse, EmployeeListResponse
  Candidates : CandidateCreateRequest, CandidateUpdateRequest,
               CandidateResponse, CandidateListResponse
  Products   : ProductCreateRequest, ProductUpdateRequest,
               ProductResponse, ProductListResponse
  Roles      : RoleCreateRequest, RoleUpdateRequest,
               RoleResponse, RoleListResponse
  Goals      : GoalCreateRequest, GoalUpdateRequest,
               GoalResponse, GoalListResponse
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

# ==============================================================
# EMPLOYEES
# ==============================================================

class EmployeeCreateRequest(BaseModel):
    """
    Payload for POST /api/employees.

    employee_id is the caller-supplied business key (e.g. "EMP001").
    It must be unique across the employees collection; the repository
    performs a pre-insert uniqueness check and returns 409 on conflict.
    """

    model_config = ConfigDict(extra="forbid")

    employee_id: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Unique business identifier, e.g. 'EMP001'.",
        examples=["EMP042"],
    )
    employee_name: str = Field(
        ...,
        min_length=1,
        max_length=120,
        description="Full legal name of the employee.",
        examples=["Alice Johnson"],
    )
    role: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Job role / title.",
        examples=["Software Engineer"],
    )
    department: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Department the employee belongs to.",
        examples=["Engineering"],
    )
    joining_date: str = Field(
        ...,
        min_length=1,
        max_length=30,
        description="Start date in YYYY-MM-DD format.",
        examples=["2024-03-01"],
    )
    manager_name: str = Field(
        ...,
        min_length=1,
        max_length=120,
        description="Full name of the direct-line manager.",
        examples=["Bob Smith"],
    )
    work_mode: str = Field(
        ...,
        min_length=1,
        max_length=30,
        description="Working arrangement: 'remote', 'hybrid', or 'on-site'.",
        examples=["hybrid"],
    )


class EmployeeUpdateRequest(BaseModel):
    """
    Payload for PUT /api/employees/{employee_id}.

    All fields are optional. Only non-None fields are applied as a
    $set patch. employee_id is immutable and must not be supplied here.
    """

    model_config = ConfigDict(extra="forbid")

    employee_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
        description="Updated full name.",
    )
    role: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Updated job role / title.",
    )
    department: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Updated department.",
    )
    joining_date: str | None = Field(
        default=None,
        min_length=1,
        max_length=30,
        description="Updated start date (YYYY-MM-DD).",
    )
    manager_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
        description="Updated manager name.",
    )
    work_mode: str | None = Field(
        default=None,
        min_length=1,
        max_length=30,
        description="Updated work mode.",
    )


class EmployeeResponse(BaseModel):
    """
    Employee document returned to the frontend.
    Extra MongoDB fields beyond those listed here are silently ignored.
    """

    model_config = ConfigDict(extra="ignore")

    employee_id: str
    employee_name: str
    role: str
    department: str
    joining_date: str
    manager_name: str
    work_mode: str


class EmployeeListResponse(BaseModel):
    """Flat list of all employees."""

    total: int = Field(
        description="Total number of employee documents in the collection."
    )
    items: list[EmployeeResponse]


# ==============================================================
# CANDIDATES
# ==============================================================

class CandidateCreateRequest(BaseModel):
    """
    Payload for POST /api/candidates.

    candidate_id is NOT accepted — it is generated server-side as a
    UUID4 string by BusinessDataRepository.create_candidate().
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        ...,
        min_length=1,
        max_length=120,
        description="Full name of the candidate.",
        examples=["Jane Doe"],
    )
    role_applied: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Role the candidate is applying for.",
        examples=["Software Engineer"],
    )
    skills: list[str] = Field(
        default_factory=list,
        description="List of skill tags.",
        examples=[["Python", "FastAPI", "MongoDB"]],
    )
    experience_years: int = Field(
        default=0,
        ge=0,
        le=60,
        description="Total years of professional experience.",
        examples=[3],
    )
    email: str = Field(
        default="",
        max_length=254,
        description="Primary contact email address.",
        examples=["jane.doe@example.com"],
    )
    phone: str = Field(
        default="",
        max_length=30,
        description="Primary contact phone number.",
        examples=["+1-555-0100"],
    )


class CandidateUpdateRequest(BaseModel):
    """
    Payload for PUT /api/candidates/{candidate_id}.

    All fields are optional. Excluded fields are left untouched:
      - candidate_id  — immutable UUID4, never in the update body.
      - match_score   — managed exclusively by the workflow engine
                        (recruitment agent); CRUD cannot override it.
      - resume_*      — managed by the future resume-upload endpoint.
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
    )
    role_applied: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )
    skills: list[str] | None = Field(
        default=None,
        description=(
            "Replaces the entire skills list. "
            "Pass [] to clear all skills."
        ),
    )
    experience_years: int | None = Field(
        default=None,
        ge=0,
        le=60,
    )
    email: str | None = Field(
        default=None,
        max_length=254,
    )
    phone: str | None = Field(
        default=None,
        max_length=30,
    )


class CandidateResponse(BaseModel):
    """
    Candidate document returned to the frontend.

    Resume extensibility
    --------------------
    resume_filename, resume_url, and resume_uploaded_at are always
    present in the response (nullable). They default to null on
    creation and are populated when the following future endpoints
    are implemented — with zero breaking changes to this contract:

        POST   /api/candidates/{candidate_id}/resume
        GET    /api/candidates/{candidate_id}/resume
        DELETE /api/candidates/{candidate_id}/resume

    Storage backend (S3 / GridFS / local filesystem) is a future decision
    that does not affect the shape of this schema.
    """

    model_config = ConfigDict(extra="ignore")

    candidate_id: str = Field(
        description="Server-generated UUID4 assigned at creation time."
    )
    name: str
    role_applied: str
    skills: list[str] = Field(default_factory=list)
    experience_years: int = 0
    match_score: float = Field(
        default=0.0,
        description=(
            "AI-computed relevance score set by the recruitment workflow agent. "
            "Read-only from the CRUD perspective."
        ),
    )
    email: str = ""
    phone: str = ""

    # ------------------------------------------------------------------
    # Resume extensibility fields.
    # Null until the future resume-upload endpoint populates them.
    # Present here so the frontend contract is stable before that feature ships.
    # ------------------------------------------------------------------
    resume_filename: str | None = Field(
        default=None,
        description=(
            "Original filename of the uploaded resume. "
            "Null until a resume has been uploaded."
        ),
    )
    resume_url: str | None = Field(
        default=None,
        description=(
            "Pre-signed or permanent URL used to retrieve the resume file. "
            "Null until a resume has been uploaded. "
            "Storage backend (S3 / GridFS / local) is a future decision."
        ),
    )
    resume_uploaded_at: str | None = Field(
        default=None,
        description=(
            "ISO 8601 UTC timestamp of the most recent resume upload. "
            "Null until a resume has been uploaded."
        ),
    )


class CandidateListResponse(BaseModel):
    """Flat list of all candidates."""

    total: int = Field(
        description="Total number of candidate documents in the collection."
    )
    items: list[CandidateResponse]


# ==============================================================
# PRODUCTS
# ==============================================================

class ProductCreateRequest(BaseModel):
    """
    Payload for POST /api/products.

    product_name is the unique business key. It is used as the URL
    path parameter in all subsequent product routes and is treated as
    case-insensitive in the repository (data_loader.py convention).
    """

    model_config = ConfigDict(extra="forbid")

    product_name: str = Field(
        ...,
        min_length=1,
        max_length=120,
        description=(
            "Unique product identifier used as the URL key. "
            "Case-insensitive matching is applied on lookup."
        ),
        examples=["HRTech Pro"],
    )
    description: str = Field(
        default="",
        max_length=1000,
        description="Human-readable product description.",
        examples=["AI-powered HR management platform."],
    )
    pain_points: list[str] = Field(
        default_factory=list,
        description=(
            "Customer pain points this product addresses. "
            "Used by the sales outreach workflow for targeting."
        ),
        examples=[["High employee turnover", "Manual onboarding processes"]],
    )
    target_industries: list[str] = Field(
        default_factory=list,
        description=(
            "Industries targeted by this product."
        ),
        examples=[["SaaS", "IT Services", "Startups"]],
    )
    category: str = Field(
        default="",
        max_length=100,
        description="Product category or vertical.",
        examples=["HR Software"],
    )
    price_range: str = Field(
        default="",
        max_length=50,
        description="Indicative pricing tier or band.",
        examples=["$500–$2,000/mo"],
    )


class ProductUpdateRequest(BaseModel):
    """
    Payload for PUT /api/products/{product_name}.

    product_name is the immutable URL key and is absent from this schema.
    All other fields are optional; only non-None values are patched.
    Pass [] for pain_points to clear the list.
    """

    model_config = ConfigDict(extra="forbid")

    description: str | None = Field(
        default=None,
        max_length=1000,
    )
    pain_points: list[str] | None = Field(
        default=None,
        description=(
            "Replaces the entire pain_points list. "
            "Pass [] to clear all pain points."
        ),
    )
    target_industries: list[str] | None = Field(
        default=None,
        description=(
            "Replaces the entire target_industries list. "
            "Pass [] to clear all industries."
        ),
    )
    category: str | None = Field(
        default=None,
        max_length=100,
    )
    price_range: str | None = Field(
        default=None,
        max_length=50,
    )


class ProductResponse(BaseModel):
    """
    Product document returned to the frontend.

    Extra fields that exist in seeded MongoDB documents (e.g. features,
    target_customers) but are not listed here are silently dropped.
    Extend this schema to expose additional fields as needed.
    """

    model_config = ConfigDict(extra="ignore")

    product_name: str
    description: str = ""
    pain_points: list[str] = Field(default_factory=list)
    target_industries: list[str] = Field(default_factory=list)
    category: str = ""
    price_range: str = ""


class ProductListResponse(BaseModel):
    """Flat list of all products."""

    total: int = Field(
        description="Total number of product documents in the collection."
    )
    items: list[ProductResponse]


# ==============================================================
# ROLES
# ==============================================================

class RoleResponse(BaseModel):
    """
    Role document returned to the frontend.

    Mirrors the dict shape returned by data_loader.get_role_info()
    so the workflow engine and the frontend always see consistent data.

    Roles can be managed through the CRUD API and are consumed by
    workflow execution for parameter enrichment and validation.

    Extra fields from MongoDB documents are silently ignored.
    """

    model_config = ConfigDict(extra="ignore")

    department: str
    role: str
    experience_years: int = 0
    skills_required: list[str] = Field(default_factory=list)
    location: str = ""
    rating_scale: int = 5
    salary_range: str = ""
    onboarding_checklist: list[str] = Field(default_factory=list)


class RoleListResponse(BaseModel):
    """Complete list of roles (no pagination; roles are a small, stable set)."""

    total: int
    items: list[RoleResponse]

class RoleCreateRequest(BaseModel):
    """
    Payload for POST /api/roles.
    """

    model_config = ConfigDict(extra="forbid")

    department: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )
    role: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )
    experience_years: int = Field(
        default=0,
        ge=0,
        le=60,
    )
    skills_required: list[str] = Field(
        default_factory=list
    )
    location: str = Field(
        default="",
        max_length=100,
    )
    rating_scale: int = Field(
        default=5,
        ge=1,
        le=10,
    )
    salary_range: str = Field(
        default="",
        max_length=100,
    )
    onboarding_checklist: list[str] = Field(
        default_factory=list
    )


class RoleUpdateRequest(BaseModel):
    """
    Payload for PUT /api/roles/{role}.
    role is immutable.
    """

    model_config = ConfigDict(extra="forbid")

    department: str | None = None
    experience_years: int | None = Field(
        default=None,
        ge=0,
        le=60,
    )
    skills_required: list[str] | None = None
    location: str | None = None
    rating_scale: int | None = Field(
        default=None,
        ge=1,
        le=10,
    )
    salary_range: str | None = None
    onboarding_checklist: list[str] | None = None

# ==============================================================
# GOALS
# ==============================================================

class GoalCreateRequest(BaseModel):
    """
    Payload for POST /api/goals.

    Goals are uniquely identified by the composite key
    (employee_name, review_period). The repository performs a
    pre-insert uniqueness check and returns 409 on conflict.

    Mirrors the document shape consumed by data_loader.get_goals(),
    ensuring that goals created via the CRUD API are immediately
    visible to the performance_review workflow without any conversion.

    review_period format
    --------------------
    Use the same string format as the existing seed data, typically
    "Q<n> <YYYY>" (e.g. "Q2 2026"). The repository applies
    case-insensitive matching so "q2 2026" and "Q2 2026" resolve to
    the same document.
    """

    model_config = ConfigDict(extra="forbid")

    employee_name: str = Field(
        ...,
        min_length=1,
        max_length=120,
        description=(
            "Full name of the employee. Must match the employee_name "
            "stored in the employees collection (case-insensitive)."
        ),
        examples=["Alice Johnson"],
    )
    review_period: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description=(
            "Review cycle identifier, e.g. 'Q2 2026' or 'H1 2025'. "
            "Together with employee_name this forms the unique composite key."
        ),
        examples=["Q2 2026"],
    )
    goals_set: list[str] = Field(
        default_factory=list,
        description=(
            "Goals defined for this employee in this review period. "
            "Used by the performance_review workflow to evaluate achievement."
        ),
        examples=[["Complete FastAPI migration", "Mentor two junior engineers"]],
    )
    goals_achieved: list[str] = Field(
        default_factory=list,
        description=(
            "Subset of goals_set that have been completed. "
            "Used by the performance_review workflow for scoring."
        ),
        examples=[["Complete FastAPI migration"]],
    )


class GoalUpdateRequest(BaseModel):
    """
    Payload for PUT /api/goals/{employee_name}/{review_period}.

    Only goals_set and goals_achieved may be updated.
    employee_name and review_period are the immutable composite key
    and must not appear in this schema.

    Partial update semantics
    ------------------------
    - Omit a field (send null / don't include it) → field is unchanged.
    - Pass an empty list []                        → field is cleared.
    - Pass a non-empty list                        → field is replaced.
    """

    model_config = ConfigDict(extra="forbid")

    goals_set: list[str] | None = Field(
        default=None,
        description=(
            "Replacement list of goals for this review period. "
            "Omit to leave unchanged. Pass [] to clear all goals."
        ),
    )
    goals_achieved: list[str] | None = Field(
        default=None,
        description=(
            "Replacement list of achieved goals. "
            "Omit to leave unchanged. Pass [] to mark all as incomplete."
        ),
    )


class GoalResponse(BaseModel):
    """
    Goal document returned to the frontend.

    Mirrors the structure expected by data_loader.get_goals() so that
    goals written by the CRUD API are immediately consumable by the
    performance_review workflow without any transformation.

    Extra fields from MongoDB documents are silently ignored.
    """

    model_config = ConfigDict(extra="ignore")

    employee_name: str
    review_period: str
    goals_set: list[str] = Field(
        default_factory=list,
        description="Goals defined for this review period.",
    )
    goals_achieved: list[str] = Field(
        default_factory=list,
        description="Goals that have been completed.",
    )


class GoalListResponse(BaseModel):
    """Flat list of all goal documents across all employees and periods."""

    total: int = Field(
        description="Total number of goal documents in the collection."
    )
    items: list[GoalResponse]