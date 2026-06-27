# Workflow State Reference

> **Status**: Canonical reference for `workflow_executor.py` and `agent_router.py` implementers.
> **Frozen inputs**: `models.py`, `workflow_definitions.py`, `task_contracts.md`,
> `agent_responsibilities.md`, `data_loader.py`, `base_agent.py`, `planner.py`.
> Do not alter those files to satisfy this document — adapt this document if needed.

---

## Table of Contents

1. [AgentState Field Reference](#1-agentstate-field-reference)
2. [AgentState Initialization](#2-agentstate-initialization)
3. [Execution Log Schema](#3-execution-log-schema)
4. [Status Lifecycle](#4-status-lifecycle)
5. [Task Readiness Algorithm](#5-task-readiness-algorithm)
6. [Human Approval Gate](#6-human-approval-gate)
7. [Output Storage Convention](#7-output-storage-convention)
8. [Error Handling](#8-error-handling)
9. [Workflow Executor Contract](#9-workflow-executor-contract)
10. [Agent Router Contract](#10-agent-router-contract)
11. [LangGraph Integration Notes](#11-langgraph-integration-notes)
12. [MongoDB Persistence Notes](#12-mongodb-persistence-notes)
13. [Workflow Dependency Maps](#13-workflow-dependency-maps)
14. [Output Key Quick Reference](#14-output-key-quick-reference)

---

## 1. AgentState Field Reference

Defined in `models.py`. This section adds executor-level semantics to every field.

### 1.1 Identity Fields

| Field | Type | Set By | Mutability | Description |
|---|---|---|---|---|
| `workflow_id` | `str` | Planner | Immutable | Unique execution ID (`wf_<uuid4>`). Created by `run_planner()`. |
| `objective_id` | `str` | Planner | Immutable | Resolved workflow type. One of the six keys in `WORKFLOWS`. |

### 1.2 Input Fields

| Field | Type | Set By | Mutability | Description |
|---|---|---|---|---|
| `params` | `Union[...Params]` | Planner (enriched) | Read-only for agents | Fully enriched parameters. Written once at init; never overwritten. |
| `tasks` | `list[Task]` | Planner | Immutable | Complete ordered task list. Treated as a frozen plan by the executor. |

### 1.3 Execution Cursor Fields

Updated by the Workflow Executor immediately before dispatching a task. Agents read these fields but must never write them.

| Field | Type | Set By | Default | Description |
|---|---|---|---|---|
| `current_task_id` | `str` | Executor | `""` | The `task_id` of the task currently being executed. Empty when idle or complete. |
| `current_agent` | `str` | Executor | `""` | The `agent` field of the current task. Mirrors `task.agent`. Empty when idle. |

Both fields are cleared (set to `""`) when the workflow reaches a terminal state (`completed` or `failed`).

### 1.4 Tracking Fields

| Field | Type | Set By | Default | Description |
|---|---|---|---|---|
| `completed_tasks` | `list[str]` | Executor | `[]` | Ordered list of `task_id` values that have finished successfully. The sole source of truth for dependency resolution. |
| `outputs` | `dict[str, dict]` | Executor | `{}` | Maps each completed `task_id` to its output dict as returned by the agent. Keyed as `"t1"`, `"t2"`, etc. |
| `execution_log` | `list[dict]` | Executor | `[]` | Ordered audit trail. See [Section 3](#3-execution-log-schema) for entry schema. |

### 1.5 Status Fields

| Field | Type | Set By | Allowed Values | Default |
|---|---|---|---|---|
| `status` | `str` | Executor | `running` \| `paused` \| `completed` \| `failed` | `running` |
| `approval_status` | `str` | Executor | `pending` \| `approved` \| `rejected` | `pending` |
| `awaiting_human_input` | `bool` | Executor | `True` \| `False` | `False` |
| `human_feedback` | `str \| None` | Executor (via API) | Free text or `None` | `None` |
| `human_input_data` | `dict` | Executor (via API) | Free-form human-provided metadata associated with approval tasks. |
| `error_message` | `str \| None` | Executor | Error string or `None` | `None` |

approval_status and awaiting_human_input are only meaningful during or after human approval gates.

Current human gates:

- hire_employee / t5 / hr_select_candidates
- hire_employee / t7 / hr_offer_approval
- hire_employee / t8 / manager_approval
---

## 2. AgentState Initialization

The Workflow Executor initializes `AgentState` immediately after receiving output from `run_planner()`. All other fields take their Pydantic defaults.

```python
# workflow_executor.py

from backend.models import AgentState, PlannerInput
from backend.planner.planner import run_planner

def initialize_state(planner_input: PlannerInput) -> AgentState:
    planner_output, enriched_params = run_planner(planner_input)

    return AgentState(
        workflow_id=planner_output.workflow_id,
        objective_id=planner_output.objective_id,
        params=enriched_params,
        tasks=planner_output.tasks,
        # current_task_id  → "" (default)
        # current_agent    → "" (default)
        # completed_tasks  → [] (default)
        # outputs          → {} (default)
        # execution_log    → [] (default)
        # status           → "running" (default)
        # approval_status  → "pending" (default)
        # awaiting_human_input → False (default)
        # human_feedback   → None (default)
        # error_message    → None (default)
    )
```

Persist to MongoDB immediately after initialization before any task is attempted.
See [Section 12](#12-mongodb-persistence-notes) for persistence points.

---

## 3. Execution Log Schema

Every entry in `state.execution_log` is a plain `dict` with the following keys.
The schema is enforced by the Workflow Executor; agents never write to `execution_log`.

```python
{
    "task_id":   str,        # e.g. "t1"
    "agent":     str,        # e.g. "recruitment" | "human"
    "action":    str,        # e.g. "generate_job_description"
    "status":    str,        # "started" | "completed" | "failed" | "skipped"
    "timestamp": str,        # ISO 8601 UTC — e.g. "2025-08-01T10:23:45Z"
    "error":     str | None  # None unless status == "failed"
}
```

### Entry Rules

| Event | status value | error field | When written |
|---|---|---|---|
| Before agent.run() is called | `"started"` | `None` | Immediately before dispatch |
| After agent.run() returns successfully | `"completed"` | `None` | Immediately after result stored in `state.outputs` |
| After agent.run() raises `AgentExecutionError` | `"failed"` | `str(e.cause)` | Immediately after exception caught |
| Human gate reached (paused) | `"started"` | `None` | When workflow enters paused state |
| Human gate resolved (approved) | `"completed"` | `None` | When resume_workflow() applies approval |
| Human gate resolved (rejected) | `"failed"` | Rejection reason | When resume_workflow() applies rejection |

The `"skipped"` status is reserved for future use (e.g. conditional branching). Do not emit it in MVP.

### Example Log for hire_employee (partial)

```python
[
    {"task_id": "t1", "agent": "recruitment", "action": "generate_job_description",  "status": "started",   "timestamp": "...", "error": None},
    {"task_id": "t1", "agent": "recruitment", "action": "generate_job_description",  "status": "completed", "timestamp": "...", "error": None},
    {"task_id": "t2", "agent": "recruitment", "action": "identify_required_skills",  "status": "started",   "timestamp": "...", "error": None},
    {"task_id": "t2", "agent": "recruitment", "action": "identify_required_skills",  "status": "completed", "timestamp": "...", "error": None},
    # ... t3, t4, t5 ...
    {"task_id": "t5", "agent": "human", "action": "hr_select_candidates", "status": "started", "timestamp": "...", "error": None},
    {"task_id": "t5", "agent": "human", "action": "hr_select_candidates", "status": "completed", "timestamp": "...", "error": None},

    {"task_id": "t7", "agent": "human", "action": "hr_offer_approval", "status": "started", "timestamp": "...", "error": None},
    {"task_id": "t7", "agent": "human", "action": "hr_offer_approval", "status": "completed", "timestamp": "...", "error": None},

    {"task_id": "t8", "agent": "human", "action": "manager_approval", "status": "started", "timestamp": "...", "error": None},
    {"task_id": "t8", "agent": "human", "action": "manager_approval", "status": "completed", "timestamp": "...", "error": None},

    {"task_id": "t9", "agent": "reporting", "action": "generate_hiring_summary", "status": "started", "timestamp": "...", "error": None},
    {"task_id": "t9", "agent": "reporting", "action": "generate_hiring_summary", "status": "completed", "timestamp": "...", "error": None}
    ```

---

## 4. Status Lifecycle

### 4.1 Status Values

| Status | Meaning |
|---|---|
| `running` | Workflow is actively executing tasks. Normal operating state. |
| `paused` | Workflow is halted at a human approval gate awaiting an external decision. |
| `completed` | All tasks in the workflow finished successfully. Terminal state. |
| `failed` | Execution halted due to an agent error or a rejected human approval. Terminal state. |

### 4.2 Status Transition Diagram

```
                         ┌───────────────────────────────────────────────────────┐
                         │                                                       │
                         │    (Planner resolves PlannerInput)                    │
                         │              │                                        │
                         │              ▼                                        │
                         │       ┌────────────┐                                  │
                         │  ┌───►│  running   │◄────────┐                        │
                         │  │    └─────┬──────┘         │                        │
                         │  │          │                 │                       │
                         │  │    ┌─────┴──────┬──────────┴──────┬───────────┐    │
                         │  │    │            │                  │          │    │
                         │  │  human       all tasks          agent         │    │
                         │  │  gate        complete           error         │    │
                         │  │  reached         │               or           │    │
                         │  │    │             │            rejection       │    │
                         │  │    ▼             ▼               │            │    │
                         │  │  ┌──────┐  ┌──────────┐    ┌──────────┐       │    │
                         │  │  │paused│  │completed │    │  failed  │       │    │
                         │  │  └──┬───┘  └──────────┘    └──────────┘       │    │
                         │  │     │       (terminal)       (terminal)       │    │
                         │  │     │                                         │    │
                         │  │ approved ──────────────────────────────────►──┘    │
                         │  │     │                                              │
                         │  │  rejected ─────────────────────────────────► failed│
                         │  │                                                    │
                         └──┴────────────────────────────────────────────────────┘
```

### 4.3 Transition Rules

| From | Trigger | To | State Changes Made by Executor |
|---|---|---|---|
| _(init)_ | `initialize_state()` called | `running` | All fields at defaults |
| `running` | Human gate task reached | `paused` | `awaiting_human_input = True`; cursor fields set to gate task |
| `paused` | `resume_workflow()` called with `"approved"` | `running` | `awaiting_human_input = False`; `approval_status = "approved"`; `human_feedback = <text>`; gate task added to `completed_tasks`; `outputs[gate_id] = {"approval_status": "approved","human_feedback": "<text>","human_input_data": {}}` |
| `paused` | `resume_workflow()` called with `"rejected"` | `failed` | `awaiting_human_input = False`; `approval_status = "rejected"`; `human_feedback = <text>`; `outputs[gate_id] = {"approval_status": "rejected","human_feedback": "<text>","human_input_data": {}
}`; `error_message` set; cursor cleared |
| `running` | All tasks in `completed_tasks` | `completed` | `current_task_id = ""`; `current_agent = ""` |
| `running` | `AgentExecutionError` raised | `failed` | `error_message = str(e)`; cursor cleared |
| `running` | Dependency deadlock detected | `failed` | `error_message = "Dependency deadlock: ..."` |

`completed` and `failed` are terminal — no further transitions occur.

---

## 5. Task Readiness Algorithm

The Workflow Executor calls this function to determine which task to execute next.
For MVP, sequential-by-list-position is the rule: the first eligible task in `state.tasks`
(by index) whose `depends_on` are fully satisfied wins.

```python
def get_next_task(state: AgentState) -> Task | None:
    """
    Return the next executable task, or None if execution should stop.

    MVP Rule: sequential-by-position.
    The first Task in state.tasks (by list order) that:
      1. Is NOT already in state.completed_tasks, AND
      2. Has ALL of its depends_on task_ids in state.completed_tasks
    is returned.

    Returns None in two cases:
      (a) len(completed_tasks) == len(tasks)  →  all tasks done, signal completion.
      (b) Remaining tasks exist but none are ready  →  dependency deadlock (guard).

    The caller (execution loop) distinguishes (a) from (b) by checking counts.
    """
    completed = set(state.completed_tasks)

    for task in state.tasks:
        if task.task_id in completed:
            continue
        if all(dep in completed for dep in task.depends_on):
            return task

    return None
```

### Caller Responsibility

```python
next_task = get_next_task(state)

if next_task is None:
    if len(state.completed_tasks) == len(state.tasks):
        # Normal completion
        state.status = "completed"
        state.current_task_id = ""
        state.current_agent = ""
    else:
        # Deadlock — should not occur with valid predefined workflows
        state.status = "failed"
        state.error_message = (
            f"Dependency deadlock: {len(state.completed_tasks)} of "
            f"{len(state.tasks)} tasks completed but no task is ready."
        )
```

### performance_report Parallelism Note

`t1` and `t2` in `performance_report` both have `depends_on=[]`. The algorithm above will
always return `t1` first (it appears first in the list), then `t2`, preserving sequential
semantics for MVP. If parallelism is introduced post-MVP, replace this function with a
scheduler that returns all ready tasks and dispatches them concurrently.

---

## 6. Human Approval Gate

The human approval gate is **not an agent**. It is a Workflow Executor checkpoint that
pauses execution, persists state, and waits for an external API call before resuming.

### 6.1 Gate Identification

A task is a human gate if and only if:

```python
task.agent == "human"
```

Current human gates:

- hire_employee / t5 / hr_select_candidates
- hire_employee / t7 / hr_offer_approval
- hire_employee / t8 / manager_approval

The executor must check `task.agent == "human"` before routing to the Agent Router.

### 6.2 Pause Sequence (Executor)

When `get_next_task()` returns a task with `agent == "human"`:

```
1. Append "started" log entry for the gate task.
2. Set state.current_task_id = task.task_id
3. Set state.current_agent  = "human"
4. Set state.status                 = "paused"
5. Set state.awaiting_human_input   = True
6. Persist AgentState to MongoDB.
7. Return state to the API layer.
   ← DO NOT BLOCK. The executor's call returns here.
```

The API layer is responsible for exposing the workflow ID to the frontend so that an authorized user (HR or Manager) can submit their decision.

### 6.3 Resume Sequence (API → Executor)

The FastAPI layer receives the manager's decision and calls:

```python
# Signature for workflow_executor.py
def resume_workflow(
    workflow_id: str,
    approval_status: str,             # "approved" | "rejected"
    human_feedback: str | None = None, # Optional comments
    human_input_data: dict | None = None,
) -> AgentState:
```

The executor then executes the following steps atomically before any further task dispatch:

```
1.  Load AgentState from MongoDB by workflow_id.
2.  Assert state.status == "paused"
        and state.awaiting_human_input == True.
    Raise ValueError if either assertion fails.
3.  gate_task_id = state.current_task_id   # e.g. "t5", "t7", or "t8"
4.  Set state.awaiting_human_input = False
5.  Set state.approval_status   = approval_status
6.  Set state.human_feedback    = human_feedback
7.  Set state.outputs[gate_task_id] = {"approval_status": approval_status,"human_feedback": human_feedback,"human_input_data": human_input_data or {}}
8a. IF approval_status == "approved":
        state.completed_tasks.append(gate_task_id)
        Append "completed" log entry for gate_task_id.
        Set state.status = "running"
        Continue the execution loop (_execute_loop).

8b. IF approval_status == "rejected":
        state.completed_tasks.append(gate_task_id)
        feedback_text = human_feedback or "(no comment provided)"
        Append "failed" log entry with error = f"Rejected: {feedback_text}"
        Set state.status        = "failed"
        Set state.error_message = f"Manager rejected offer: {feedback_text}"
        Set state.current_task_id = ""
        Set state.current_agent   = ""
        Persist and return state (do NOT continue the loop).
```

### 6.4 State Snapshot After Gate Resolution

```python
# ── After approval ──────────────────────────────────────────
state.outputs[gate_task_id] = {
    "approval_status": "approved",
    "human_feedback": human_feedback,
    "human_input_data": human_input_data or {}
}
state.approval_status         == "approved"
state.awaiting_human_input    == False
state.human_feedback          == "<manager comment>"  # or None if not provided
state.completed_tasks == [..., gate_task_id]
state.status == "running"

# ── After rejection ─────────────────────────────────────────
state.outputs[gate_task_id] = {
    "approval_status": "rejected",
    "human_feedback": human_feedback,
    "human_input_data": human_input_data or {}
}
state.approval_status         == "rejected"
state.awaiting_human_input    == False
state.human_feedback          == "<manager comment>"  # or None if not provided
state.completed_tasks == [..., gate_task_id]
state.status                  == "failed"
state.error_message           == "Manager rejected offer: <manager comment or (no comment provided)>"
state.current_task_id         == ""
state.current_agent           == ""
```

### 6.5 What the Reporting Agent (t9) Reads

After final approval, `t9 generate_hiring_summary` reads:

- `state.outputs["t6"]["offer_details"]`
- `state.approval_status`

The Reporting Agent receives the full AgentState and may also inspect:

- `state.outputs["t5"]`
- `state.outputs["t7"]`
- `state.outputs["t8"]`

to include human decisions in the final summary.
---

## 7. Output Storage Convention

Agents return plain dicts. The Workflow Executor is solely responsible for writing to
`state.outputs`. Agents must never do this themselves.

### Storage Pattern

```python
# In workflow_executor.py — after agent.run() returns:
result = agent.run(task, state)
state.outputs[task.task_id] = result          # always keyed by task_id string
state.completed_tasks.append(task.task_id)
# Append "completed" log entry
# Persist state
```

### Rules

- Keys are always the `task_id` string literal (`"t1"`, `"t2"`, ..., `"t9"`).
- Values are the exact dict returned by `agent.execute()`.
- Downstream agents access upstream outputs via `state.outputs["tN"]["key"]`
  or through `BaseAgent.get_output(state, "tN")["key"]`.
- The precise keys within each output dict are defined in `task_contracts.md`
  and summarised in [Section 14](#14-output-key-quick-reference).
- A task's output is written exactly once. The executor must not overwrite an existing
  `outputs[task_id]` entry.

---

## 8. Error Handling

### 8.1 Agent Errors

`BaseAgent.run()` wraps all agent-raised exceptions as `AgentExecutionError` before
they reach the executor. The executor handles only this type:

```python
# In _execute_loop — after agent.run() call:
try:
    result = agent.run(task, state)
    state.outputs[task.task_id] = result
    state.completed_tasks.append(task.task_id)
    # log "completed"
except AgentExecutionError as e:
    state.status        = "failed"
    state.error_message = str(e)                # full message inc. task_id / action
    state.current_task_id = ""
    state.current_agent   = ""
    state.execution_log.append({
        "task_id":   e.task_id,
        "agent":     e.agent,
        "action":    e.action,
        "status":    "failed",
        "timestamp": utc_now(),
        "error":     str(e.cause),
    })
    # Persist and break loop
```

The `AgentExecutionError` message format (from `base_agent.py`) is:

```
[{agent}] Task '{task_id}' (action='{action}') failed: {cause}
```

### 8.2 Unknown Agent Type

`get_agent()` in `agent_router.py` raises `ValueError` for unrecognised `task.agent`
strings (including `"human"`, which is not routed). The executor wraps this as a
failed state before any agent call is attempted:

```python
try:
    agent = get_agent(task)
except ValueError as e:
    # Wrap and fail immediately — same terminal behaviour as AgentExecutionError
    state.status        = "failed"
    state.error_message = str(e)
    # log "failed" for current task
    break
```

### 8.3 Dependency Deadlock

Handled by the caller of `get_next_task()`. See [Section 5](#5-task-readiness-algorithm).
This condition cannot occur with the predefined workflows but must be guarded.

### 8.4 Invalid Resume Call

Raises:
    ValueError:
        - workflow_id not found
        - workflow is not paused
        - awaiting_human_input is False
        - approval_status is not one of {"approved", "rejected"}

```python
if state.status != "paused" or not state.awaiting_human_input:
    raise ValueError(
        f"Cannot resume workflow '{workflow_id}': "
        f"status={state.status}, awaiting_human_input={state.awaiting_human_input}"
    )

if approval_status not in {"approved", "rejected"}:
    raise ValueError(
        "approval_status must be 'approved' or 'rejected'"
    )    
```

### 8.5 Error Recovery (MVP)

MVP does not implement retry or partial recovery. A `"failed"` state is terminal.
The caller (FastAPI route) should surface `state.error_message` to the client.
A new workflow execution requires a fresh call to `start_workflow()`.

---

## 9. Workflow Executor Contract

`workflow_executor.py` exposes two public functions and one private execution loop.

### 9.1 start_workflow

```python
def start_workflow(planner_input: PlannerInput) -> AgentState:
    """
    Initialize and run a workflow from the beginning.

    Steps:
      1. Call run_planner(planner_input) → (PlannerOutput, enriched_params)
      2. Build AgentState via initialize_state()
      3. Persist AgentState to MongoDB (created_at timestamp added at this layer)
      4. Enter _execute_loop(state)
      5. Return the final AgentState (completed | paused | failed)

    The returned state is the API layer's source of truth for
    the workflow's current condition.

    Raises:
        ValueError: if planner_input.objective_id has no defined workflow
                    (raised by run_planner before state is created).
    """
```

### 9.2 resume_workflow

```python
def resume_workflow(
    workflow_id: str,
    approval_status: str,   # "approved" | "rejected"
    human_feedback: str | None = None,
    human_input_data: dict | None = None,
) -> AgentState:
    """
    Resume a paused workflow after the human approval gate.

    Steps:
      1. Load AgentState from MongoDB by workflow_id
      2. Assert status == "paused" and awaiting_human_input == True
      3. Apply approval decision (see Section 6.3)
      4. If approved: re-enter _execute_loop(state)
      5. If rejected: set terminal failed state, return
      6. Return final AgentState

    Raises:
    ValueError:
        - workflow_id not found
        - workflow is not paused
        - awaiting_human_input is False
        - approval_status is not one of {"approved", "rejected"}
    """
```

### 9.3 Execution Loop (Pseudocode)

```python
def _execute_loop(state: AgentState) -> AgentState:
    """
    Core execution driver. Runs until completion, pause, or failure.
    Modifies state in place and persists at each checkpoint.
    """
    while True:
        next_task = get_next_task(state)

        # ── Terminal: no task returned ───────────────────────────
        if next_task is None:
            if len(state.completed_tasks) == len(state.tasks):
                state.status        = "completed"
                state.current_task_id = ""
                state.current_agent   = ""
            else:
                state.status        = "failed"
                state.error_message = "Dependency deadlock."
            persist(state)
            break

        # ── Update cursor ─────────────────────────────────────────
        state.current_task_id = next_task.task_id
        state.current_agent   = next_task.agent

        # ── Human gate ───────────────────────────────────────────
        if next_task.agent == "human":
            state.status              = "paused"
            state.awaiting_human_input = True
            _log(state, next_task, "started")
            persist(state)
            break   # Return to API layer; resume via resume_workflow()

        # ── Normal task ──────────────────────────────────────────
        _log(state, next_task, "started")
        persist(state)

        try:
            agent  = get_agent(next_task)            # agent_router
            result = agent.run(next_task, state)     # BaseAgent.run()

            state.outputs[next_task.task_id] = result
            state.completed_tasks.append(next_task.task_id)
            _log(state, next_task, "completed")

        except AgentExecutionError as e:
            state.status        = "failed"
            state.error_message = str(e)
            state.current_task_id = ""
            state.current_agent   = ""
            _log(state, next_task, "failed", error=str(e.cause))
            persist(state)
            break

        except ValueError as e:
            # Unknown agent type from get_agent()
            state.status        = "failed"
            state.error_message = str(e)
            state.current_task_id = ""
            state.current_agent   = ""
            _log(state, next_task, "failed", error=str(e))
            persist(state)
            break

        persist(state)

    return state
```

---

## 10. Agent Router Contract

`agent_router.py` exposes a single function. It is called by the execution loop for every
non-human task.

### 10.1 Function Signature

```python
def get_agent(task: Task) -> BaseAgent:
    """
    Map task.agent to the appropriate BaseAgent subclass instance.

    Args:
        task: The Task to be dispatched.

    Returns:
        A concrete BaseAgent subclass instance capable of handling task.action.

    Raises:
        ValueError: If task.agent is "human" (not an agent — handled by executor).
        ValueError: If task.agent is not a recognised agent type string.
    """
```

### 10.2 Agent Type → Class Mapping

| `task.agent` value | Agent Class (to implement) | Workflows |
|---|---|---|
| `"recruitment"` | `RecruitmentAgent` | `hire_employee` |
| `"hr"` | `HRAgent` | `onboard_employee`, `performance_report`, `performance_review` |
| `"sales"` | `SalesAgent` | `sales_outreach`, `performance_report` |
| `"research"` | `ResearchAgent` | `sales_outreach`, `market_research` |
| `"reporting"` | `ReportingAgent` | all six workflows |
| `"human"` | _(not routed — raise ValueError)_ | `hire_employee` |

### 10.3 Instantiation Strategy

For MVP, agent instances may be created fresh per call (stateless dispatch):

```python
_AGENT_MAP: dict[str, type[BaseAgent]] = {
    "recruitment": RecruitmentAgent,
    "hr":          HRAgent,
    "sales":       SalesAgent,
    "research":    ResearchAgent,
    "reporting":   ReportingAgent,
}

def get_agent(task: Task) -> BaseAgent:
    if task.agent == "human":
        raise ValueError(
            f"Task '{task.task_id}' has agent='human' — "
            "human gates must be handled by the executor, not routed."
        )
    agent_class = _AGENT_MAP.get(task.agent)
    if agent_class is None:
        raise ValueError(
            f"Unknown agent type: '{task.agent}'. "
            f"Expected one of: {list(_AGENT_MAP.keys())}"
        )
    return agent_class()
```

---

## 11. LangGraph Integration Notes

LangGraph is used for workflow **execution** state management, not for planning.
The Planner (`planner.py`) remains a plain Python function — it is called once at the
start and its output seeds the LangGraph graph's initial state.

### 11.1 State Schema

`AgentState` (already a Pydantic model) is passed directly as the LangGraph state type.
LangGraph supports Pydantic models natively as state schemas.

### 11.2 Recommended Node Structure

| Node | LangGraph Role | Responsibility |
|---|---|---|
| `initialize_node` | Entry | Call `run_planner()`, build `AgentState`, persist |
| `task_router_node` | Conditional | Call `get_next_task()`, branch to: agent_executor, human_gate, complete, or fail |
| `agent_executor_node` | Standard | Call `get_agent(task).run(task, state)`, store output, append log |
| `human_gate_node` | Interrupt | Set `paused` + `awaiting_human_input`, emit interrupt, persist |
| `human_resume_node` | Resume | Apply approval decision, route to agent_executor or failure |
| `completion_node` | Terminal | Set `status = "completed"`, clear cursor, persist |
| `failure_node` | Terminal | Set `status = "failed"`, set `error_message`, persist |

### 11.3 Edge Logic

```
initialize_node
    └─► task_router_node

task_router_node
    ├─► agent_executor_node   (next_task exists and task.agent != "human")
    ├─► human_gate_node       (next_task exists and task.agent == "human")
    ├─► completion_node       (next_task is None and all tasks complete)
    └─► failure_node          (next_task is None and deadlock detected)

agent_executor_node
    ├─► task_router_node      (success — loop back for next task)
    └─► failure_node          (AgentExecutionError or ValueError raised)

human_gate_node
    └─► [interrupt / pause — graph yields here]

human_resume_node             (called via graph.invoke() with external decision)
    ├─► task_router_node      (approval_status == "approved")
    └─► failure_node          (approval_status == "rejected")

completion_node  ─► END
failure_node     ─► END
```

### 11.4 Human-in-the-Loop with LangGraph Interrupts

Use LangGraph's `NodeInterrupt` (or `interrupt()` in LangGraph 0.2+) inside
`human_gate_node` to suspend the graph. The graph state (full `AgentState`) is persisted
to the LangGraph checkpointer (which can be backed by the same MongoDB instance).

Resume via:

```python
graph.invoke(
    {"approval_status": "approved", "human_feedback": "Looks good."},
    config={"configurable": {"thread_id": workflow_id}},
)
```

The `human_resume_node` reads these fields from the incoming state update.

---

## 12. MongoDB Persistence Notes

`AgentState` is the intended document body. Timestamps and MongoDB metadata are **not**
added to the Pydantic model — they are handled at the persistence layer only.

AgentState is the primary persistence model for workflow execution.

PlannerOutput is a transient planning artifact used only during workflow initialization.

After workflow creation, AgentState becomes the source of truth for execution state, recovery, pause/resume, and persistence.

### 12.1 Collection

```
Collection: workflows
```

### 12.2 Document Structure

```python
{
    "_id":        state.workflow_id,          # "wf_<uuid4>"
    "created_at": datetime,                   # Set once at initialization
    "updated_at": datetime,                   # Updated on every persist() call
    "state":      state.model_dump(),         # Full AgentState serialized
}
```

Do not embed timestamps inside `AgentState`. The wrapper document handles them.

### 12.3 Required Persistence Points

| When | Operation |
|---|---|
| After `initialize_state()` | INSERT — create document |
| Before human gate pause | REPLACE — capture `paused` state |
| After each agent task completes | REPLACE — capture output + log entry |
| After `resume_workflow()` applies decision | REPLACE — capture approval fields |
| On `status = "failed"` | REPLACE — capture `error_message` |
| On `status = "completed"` | REPLACE — capture final state |

### 12.4 Query Patterns

```python
# Load by workflow_id
db.workflows.find_one({"_id": workflow_id})

# List all paused workflows (pending manager approvals)
db.workflows.find({"state.status": "paused", "state.awaiting_human_input": True})

# List all workflows for a given objective
db.workflows.find({"state.objective_id": "hire_employee"})
```

---

## 13. Workflow Dependency Maps

Visual DAGs for all six workflows. Arrow direction = "must complete before".

### hire_employee (strictly sequential, includes human gate)

```
t1 ─► t2 ─► t3 ─► t4 ─► t5[HR] ─► t6 ─► t7[HR] ─► t8[MANAGER] ─► t9

```

| Task | Agent       | Action                   |
| ---- | ----------- | ------------------------ |
| t1   | recruitment | generate_job_description |
| t2   | recruitment | identify_required_skills |
| t3   | recruitment | shortlist_candidates     |
| t4   | recruitment | schedule_interviews      |
| t5   | human       | hr_select_candidates     |
| t6   | recruitment | prepare_offer            |
| t7   | human       | hr_offer_approval        |
| t8   | human       | manager_approval         |
| t9   | reporting   | generate_hiring_summary  |

---

### onboard_employee (strictly sequential)

```
t1 ─► t2 ─► t3 ─► t4 ─► t5
```

| Task | Agent | Action |
|---|---|---|
| t1 | hr | retrieve_employee_details |
| t2 | hr | generate_onboarding_plan |
| t3 | hr | create_welcome_package |
| t4 | hr | create_first_week_tasks |
| t5 | reporting | generate_summary |

---

### sales_outreach (strictly sequential)

```
t1 ─► t2 ─► t3 ─► t4 ─► t5 ─► t6
```

| Task | Agent | Action |
|---|---|---|
| t1 | research | gather_market_data |
| t2 | research | analyze_competitors |
| t3 | sales | create_outreach_strategy |
| t4 | sales | generate_email_sequence |
| t5 | sales | generate_call_scripts |
| t6 | reporting | generate_campaign_summary |

---

### performance_report (fork-join; MVP executes t1 before t2 by list order)

```
t1 ─┐
    ├─► t3 ─► t4 ─► t5 ─┐
t2 ─┘                   ├─► t6
         └─────────────────┘
         (t3 also feeds t6 directly)
```

| Task | Agent | Action | depends_on |
|---|---|---|---|
| t1 | hr | collect_hr_metrics | `[]` |
| t2 | sales | collect_sales_metrics | `[]` |
| t3 | reporting | aggregate_results | `["t1","t2"]` |
| t4 | reporting | generate_kpi_dashboard | `["t3"]` |
| t5 | reporting | generate_executive_summary | `["t4"]` |
| t6 | reporting | generate_recommendations | `["t3","t5"]` |

> **MVP Note**: `t1` and `t2` are both root tasks. Sequential list-position ordering
> means `t1` always executes before `t2`. Parallelism requires a post-MVP scheduler change.

---

### performance_review (mostly sequential; t6 has multi-parent dependency)

```
t1 ─► t2 ─► t3 ─► t4 ─► t5
                    │     │
                    ▼     ▼
                   t6 ◄───┘
                    ▲
                    └── (t3 also feeds t6)
```

| Task | Agent | Action | depends_on |
|---|---|---|---|
| t1 | hr | retrieve_employee_data | `[]` |
| t2 | hr | retrieve_goal_data | `["t1"]` |
| t3 | hr | evaluate_performance | `["t2"]` |
| t4 | hr | generate_rating | `["t3"]` |
| t5 | hr | generate_improvement_plan | `["t4"]` |
| t6 | reporting | generate_review_summary | `["t3","t4","t5"]` |

> Because the chain is sequential, `t3`, `t4`, and `t5` are all guaranteed to be in
> `completed_tasks` before `t6` is attempted. The multi-dependency on t6 is satisfied
> naturally by the linear chain.

---

### market_research (strictly sequential)

```
t1 ─► t2 ─► t3 ─► t4 ─► t5 ─► t6
```

| Task | Agent | Action |
|---|---|---|
| t1 | research | gather_research_data |
| t2 | research | perform_competitor_analysis |
| t3 | research | synthesize_findings |
| t4 | research | generate_recommendations |
| t5 | research | generate_structured_report |
| t6 | reporting | generate_executive_summary |

---

## 14. Output Key Quick Reference

Flat lookup table: workflow + task → the dict key(s) the agent returns and downstream
agents consume via `state.outputs["tN"]["key"]`.

| Workflow | Task | Output Key | Value Type |
|---|---|---|---|
| hire_employee | t1 | `job_description` | `str` |
| hire_employee | t2 | `required_skills` | `list[str]` |
| hire_employee | t3 | `shortlisted_candidates` | `list[Candidate]` |
| hire_employee | t4 | `interview_schedule` | `list[InterviewSchedule]` |
| hire_employee | t5 | `approval_status`, `human_feedback`, `human_input_data` | `dict` |
| hire_employee | t6 | `offer_details`  | `list[OfferDetails]` |
| hire_employee | t7 | `approval_status`, `human_feedback`, `human_input_data` | `dict` |
| hire_employee | t8 | `approval_status`, `human_feedback`, `human_input_data` | `dict`|
| hire_employee | t9 | `hiring_summary` | `str`|
| onboard_employee | t1 | `employee_details` | `EmployeeDetails` |
| onboard_employee | t2 | `onboarding_plan` | `OnboardingPlan` |
| onboard_employee | t3 | `welcome_package` | `WelcomePackage` |
| onboard_employee | t4 | `first_week_tasks` | `list[str]` |
| onboard_employee | t5 | `summary` | `str` |
| sales_outreach | t1 | `market_data` | `MarketData` |
| sales_outreach | t2 | `competitor_analysis` | `CompetitorAnalysis` |
| sales_outreach | t3 | `outreach_strategy` | `OutreachStrategy` |
| sales_outreach | t4 | `email_sequence` | `list[str]` |
| sales_outreach | t5 | `call_scripts` | `list[str]` |
| sales_outreach | t6 | `campaign_summary` | `str` |
| performance_report | t1 | `hr_metrics` | `HRMetrics` |
| performance_report | t2 | `sales_metrics` | `SalesMetrics` |
| performance_report | t3 | `aggregated_metrics` | `AggregatedMetrics` |
| performance_report | t4 | `kpi_dashboard` | `KPIDashboard` |
| performance_report | t5 | `executive_summary` | `str` |
| performance_report | t6 | `recommendations` | `list[str]` |
| performance_review | t1 | `employee_data` | `EmployeeDetails` |
| performance_review | t2 | `goal_data` | `GoalData` |
| performance_review | t3 | `performance_evaluation` | `PerformanceEvaluation` |
| performance_review | t4 | `rating` | `int` |
| performance_review | t5 | `improvement_plan` | `list[str]` |
| performance_review | t6 | `review_summary` | `str` |
| market_research | t1 | `research_data` | `ResearchData` |
| market_research | t2 | `competitor_analysis` | `CompetitorAnalysis` |
| market_research | t3 | `findings` | `list[str]` |
| market_research | t4 | `recommendations` | `list[str]` |
| market_research | t5 | `structured_report` | `StructuredReport` |
| market_research | t6 | `executive_summary` | `str` |

> **Note**: Return values are serialized to plain dicts in `state.outputs`. Model types
> listed above indicate the logical shape; concrete dicts will have the same field names
> as the Pydantic model (via `.model_dump()`). Downstream agents reconstruct typed models
> from these dicts if needed.

---

*End of workflow_state.md*