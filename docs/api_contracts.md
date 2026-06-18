# API Contract Specification
## AI Digital Employee Platform — MVP Backend

**Version:** 1.0 — MVP  
**Status:** Implementation-Ready  
**Architecture Baseline:** `workflow_executor.py` (frozen)

---

## Table of Contents

1. [Endpoint Inventory](#1-endpoint-inventory)
2. [Platform Error Contract](#2-platform-error-contract)
3. [Workflow Status Reference](#3-workflow-status-reference)
4. [POST /workflows/start](#4-post-workflowsstart)
5. [GET /workflows/{workflow_id}](#5-get-workflowsworkflow_id)
6. [POST /workflows/{workflow_id}/resume](#6-post-workflowsworkflow_idresume)
7. [GET /workflows](#7-get-workflows)
8. [Params Reference by Objective](#8-params-reference-by-objective)
9. [FastAPI Implementation Notes](#9-fastapi-implementation-notes)
10. [Future Compatibility Notes](#10-future-compatibility-notes)
11. [Architecture Review](#11-architecture-review)

---

## 1. Endpoint Inventory

| Method | Path | Purpose | Calls Executor |
|--------|------|---------|---------------|
| `POST` | `/workflows/start` | Start a new workflow | `start_workflow()` |
| `GET` | `/workflows/{workflow_id}` | Get workflow status and result | `_load_state()` |
| `POST` | `/workflows/{workflow_id}/resume` | Submit human approval decision | `resume_workflow()` |
| `GET` | `/workflows` | List workflows (filterable) | `_load_state()` per record |

All endpoints live under the `/workflows` prefix. Candidate, resume, and other future resource endpoints live under their own prefixes and do not touch these routes.

---

## 2. Platform Error Contract

Every error response across all endpoints uses a single consistent envelope.

### Error Response Shape

```json
{
  "error": {
    "code": "WORKFLOW_NOT_FOUND",
    "message": "Workflow 'wf_abc123' not found.",
    "field": null,
    "details": null
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `code` | `string` | Machine-readable error identifier (screaming snake case) |
| `message` | `string` | Human-readable description, safe to display in UI |
| `field` | `string \| null` | Field name for validation errors; `null` for non-field errors |
| `details` | `object \| null` | Reserved for extended error context (future use) |

### Error Code Registry

| HTTP Status | Code | Trigger |
|-------------|------|---------|
| `404` | `WORKFLOW_NOT_FOUND` | `workflow_id` does not exist in the store |
| `422` | `INVALID_OBJECTIVE` | `objective_id` is not one of the six valid values |
| `422` | `INVALID_PARAMS` | Params do not satisfy the model for the given `objective_id` |
| `422` | `VALIDATION_ERROR` | General field-level validation failure |
| `422` | `INVALID_APPROVAL_STATUS` | `approval_status` is not `"approved"` or `"rejected"` |
| `409` | `WORKFLOW_NOT_PAUSED` | `resume` called on a workflow that is not in `paused` status |
| `409` | `WORKFLOW_NOT_AWAITING_INPUT` | `resume` called when `awaiting_human_input` is `false` |
| `500` | `INTERNAL_SERVER_ERROR` | Unhandled exception in executor or routing layer |

### Internal State Corruption Errors

The workflow executor contains internal consistency checks to detect invalid or corrupt workflow state.

Examples include:

- Missing approval gate
- Invalid current_task_id
- Duplicate gate output
- Corrupt persistence records
- Invalid workflow state transitions

These errors are considered server-side faults and must return: HTTP 500 INTERNAL_SERVER_ERROR
They are not validation errors and must never be returned as HTTP 422 responses.

---

## 3. Workflow Status Reference

| Status | Meaning | Terminal |
|--------|---------|----------|
| `running` | Executor is actively processing tasks | No |
| `paused` | Halted at human approval gate (`hire_employee` only) | No |
| `completed` | All tasks finished successfully | Yes |
| `failed` | Stopped due to agent error or rejected approval | Yes |

`approval_status` is a separate field and only applies to the `hire_employee` workflow's manager gate.

| Approval Status | Meaning |
|-----------------|---------|
| `pending` | Gate not yet reached, or awaiting decision |
| `approved` | Manager approved the offer |
| `rejected` | Manager rejected the offer |

---

## 4. POST /workflows/start

Validates the request, creates `AgentState`, and begins sequential task execution.

**Executor call:** `start_workflow(planner_input: PlannerInput) -> AgentState`

Because workflows can run multiple AI tasks sequentially (up to 7 tasks for `hire_employee`), this endpoint dispatches execution asynchronously via a FastAPI `BackgroundTask` and returns `202 Accepted` immediately. The client polls `GET /workflows/{workflow_id}` to track progress.

### Request

```
POST /workflows/start
Content-Type: application/json
```

```json
{
  "objective_id": "hire_employee",
  "params": {
    "role": "Senior Software Engineer",
    "department": "Engineering",
    "job_type": "full_time"
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `objective_id` | `string` | Yes | One of the six valid objective identifiers |
| `params` | `object` | Yes | Params object matching the given `objective_id` (see Section 8) |

**Valid `objective_id` values:**  
`hire_employee` · `onboard_employee` · `sales_outreach` · `performance_report` · `performance_review` · `market_research`

### Validation Rules

- `objective_id` must be one of the six valid values; return `INVALID_OBJECTIVE` (422) otherwise.
- `params` must satisfy the required fields for the given `objective_id`; return `INVALID_PARAMS` (422) otherwise.
- Planner-owned enrichment fields (e.g. experience_years,skills_required, salary_range, and similar fields generated during planning) may be present in the underlying params models but should not be supplied by clients.If provided, these values are ignored and may be overwritten during planner enrichment.Clients must not rely on submitted enrichment values being preserved.
- The API layer must dispatch the correct `params` model for validation based on `objective_id` (see FastAPI notes, Section 9.2).

### Success Response — 202 Accepted

Returned immediately after the executor initializes and persists `AgentState`. Execution continues in the background.

```json
{
  "workflow_id": "wf_3f8a2c1d-7e4b-4a12-9f3e-1b2c3d4e5f6a",
  "objective_id": "hire_employee",
  "status": "running",
  "message": "Workflow started. Poll GET /workflows/{workflow_id} for status."
}
```

| Field | Type | Description |
|-------|------|-------------|
| `workflow_id` | `string` | Unique execution ID (`wf_<uuid4>`) to use for polling and resume |
| `objective_id` | `string` | Echoed from request |
| `status` | `string` | Always `"running"` at time of acceptance |
| `message` | `string` | Polling instruction for frontend |

### Error Responses

**422 — Invalid objective_id:**
```json
{
  "error": {
    "code": "INVALID_OBJECTIVE",
    "message": "Invalid objective_id 'hire_employe'. Valid values: hire_employee, onboard_employee, sales_outreach, performance_report, performance_review, market_research.",
    "field": "objective_id",
    "details": null
  }
}
```

**422 — Missing required params field:**
```json
{
  "error": {
    "code": "INVALID_PARAMS",
    "message": "Missing required field 'department' for objective 'hire_employee'.",
    "field": "params.department",
    "details": null
  }
}
```

**500 — Executor initialization failure:**
```json
{
  "error": {
    "code": "INTERNAL_SERVER_ERROR",
    "message": "An unexpected error occurred while initializing the workflow.",
    "field": null,
    "details": null
  }
}
```

---

## 5. GET /workflows/{workflow_id}

Returns the current state of a workflow. Used for polling after `POST /workflows/start` or `POST /workflows/{workflow_id}/resume`.

**Executor call:** `_load_state(workflow_id)` (internal — API layer calls this directly)

### Request

```
GET /workflows/wf_3f8a2c1d-7e4b-4a12-9f3e-1b2c3d4e5f6a
```

No request body.

### Success Response — 200 OK

The response shape is identical across all statuses. Fields that are not applicable for a given status are `null` or `""`.

```json
{
  "workflow_id": "wf_3f8a2c1d-7e4b-4a12-9f3e-1b2c3d4e5f6a",
  "objective_id": "hire_employee",
  "status": "paused",
  "current_task_id": "t6",
  "current_agent": "human",
  "awaiting_human_input": true,
  "approval_status": "pending",
  "approval_context": null,
  "human_feedback": null,
  "error_message": null,
  "result": null,
  "created_at": "2025-08-01T10:23:40Z",
  "updated_at": "2025-08-01T10:24:55Z"
}
```

### Response Field Reference

| Field | Type | Description |
|-------|------|-------------|
| `workflow_id` | `string` | Unique execution ID |
| `objective_id` | `string` | Workflow type |
| `status` | `string` | `running` \| `paused` \| `completed` \| `failed` |
| `current_task_id` | `string` | Active task ID (`"t3"`) or `""` when idle/terminal |
| `current_agent` | `string` | Active agent name or `""` when idle/terminal |
| `awaiting_human_input` | `boolean` | `true` only when paused at human gate — triggers approval UI |
| `approval_status` | `string` | `pending` \| `approved` \| `rejected` — meaningful for `hire_employee` only |
| `approval_context` | `object` \| `null` | Manager-facing approval information. Present only when awaiting human approval. Null otherwise. |
| `human_feedback` | `string \| null` | Manager's comment submitted with approval decision |
| `error_message` | `string \| null` | Populated when `status == "failed"`; `null` otherwise |
| `result` | `object \| null` | Final task output dict when `status == "completed"`; `null` otherwise |
| `created_at` | `string` | ISO 8601 UTC — workflow creation timestamp |
| `updated_at` | `string` | ISO 8601 UTC — last persistence write timestamp |

### The approval_context Field

Present only when:

- status == "paused"
- awaiting_human_input == true

Contains the information required by a manager to make an approval decision.

This field intentionally exposes only approval-facing business data and does not expose raw workflow outputs or internal AgentState structures.

Null for all other workflow states.

approval_context is a presentation-oriented summary generated for approval workflows.
Clients must not rely on the exact structure remaining identical across workflow types.The field is intended for display purposes only.

### The `result` Field

Populated only when `status == "completed"`. Contains the output dict of the final task, keyed by workflow type:

| Objective | Result Shape |
|-----------|-------------|
| `hire_employee` | `{ "hiring_summary": string }` |
| `onboard_employee` | `{ "summary": string }` |
| `sales_outreach` | `{ "campaign_summary": string }` |
| `performance_report` | `{ "recommendations": string[] }` |
| `performance_review` | `{ "review_summary": string }` |
| `market_research` | `{ "executive_summary": string }` |

**Intentionally excluded from response:** `tasks`, `outputs` (raw agent data), `params` (internal/enriched), `completed_tasks`, `execution_log`. These are internal implementation details. A future debug endpoint can expose `execution_log` if needed.

### Response Examples by Status

**Status: `running`**
```json
{
  "workflow_id": "wf_abc123",
  "objective_id": "hire_employee",
  "status": "running",
  "current_task_id": "t3",
  "current_agent": "recruitment",
  "awaiting_human_input": false,
  "approval_status": "pending",
  "human_feedback": null,
  "error_message": null,
  "result": null,
  "created_at": "2025-08-01T10:23:40Z",
  "updated_at": "2025-08-01T10:24:10Z"
}
```

**Status: `paused`** (hire_employee, at t6 manager_approval gate)
```json
{
  "workflow_id": "wf_abc123",
  "objective_id": "hire_employee",
  "status": "paused",
  "current_task_id": "t6",
  "current_agent": "human",
  "awaiting_human_input": true,

  "approval_context": {
    "candidate_name": "Alex Smith",
    "role": "Senior Software Engineer",
    "department": "Engineering",
    "salary_offered": "$140,000"
  },

  "approval_status": "pending",
  "human_feedback": null,
  "error_message": null,
  "result": null,
  "created_at": "2025-08-01T10:23:40Z",
  "updated_at": "2025-08-01T10:24:55Z"
}
```

**Status: `completed`**
```json
{
  "workflow_id": "wf_abc123",
  "objective_id": "hire_employee",
  "status": "completed",
  "current_task_id": "",
  "current_agent": "",
  "awaiting_human_input": false,
  "approval_status": "approved",
  "human_feedback": "Strong candidate, compensation is within budget.",
  "error_message": null,
  "result": {
    "hiring_summary": "Alex Smith has been successfully hired as Senior Software Engineer in Engineering..."
  },
  "created_at": "2025-08-01T10:23:40Z",
  "updated_at": "2025-08-01T10:26:30Z"
}
```

**Status: `failed` — agent error**
```json
{
  "workflow_id": "wf_abc123",
  "objective_id": "hire_employee",
  "status": "failed",
  "current_task_id": "",
  "current_agent": "",
  "awaiting_human_input": false,
  "approval_status": "pending",
  "human_feedback": null,
  "error_message": "[recruitment] Task 't3' (action='shortlist_candidates') failed: candidates.json not found.",
  "result": null,
  "created_at": "2025-08-01T10:23:40Z",
  "updated_at": "2025-08-01T10:24:05Z"
}
```

**Status: `failed` — manager rejected offer**
```json
{
  "workflow_id": "wf_abc123",
  "objective_id": "hire_employee",
  "status": "failed",
  "current_task_id": "",
  "current_agent": "",
  "awaiting_human_input": false,
  "approval_status": "rejected",
  "human_feedback": "Salary exceeds budget. Please re-evaluate.",
  "error_message": "Manager rejected offer: Salary exceeds budget. Please re-evaluate.",
  "result": null,
  "created_at": "2025-08-01T10:23:40Z",
  "updated_at": "2025-08-01T10:25:40Z"
}
```

### Error Responses

**404 — Workflow not found:**
```json
{
  "error": {
    "code": "WORKFLOW_NOT_FOUND",
    "message": "Workflow 'wf_abc123' not found.",
    "field": null,
    "details": null
  }
}
```

---

## 6. POST /workflows/{workflow_id}/resume

Submits the human approval decision for a paused workflow. Only valid when `status == "paused"` and `awaiting_human_input == true`. Applicable only to `hire_employee` workflows in MVP.

**Executor call:** `resume_workflow(workflow_id, approval_status, human_feedback) -> AgentState`

Returns `202 Accepted`. The executor runs the remaining task (`t7 generate_hiring_summary`) in the background for approval; for rejection the workflow immediately fails with no further execution.

### Request

```
POST /workflows/wf_abc123/resume
Content-Type: application/json
```

```json
{
  "approval_status": "approved",
  "human_feedback": "Strong candidate, compensation is within budget."
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `approval_status` | `string` | Yes | Must be exactly `"approved"` or `"rejected"` |
| `human_feedback` | `string \| null` | No | Manager's comments. Optional for both approved and rejected decisions. Max 2000 characters. |

### Validation Rules

- `approval_status` must be exactly `"approved"` or `"rejected"` (case-sensitive); return `INVALID_APPROVAL_STATUS` (422) otherwise.
- The target workflow must have `status == "paused"` AND `awaiting_human_input == true`; return `WORKFLOW_NOT_PAUSED` (409) otherwise.
- `human_feedback` is optional on both approval and rejection. No default value is enforced by the API; the executor uses `"(no comment provided)"` internally if `null` and the workflow is rejected (purely for the `error_message` field).
- `human_feedback`, when provided, must be a string with max 2000 characters.

### Success Response — 202 Accepted

```json
{
  "workflow_id": "wf_abc123",
  "objective_id": "hire_employee",
  "approval_status": "approved",
  "status": "running",
  "message": "Decision recorded. Poll GET /workflows/{workflow_id} for final status."
}
```

| Field | Type | Description |
|-------|------|-------------|
| `workflow_id` | `string` | Echoed from URL path |
| `objective_id` | `string` | Workflow type |
| `approval_status` | `string` | Echoed from request: `"approved"` or `"rejected"` |
| `status` | `string` | `"running"` if approved (execution continues); `"failed"` if rejected |
| `message` | `string` | Polling instruction |

**Note:** For a `"rejected"` decision, `status` in this response is `"failed"` immediately (no background execution occurs). The client can either use this value directly or verify with a GET call.

### Error Responses

**404 — Workflow not found:**
```json
{
  "error": {
    "code": "WORKFLOW_NOT_FOUND",
    "message": "Workflow 'wf_abc123' not found.",
    "field": null,
    "details": null
  }
}
```

**409 — Workflow not paused:**
```json
{
  "error": {
    "code": "WORKFLOW_NOT_PAUSED",
    "message": "Cannot resume workflow 'wf_abc123': current status is 'completed'. Only paused workflows can be resumed.",
    "field": null,
    "details": null
  }
}
```

**409 — Not awaiting human input:**
```json
{
  "error": {
    "code": "WORKFLOW_NOT_AWAITING_INPUT",
    "message": "Workflow 'wf_abc123' is paused but is not currently awaiting human input.",
    "field": null,
    "details": null
  }
}
```

**422 — Invalid approval status:**
```json
{
  "error": {
    "code": "INVALID_APPROVAL_STATUS",
    "message": "Invalid approval_status 'Approved'. Must be exactly 'approved' or 'rejected' (case-sensitive).",
    "field": "approval_status",
    "details": null
  }
}
```

**422 — Feedback too long:**
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "human_feedback must not exceed 2000 characters.",
    "field": "human_feedback",
    "details": null
  }
}
```

---

## 7. GET /workflows

Returns a paginated list of workflows. Primarily useful for the manager dashboard to surface pending approvals and track recent runs.

### Request

```
GET /workflows?status=paused&objective_id=hire_employee&limit=20&offset=0
```

| Query Param | Type | Required | Description |
|-------------|------|----------|-------------|
| `status` | `string` | No | Filter by workflow status: `running` \| `paused` \| `completed` \| `failed` |
| `objective_id` | `string` | No | Filter by objective type |
| `limit` | `integer` | No | Page size. Default: `20`, max: `100` |
| `offset` | `integer` | No | Pagination offset. Default: `0` |

### Success Response — 200 OK

```json
{
  "total": 3,
  "limit": 20,
  "offset": 0,
  "items": [
    {
      "workflow_id": "wf_abc123",
      "objective_id": "hire_employee",
      "status": "paused",
      "awaiting_human_input": true,
      "approval_status": "pending",
      "created_at": "2025-08-01T10:23:40Z",
      "updated_at": "2025-08-01T10:24:55Z"
    },
    {
      "workflow_id": "wf_def456",
      "objective_id": "hire_employee",
      "status": "completed",
      "awaiting_human_input": false,
      "approval_status": "approved",
      "created_at": "2025-07-31T09:10:00Z",
      "updated_at": "2025-07-31T09:15:30Z"
    }
  ]
}
```

List items are intentionally trimmed — `current_task_id`, `error_message`, `result`, etc. are omitted. Clients fetch the full record via `GET /workflows/{workflow_id}` when needed.

### Common Frontend Pattern — Pending Approvals Dashboard

```
GET /workflows?status=paused
```

Returns all `hire_employee` workflows awaiting a manager decision.

---

## 8. Params Reference by Objective

The `params` object in `POST /workflows/start` must match the schema for the given `objective_id`. Clients should send only the required fields.Planner-owned enrichment fields may be supplied but are ignored and may be overwritten during planner enrichment.

### hire_employee

```json
{
  "role": "Senior Software Engineer",
  "department": "Engineering",
  "job_type": "full_time"
}
```

| Field | Type | Required |
|-------|------|----------|
| `role` | `string` | Yes |
| `department` | `string` | Yes |
| `job_type` | `string` | Yes |

---

### onboard_employee

```json
{
  "employee_name": "Priya Kapoor"
}
```

| Field | Type | Required |
|-------|------|----------|
| `employee_name` | `string` | Yes |

---

### sales_outreach

```json
{
  "target_segment": "Mid-market SaaS companies",
  "outreach_channels": ["email", "linkedin"],
  "campaign_goal": "Book 20 discovery calls in Q3"
}
```

| Field | Type | Required |
|-------|------|----------|
| `target_segment` | `string` | Yes |
| `outreach_channels` | `string[]` | Yes |
| `campaign_goal` | `string` | Yes |

---

### performance_report

```json
{
  "report_period": "Q2 2025",
  "departments": ["Engineering", "Sales"],
  "metrics_to_include": ["headcount", "revenue", "attrition"],
  "report_type": "executive"
}
```

| Field | Type | Required |
|-------|------|----------|
| `report_period` | `string` | Yes |
| `departments` | `string[]` | Yes |
| `metrics_to_include` | `string[]` | Yes |
| `report_type` | `string` | Yes |

---

### performance_review

```json
{
  "employee_name": "Alex Smith",
  "review_period": "H1 2025",
  "manager_comments": "Alex consistently delivered on sprint goals and mentored two junior engineers."
}
```

| Field | Type | Required |
|-------|------|----------|
| `employee_name` | `string` | Yes |
| `review_period` | `string` | Yes |
| `manager_comments` | `string` | Yes |

---

### market_research

```json
{
  "research_topic": "AI-powered HR software market",
  "competitors": ["Workday", "BambooHR", "Rippling"],
  "focus_areas": ["pricing", "features", "market_share"],
  "output_format": "executive_report"
}
```

| Field | Type | Required |
|-------|------|----------|
| `research_topic` | `string` | Yes |
| `competitors` | `string[]` | Yes |
| `focus_areas` | `string[]` | Yes |
| `output_format` | `string` | Yes |

---

## 9. FastAPI Implementation Notes

### 9.1 Route Declarations

```python
from fastapi import FastAPI, BackgroundTasks, HTTPException

app = FastAPI()

@app.post("/workflows/start", status_code=202)
async def start_workflow_route(body: StartWorkflowRequest, background_tasks: BackgroundTasks):
    ...

@app.get("/workflows/{workflow_id}", status_code=200)
async def get_workflow_route(workflow_id: str):
    ...

@app.post("/workflows/{workflow_id}/resume", status_code=202)
async def resume_workflow_route(workflow_id: str, body: ResumeWorkflowRequest):
    ...

@app.get("/workflows", status_code=200)
async def list_workflows_route(
    status: str | None = None,
    objective_id: str | None = None,
    limit: int = 20,
    offset: int = 0,
):
    ...
```

### 9.2 Params Discriminator Pattern

`PlannerInput.params` is a bare `Union` with no Pydantic discriminator. The API layer must validate against the correct model using `objective_id` as the key:

```python
PARAMS_MODEL_MAP = {
    "hire_employee":      HireEmployeeParams,
    "onboard_employee":   OnboardEmployeeParams,
    "sales_outreach":     SalesOutreachParams,
    "performance_report": PerformanceReportParams,
    "performance_review": PerformanceReviewParams,
    "market_research":    MarketResearchParams,
}

def build_planner_input(objective_id: str, raw_params: dict) -> PlannerInput:
    model_class = PARAMS_MODEL_MAP.get(objective_id)
    if model_class is None:
        raise ValueError(f"Invalid objective_id: {objective_id}")
    validated_params = model_class(**raw_params)
    return PlannerInput(objective_id=objective_id, params=validated_params)
```

This produces precise per-field error messages rather than Pydantic's generic union-matching errors.

### 9.3 Executor Error → HTTP Status Mapping

Map `ValueError` messages from the executor to the appropriate status codes:

```python
def map_executor_error(e: ValueError) -> tuple[int, str]:
    msg = str(e)
    if "not found" in msg:
        return 404, "WORKFLOW_NOT_FOUND"
    if "not in 'paused' status" in msg or "status=" in msg:
        return 409, "WORKFLOW_NOT_PAUSED"
    if "awaiting_human_input" in msg:
        return 409, "WORKFLOW_NOT_AWAITING_INPUT"
    if "approval_status" in msg and "approved" in msg:
        return 422, "INVALID_APPROVAL_STATUS"
    if "corrupt" in msg:
        return 500, "INTERNAL_SERVER_ERROR"
    return 500, "INTERNAL_SERVER_ERROR"
```
Corruption-related executor errors must always map to:

HTTP 500 Code: INTERNAL_SERVER_ERROR

Examples:
- Missing approval gate
- Duplicate gate output
- Invalid current_task_id
- Corrupt persisted workflow state

These indicate an internal consistency failure and are never caused by client input.

### 9.4 Background Task Pattern for start_workflow

```python
@app.post("/workflows/start", status_code=202)
async def start_workflow_route(body: StartWorkflowRequest, background_tasks: BackgroundTasks):
    # Validate and build PlannerInput (raises 422 on invalid objective or params)
    planner_input = build_planner_input(body.objective_id, body.params)

    # Initialize state synchronously to get workflow_id for the 202 response.
    # initialize_state() is fast (no AI calls) — safe to run before returning.
    state = initialize_state(planner_input)
    _save_state(state)

    # Dispatch the execution loop in the background.
    background_tasks.add_task(_execute_loop, state)

    return {
        "workflow_id": state.workflow_id,
        "objective_id": state.objective_id,
        "status": "running",
        "message": f"Workflow started. Poll GET /workflows/{state.workflow_id} for status."
    }
```

### 9.5 `created_at` / `updated_at` Timestamps

These fields are not part of `AgentState` but are stored in the MongoDB document envelope (see `workflow_executor.py` §12.2). For MVP in-memory mode, the API layer should maintain a separate `_metadata` dict alongside `_store`:

```python
_metadata: dict[str, dict] = {}  # workflow_id -> {created_at, updated_at}
```

Populate `created_at` when `_save_state()` is first called; update `updated_at` on every subsequent call. When MongoDB is integrated, these are read directly from the document.

---

## 10. Future Compatibility Notes

### 10.1 MongoDB Integration

No workflow API contract changes required. The only change is inside `_save_state()` and `_load_state()` in `workflow_executor.py` — their signatures and return types are unchanged. The `GET /workflows/{workflow_id}` endpoint gains real `created_at`/`updated_at` values from the document envelope. `GET /workflows` gains proper indexed query support. All request and response shapes remain identical.

### 10.2 Candidate Repository Integration

Add under `/candidates` prefix — entirely separate from workflow routes:

```
POST /candidates/upload        # Single resume upload
POST /candidates/bulk-upload   # Batch upload
GET  /candidates/{candidate_id}
```

No workflow endpoints change. The only internal change is that `shortlist_candidates` (task `t3` in `hire_employee`) reads from the candidate repository instead of `candidates.json`. `AgentState`, `PlannerInput`, and all API contracts remain identical.

### 10.3 Resume Upload / Parsing Feature

Resume upload is a new resource operation, not a workflow mutation. It adds endpoints under `/candidates`. The `hire_employee` workflow contracts, `AgentState`, and all three workflow endpoints are unaffected.

### 10.4 Additional Workflow Types

Adding new objectives (e.g., `offboard_employee`) requires only: a new entry in `WORKFLOWS`, a new `Params` model in `models.py`, and a new entry in `PARAMS_MODEL_MAP` in the API layer. No endpoint paths, response shapes, or error contracts change.

### 10.5 Execution Log / Debug Endpoint (Future)

If an audit trail becomes needed, add:

```
GET /workflows/{workflow_id}/log
```

This returns `AgentState.execution_log` directly. It does not modify any existing response shape.

### 10.6 Design Decisions That Protect Stability

- `result` exposes only the final task output, not `outputs` (raw per-task data). Downstream task structure changes do not affect the response shape.
- `current_task_id` and `current_agent` expose task IDs and agent names, not task objects. Restructuring `Task` internally does not break the API.
- `params` is intentionally excluded from `GET /workflows/{workflow_id}`. If enriched params need to be exposed later, they can be added without breaking existing clients.

---

## 11. Architecture Review

### A. API Architecture Score: 8 / 10

The three required endpoints map cleanly onto the two public executor functions and the persistence layer. The contract boundaries respect the executor's ownership of `AgentState` — the API layer never writes state, only reads it from the store. The async dispatch pattern (`202 + poll`) is correct for a synchronous sequential executor that can block for seconds per task.

Minor deductions: the `params` Union without a discriminator field requires API-layer workaround logic (Section 9.2); and `created_at`/`updated_at` living outside `AgentState` requires a small metadata shim for MVP.

### B. Future-Proofing Score: 9 / 10

All three planned upgrades (MongoDB, candidate repository, resume upload) require zero changes to workflow endpoint contracts. The response schema deliberately excludes internal fields (`outputs`, `tasks`, `params`, `completed_tasks`) that are most likely to evolve. New objectives slot in without endpoint modification. The `/candidates` namespace is kept fully separate.

Minor deduction: the `result` field shape is workflow-specific (different keys per objective); if a strongly-typed frontend wants compile-time type safety per objective it will need a discriminated union on the client side.

### C. Frontend Integration Score: 9 / 10

The `status` field drives all conditional UI logic with four clean states. `awaiting_human_input: true` is the single unambiguous signal to render the approval UI — no status string parsing required. The `result` field delivers the final deliverable in a single GET without a second round-trip. `GET /workflows?status=paused` gives the manager dashboard exactly what it needs.

Minor deduction: polling interval is not defined by the contract (recommend 2–5 seconds with exponential back-off capped at 15 seconds, documented separately).

### D. MongoDB Compatibility Assessment

**Fully compatible — zero contract changes needed.**

The executor already plans for MongoDB with `_save_state()` and `_load_state()` as the sole persistence boundary. The MongoDB document structure (`_id`, `created_at`, `updated_at`, `state`) is already defined in `workflow_executor.py`. The `GET /workflows` endpoint gains indexed query support transparently. `AgentState.model_dump()` / `AgentState.model_validate()` are already the serialization path.

### E. Resume Upload Compatibility Assessment

**Fully compatible — zero contract changes needed.**

Resume upload is a pure resource operation under `/candidates`. The `hire_employee` workflow's `shortlist_candidates` task reads candidates internally from `state.params`/mock data. When a candidate repository is added, only the agent's internal data access changes — not `AgentState`, not `PlannerInput`, not any API contract.

### F. Recommended Improvements Before Implementation

1. **Add a discriminator field to `PlannerInput.params`** — add `objective_id` as a `Literal` discriminator to each Params model, enabling Pydantic's native union validation and eliminating the `PARAMS_MODEL_MAP` workaround. This is a `models.py` change (not a frozen file per the architecture spec — confirm with the architect).

2. **Track `created_at`/`updated_at` in `_save_state()`** — even in the in-memory MVP, add these to `_store` alongside the serialized state dict so the GET response is complete from day one without a separate metadata shim.

3. **Define polling interval guidance** — document a recommended poll interval (e.g., 2s with 1.5× backoff, max 15s) in the frontend integration guide to prevent thundering herd on the GET endpoint.

4. **Add `GET /workflows/{workflow_id}/log`** as a reserved (non-MVP) endpoint returning `execution_log` — even a stub response now prevents a future breaking path conflict.

5. **`human_feedback` on rejection** — the executor uses `"(no comment provided)"` when feedback is `null` and the workflow is rejected. Consider making feedback required (not optional) when `approval_status == "rejected"` for better audit trail quality. This is a product decision, not a bug.

---

*End of API Contract Specification v1.0*