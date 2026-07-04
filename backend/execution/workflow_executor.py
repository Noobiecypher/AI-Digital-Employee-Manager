"""
workflow_executor.py
====================
Workflow Execution Engine — multi-agent AI Digital Employee Platform.

Sole Responsibilities
---------------------
- Own and mutate AgentState throughout a workflow's entire lifetime.
- Execute workflow tasks sequentially using dependency-based readiness.
- Route non-human tasks through agent_router → BaseAgent.run().
- Identify and handle the human approval gate without routing to agent_router.
- Store task outputs in state.outputs, update tracking fields, write execution logs.
- Persist AgentState at every defined checkpoint (workflow_state.md §12.3).
- Handle and classify all failure modes into a terminal "failed" state.

Architecture Rules (frozen — do not modify)
--------------------------------------------
- Planner is non-AI; objectives and workflows are predefined.
- Agents receive the full AgentState; they return plain dicts.
- Human approval is NOT an agent — it is a Workflow Executor checkpoint.
- Sequential execution only for MVP.
- This module is the SOLE writer to AgentState.

Public API
----------
    create_workflow(planner_input: PlannerInput,) -> AgentState
    execute_workflow(workflow_id: str,) -> AgentState
    start_workflow(planner_input: PlannerInput)  -> AgentState
    resume_workflow(workflow_id, approval_status, human_feedback) -> AgentState

Internal (do not call directly from outside this module)
---------------------------------------------------------
    initialize_state(planner_input)  -> AgentState
    get_next_task(state)             -> Task | None
    _execute_loop(state)             -> AgentState
    _log(state, task, status, *, error)
    _utc_now()                       -> str
    _save_state(state)               -> None      # persistence placeholder
    _load_state(workflow_id)         -> AgentState # persistence placeholder

References
----------
- workflow_state.md  : canonical spec for this file (all section refs below are to it)
- task_contracts.md  : input/output contracts per task
- agent_responsibilities.md : agent action dispatch table
- base_agent.py      : AgentExecutionError definition
- agent_router.py    : get_agent() implementation
- planner.py         : run_planner() implementation
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from backend.models import AgentState, PlannerInput, Task
from backend.planner.planner import run_planner
from backend.execution.agent_router import get_agent
from backend.agent_nodes.base_agent import AgentExecutionError
from backend.database.workflow_repository import WorkflowRepository
from backend.execution.workflow_document_resolution import (
    resolve_initial_document_ids,
    resolve_hire_employee_shortlist_documents,
)


logger = logging.getLogger(__name__)

class WorkflowNotFoundError(ValueError):
    pass


class WorkflowNotPausedError(ValueError):
    pass


class InvalidApprovalStatusError(ValueError):
    pass

# ==============================================================
# PERSISTENCE PLACEHOLDERS
# ==============================================================
#
# _save_state() and _load_state() are the ONLY persistence entry
# points in this module. All other code calls these two functions
# exclusively. When MongoDB is ready, replace only their bodies —
# the rest of the executor is unchanged.
#
# MongoDB document structure (ref: workflow_state.md §12.2):
# {
#     "_id":        state.workflow_id,    # "wf_<uuid4>"
#     "created_at": datetime,             # set once at initialization
#     "updated_at": datetime,             # updated on every _save_state() call
#     "state":      state.model_dump(),   # full AgentState serialized
# }
#
# Collection: workflows
#
# Required persistence points (ref: workflow_state.md §12.3):
#   ① After initialize_state()              → INSERT (create document)
#   ② Before human gate pause              → REPLACE (capture "paused" state)
#   ③ Before each agent task (started)     → REPLACE (capture "started" log entry)
#   ④ After each agent task completes      → REPLACE (capture output + "completed" log)
#   ⑤ After resume_workflow() decision     → REPLACE (capture approval fields)
#   ⑥ On status = "failed"                 → REPLACE (capture error_message)
#   ⑦ On status = "completed"              → REPLACE (capture final state)
# ==============================================================

_repository: WorkflowRepository = WorkflowRepository()
"""MongoDB persistence repository."""


def _save_state(state: AgentState) -> None:
    """
    Persist AgentState to the database (upsert by workflow_id).

    PLACEHOLDER — replace body with:

        db.workflows.replace_one(
            {"_id": state.workflow_id},
            {
                "_id":        state.workflow_id,
                "updated_at": datetime.now(timezone.utc),
                "state":      state.model_dump(),
            },
            upsert=True,
        )

    The "created_at" timestamp is set only on the first INSERT by
    initialising the document without upsert and letting a second call
    handle conflict, or by using a conditional update pipeline. See
    MongoDB docs for $setOnInsert.
    """
    _repository.save(state)
    logger.debug(
        "[%s] State persisted — status=%s current_task=%s",
        state.workflow_id,
        state.status,
        state.current_task_id or "(none)",
    )


def _load_state(workflow_id: str) -> AgentState:
    """
    Load AgentState from the database by workflow_id.

    PLACEHOLDER — replace body with:

        doc = db.workflows.find_one({"_id": workflow_id})
        if doc is None:
            raise ValueError(f"Workflow '{workflow_id}' not found.")
        return AgentState.model_validate(doc["state"])

    Note: AgentState.model_validate() is used (not AgentState(**doc)) so that
    Pydantic v2's smart-union validation correctly reconstructs the params
    Union field from the serialised dict.

    Raises:
        ValueError: If workflow_id is not present in the store.
    """
    try:
        return _repository.load(workflow_id)
    except KeyError:
        raise WorkflowNotFoundError(
            f"Workflow '{workflow_id}' not found."
        )

# ==============================================================
# PUBLIC PERSISTENCE HELPERS
# ==============================================================

def save_state(state: AgentState) -> None:
    """Public persistence wrapper for API layer."""
    _save_state(state)


def load_state(workflow_id: str) -> AgentState:
    """Public persistence wrapper for API layer."""
    return _load_state(workflow_id)

def list_workflow_ids() -> list[str]:
    """Public persistence wrapper for API layer."""
    return _repository.list_ids()

# ==============================================================
# INTERNAL HELPERS
# ==============================================================

def _utc_now() -> str:
    """Return current UTC time as an ISO 8601 string, e.g. '2025-08-01T10:23:45Z'."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _log(
    state: AgentState,
    task: Task,
    status: str,
    *,
    error: str | None = None,
) -> None:
    """
    Append a single structured entry to state.execution_log.

    Log schema (ref: workflow_state.md §3):
        task_id   : str        — e.g. "t1"
        agent     : str        — e.g. "recruitment" | "human"
        action    : str        — e.g. "generate_job_description"
        status    : str        — "started" | "completed" | "failed"
        timestamp : str        — ISO 8601 UTC
        error     : str | None — None unless status == "failed"

    Note: The "skipped" status is reserved for future use and must NOT
    be emitted by this function in MVP (ref: workflow_state.md §3).

    Args:
        state:  The workflow state being mutated.
        task:   The Task object whose identity is recorded (task_id, agent, action).
        status: Log event type. One of "started" | "completed" | "failed".
        error:  Cause string; None for non-failure entries.
    """
    state.execution_log.append(
        {
            "task_id":   task.task_id,
            "agent":     task.agent,
            "action":    task.action,
            "status":    status,
            "timestamp": _utc_now(),
            "error":     error,
        }
    )


def _log_agent_error(state: AgentState, e: AgentExecutionError) -> None:
    """
    Append a "failed" log entry for an AgentExecutionError.

    This function bypasses _log() intentionally. Spec §8.1 requires the log
    entry to use e.task_id, e.agent, e.action, and str(e.cause) — the fields
    carried on the error object itself — not the current next_task fields.
    These diverge when an agent raises AgentExecutionError with a task_id
    different from the task being dispatched (e.g. a sub-task reference).
    Using e.* produces the most accurate audit trail in all cases.

    Ref: workflow_state.md §8.1
    """
    state.execution_log.append(
        {
            "task_id":   e.task_id,
            "agent":     e.agent,
            "action":    e.action,
            "status":    "failed",
            "timestamp": _utc_now(),
            "error":     str(e.cause),
        }
    )


# ==============================================================
# STATE INITIALIZATION
# ==============================================================

def initialize_state(planner_input: PlannerInput) -> AgentState:
    """
    Build the initial AgentState from a PlannerInput.

    Delegates to run_planner() which:
      - Validates the objective_id (fails fast before enrichment).
      - Enriches params using mock data sources.
      - Retrieves a deep-copied predefined task list from WORKFLOWS.
      - Generates a unique workflow_id ("wf_<uuid4>").

    All remaining AgentState fields take their Pydantic defaults:
        status               = "running"
        completed_tasks      = []
        outputs              = {}
        execution_log        = []
        current_task_id      = ""
        current_agent        = ""
        approval_status      = "pending"
        awaiting_human_input = False
        human_feedback       = None
        error_message        = None

    Ref: workflow_state.md §2

    Args:
        planner_input: PlannerInput containing objective_id and params.

    Returns:
        A fresh AgentState ready to be passed to _execute_loop().

    Raises:
        ValueError: If objective_id has no defined workflow (raised by run_planner).
    """
    planner_output, enriched_params = run_planner(planner_input)

    # M6.6 — resolve initial document_ids BEFORE the first persist.
    # Explicit-selection workflows (market_research, performance_report)
    # raise here (DocumentAccessError subclasses) if any supplied ID is
    # invalid — this fails workflow creation atomically, before any
    # AgentState is persisted. Entity-linked workflows (sales_outreach,
    # performance_review) never raise here; they silently resolve to
    # whatever valid linked documents currently exist (possibly none).
    # hire_employee/onboard_employee resolve to [] here by design — see
    # resolve_initial_document_ids() docstring.
    document_ids = resolve_initial_document_ids(
        planner_output.objective_id, enriched_params
    )

    return AgentState(
        workflow_id=planner_output.workflow_id,
        objective_id=planner_output.objective_id,
        params=enriched_params,
        tasks=planner_output.tasks,
        document_ids=document_ids,
        # All remaining fields take defaults as documented above.
    )


# ==============================================================
# TASK READINESS ALGORITHM
# ==============================================================

def get_next_task(state: AgentState) -> Task | None:
    """
    Return the next executable task, or None if execution should stop.

    MVP Rule — sequential-by-list-position (ref: workflow_state.md §5):

    The first Task in state.tasks (by list order) that satisfies both:
      1. task.task_id NOT in state.completed_tasks
      2. ALL task.depends_on ids ARE in state.completed_tasks
    is returned.

    Returns None in exactly two cases:
      (a) len(completed_tasks) == len(tasks): all done → signal completion.
      (b) Remaining tasks exist but none are eligible → dependency deadlock.

    The caller (_execute_loop) distinguishes (a) from (b) by comparing
    len(state.completed_tasks) against len(state.tasks).

    Performance note: completed_tasks is converted to a set once per call
    for O(1) membership tests during the task scan.
    """
    completed = set(state.completed_tasks)

    for task in state.tasks:
        if task.task_id in completed:
            continue
        if all(dep in completed for dep in task.depends_on):
            return task

    return None


# ==============================================================
# EXECUTION LOOP
# ==============================================================

def _execute_loop(state: AgentState) -> AgentState:
    """
    Core execution driver. Drives the workflow until it reaches a
    terminal state: "completed", "paused" (human gate), or "failed".

    Mutates state in-place at every checkpoint and persists after
    every significant state change. The loop is re-entered after a
    human gate resume by calling this function again from resume_workflow().

    State transitions handled here (ref: workflow_state.md §4.3):
        running   → completed  (all tasks done)
        running   → paused     (human gate reached)
        running   → failed     (agent error, routing error, deadlock,
                                type error, overwrite attempt,
                                or unexpected exception)

    Returns:
        The AgentState with status "completed" | "paused" | "failed".
    """
    if state.status != "running":
        raise ValueError(
            f"_execute_loop() requires state.status='running'; "
            f"got {state.status!r} for workflow '{state.workflow_id}'. "
            "Call start_workflow() for new workflows or resume_workflow() "
            "for paused workflows."
        )

    while True:

        next_task = get_next_task(state)

        # ── No executable task returned ────────────────────────────
        if next_task is None:
            if len(set(state.completed_tasks)) == len(state.tasks):
                # (a) Normal completion — every task is in completed_tasks.
                state.status = "completed"
                state.current_task_id = ""
                state.current_agent = ""
                logger.info(
                    "[%s] Workflow COMPLETED — objective=%s tasks=%d",
                    state.workflow_id,
                    state.objective_id,
                    len(state.tasks),
                )
            else:
                # (b) Dependency deadlock — remaining tasks but none eligible.
                # Cannot occur with valid predefined workflows; guards against
                # state corruption or future dynamic workflow bugs.
                state.status = "failed"
                state.error_message = (
                    f"Dependency deadlock: {len(state.completed_tasks)} of "
                    f"{len(state.tasks)} tasks completed but no task is ready. "
                    f"Completed: {state.completed_tasks}"
                )
                state.current_task_id = ""
                state.current_agent = ""
                logger.error(
                    "[%s] DEADLOCK — %s",
                    state.workflow_id,
                    state.error_message,
                )
            _save_state(state)
            break

        # ── Update execution cursor (ref: workflow_state.md §1.3) ─────
        # Written before dispatch so observers can see which task is active.
        state.current_task_id = next_task.task_id
        state.current_agent = next_task.agent

        # ── Human approval gate (ref: workflow_state.md §6) ───────────
        #
        # Identified by task.agent == "human". This is NOT an agent.
        # Never routed through agent_router. The executor pauses here
        # and returns control to the API layer. Resume happens via
        # resume_workflow() when the manager submits a decision.
        #
        # Pause sequence (ref: workflow_state.md §6.2):
        #   1. Append "started" log entry.
        #   2. Set status = "paused".
        #   3. Set awaiting_human_input = True.
        #   4. Persist state.
        #   5. Break — do NOT block; return to caller.
        if next_task.agent == "human":
            _log(state, next_task, "started")
            state.status = "paused"
            state.awaiting_human_input = True
            _save_state(state)
            logger.info(
                "[%s] Workflow PAUSED at human gate — task_id=%s action=%s",
                state.workflow_id,
                next_task.task_id,
                next_task.action,
            )
            break

        # ── Normal agent task ──────────────────────────────────────────
        #
        # Execution sequence:
        #   1. Log "started" and persist (checkpoint ③).
        #   2. Resolve agent via agent_router.
        #   3. Execute agent; collect result dict.
        #   4. Validate result type.
        #   5. Guard against output overwrite.
        #   6. Store result; mark task complete; log "completed".
        #   7. Persist (checkpoint ④).
        _log(state, next_task, "started")
        _save_state(state)  # Checkpoint ③ — persist "started" before any agent call.

        try:
            # ── Routing ─────────────────────────────────────────────
            # get_agent() raises ValueError for "human" or unknown agent type.
            agent = get_agent(next_task)

            # ── Execution ────────────────────────────────────────────
            # BaseAgent.run() wraps ALL internal exceptions as AgentExecutionError
            # before they reach this scope.
            result = agent.run(next_task, state)

            # ── Output type validation ───────────────────────────────
            # Agents must return a plain dict. Pydantic model instances,
            # None, or other types indicate a contract violation.
            if not isinstance(result, dict):
                raise AgentExecutionError(
                    task_id=next_task.task_id,
                    agent=next_task.agent,
                    action=next_task.action,
                    cause=TypeError(
                        f"Agent '{next_task.agent}' returned "
                        f"'{type(result).__name__}' for task "
                        f"'{next_task.task_id}'. Expected dict. "
                        "Ensure agent.execute() returns a plain dict "
                        "(use .model_dump() for Pydantic models)."
                    ),
                )

            # ── Output overwrite protection ───────────────────────────
            # Each task's output is written exactly once (ref: §7).
            # A collision here indicates an executor bug — task was
            # returned by get_next_task() despite already having output.
            if next_task.task_id in state.outputs:
                raise AgentExecutionError(
                    task_id=next_task.task_id,
                    agent=next_task.agent,
                    action=next_task.action,
                    cause=RuntimeError(
                        f"Output for task '{next_task.task_id}' already "
                        "exists in state.outputs. Refusing overwrite. "
                        "This is an executor bug — task was dispatched "
                        "despite being present in state.outputs."
                    ),
                )

            # ── Commit ────────────────────────────────────────────────
            state.outputs[next_task.task_id] = result
            state.completed_tasks.append(next_task.task_id)
            _log(state, next_task, "completed")
            logger.info(
                "[%s] Task COMPLETED — task_id=%s agent=%s action=%s",
                state.workflow_id,
                next_task.task_id,
                next_task.agent,
                next_task.action,
            )

            # ── M6.6 — Hire Employee post-t3 document resolution ──────
            # Executor-owned checkpoint: only after shortlist_candidates
            # completes do we know WHICH candidates are eligible for
            # resume document access. Resolves only shortlisted (never
            # rejected) candidates' trusted resume document IDs and
            # appends them to state.document_ids, deduplicated preserving
            # order. Persisted by the normal checkpoint ④ below — no
            # extra persist call needed here.
            if (
                state.objective_id == "hire_employee"
                and next_task.agent == "recruitment"
                and next_task.action == "shortlist_candidates"
            ):
                shortlisted = result.get("shortlisted_candidates", [])
                new_ids = resolve_hire_employee_shortlist_documents(shortlisted)
                state.document_ids = list(
                    dict.fromkeys([*state.document_ids, *new_ids])
                )

        except AgentExecutionError as e:
            # Full failure context (task_id, agent, action, cause) is carried
            # on the error object, not on next_task. Use e.* fields for the log
            # entry to get the most accurate audit trail (ref: workflow_state.md §8.1).
            # See _log_agent_error() for explanation of why _log() is bypassed here.
            state.status = "failed"
            state.error_message = str(e)
            state.current_task_id = ""
            state.current_agent = ""
            _log_agent_error(state, e)
            _save_state(state)  # Checkpoint ⑥
            logger.error(
                "[%s] Task FAILED (AgentExecutionError) — "
                "task_id=%s agent=%s action=%s cause=%s",
                state.workflow_id,
                e.task_id,
                e.agent,
                e.action,
                e.cause,
            )
            break

        except ValueError as e:
            # Raised by get_agent() for an unknown agent type string or when
            # task.agent == "human" reaches the router erroneously.
            # ValueError has no task_id/agent/action attributes —
            # use next_task fields for the log entry (ref: workflow_state.md §8.2).
            state.status = "failed"
            state.error_message = str(e)
            state.current_task_id = ""
            state.current_agent = ""
            _log(state, next_task, "failed", error=str(e))
            _save_state(state)  # Checkpoint ⑥
            logger.error(
                "[%s] Task FAILED (routing ValueError) — task_id=%s error=%s",
                state.workflow_id,
                next_task.task_id,
                e,
            )
            break

        except Exception as e:  # noqa: BLE001
            # Catch-all for unexpected exceptions not covered by the two handlers
            # above (e.g. OS errors, import failures, network errors from mocks).
            # BaseAgent.run() wraps most internal exceptions as AgentExecutionError,
            # but this guard ensures the executor never propagates raw exceptions
            # upward and always leaves state in a deterministic terminal condition.
            state.status = "failed"
            state.error_message = (
                f"Unexpected error during task '{next_task.task_id}' "
                f"({next_task.agent}/{next_task.action}): {e}"
            )
            state.current_task_id = ""
            state.current_agent = ""
            _log(state, next_task, "failed", error=str(e))
            _save_state(state)  # Checkpoint ⑥
            logger.exception(
                "[%s] Task FAILED (unexpected exception) — task_id=%s",
                state.workflow_id,
                next_task.task_id,
            )
            break

        # Checkpoint ④ — reached only when the try block succeeds.
        # Persists: completed output, updated completed_tasks, "completed" log.
        _save_state(state)

    return state


# ==============================================================
# PUBLIC API
# ==============================================================

def create_workflow(planner_input: PlannerInput,) -> AgentState:
    """
    Create and persist workflow state
    without executing it.
    """

    state = initialize_state(
        planner_input
    )

    _save_state(state)

    return state

def execute_workflow(workflow_id: str,) -> AgentState:
    """
    Load and execute an existing workflow.
    """

    state = _load_state(
        workflow_id
    )

    return _execute_loop(state)

def start_workflow(planner_input: PlannerInput) -> AgentState:
    """
    Initialize and execute a workflow from scratch.

    This is the main entry point for the FastAPI route layer when a
    manager submits a new workflow objective.

    Steps (ref: workflow_state.md §9.1):
      1. Call initialize_state() → validates objective, enriches params,
         builds fresh AgentState with status="running".
      2. Persist initial state (checkpoint ① — INSERT equivalent).
      3. Enter _execute_loop(state).
      4. Return final AgentState (status: "completed" | "paused" | "failed").

    The returned state is the API layer's source of truth. If
    state.status == "paused", the API should surface state.workflow_id
    to the frontend so a manager can submit their decision via
    resume_workflow().

    Args:
        planner_input: PlannerInput containing objective_id and params.

    Returns:
        Final AgentState after the execution loop halts.

    Raises:
        ValueError: If objective_id has no defined workflow (from run_planner).
                    Raised before any state is created or persisted.
    """
    state = initialize_state(planner_input)
    logger.info(
        "[%s] Workflow STARTED — objective=%s",
        state.workflow_id,
        state.objective_id,
    )
    _save_state(state)  # Checkpoint ① — initial INSERT before any task runs.
    return _execute_loop(state)


def resume_workflow(
    workflow_id: str,
    approval_status: str,
    human_feedback: str | None = None,
    human_input_data: dict | None = None,
) -> AgentState:
    """
    Resume a paused workflow after the human approval gate is resolved.

    Called by the FastAPI layer when a manager submits their decision.
    Applies the approval decision atomically — all state mutations occur
    before any persist call — then either continues execution or sets a
    terminal "failed" state.

    Steps (ref: workflow_state.md §6.3):
      1. Load AgentState from persistence by workflow_id.
      2. Validate: status must be "paused" AND awaiting_human_input must be True.
      3. Validate: approval_status must be "approved" or "rejected".
      4. Capture gate_task_id (= state.current_task_id at pause).
      5. Locate the gate Task object in state.tasks (corruption guard).
      6. Apply decision atomically:
           - Set awaiting_human_input = False.
           - Set approval_status and human_feedback on state.
           - Store gate output: outputs[gate_task_id] = {"approval_status": ...}.
      7a. If "approved":
           - Append gate_task_id to completed_tasks.
           - Log "completed" for the gate.
           - Set status = "running".
           - Persist (checkpoint ⑤).
           - Re-enter _execute_loop(state).
      7b. If "rejected":
           - Append gate_task_id to completed_tasks.
           - Log "failed" for the gate.
           - Set status = "failed", error_message, clear cursor.
           - Persist (checkpoint ⑥).
           - Return state immediately (do NOT re-enter _execute_loop).

    Note on approval_status source of truth (ref: workflow_state.md §6.5):
        state.approval_status is authoritative.
        state.outputs[gate_task_id]["approval_status"] is the companion record
        for consistency with the standard task-output pattern. Downstream agents
        (e.g. t7 generate_hiring_summary) must read from state.approval_status,
        not from state.outputs["t6"].

    Args:
        workflow_id:     The "wf_<uuid4>" identifier of the paused workflow.
        approval_status: "approved" | "rejected"
        human_feedback:  Optional manager comment attached to the decision.

    Returns:
        Final AgentState (status: "completed" | "failed").

    Raises:
        ValueError: workflow_id not found in persistence.
        ValueError: Workflow is not paused or not awaiting human input.
        ValueError: gate_task_id is empty (state corruption).
        ValueError: gate_task_id not found in state.tasks (state corruption).
        ValueError: approval_status is not "approved" or "rejected".
    """
    # 1. Load state.
    state = _load_state(workflow_id)

    # 2. Validate resumable condition.
    if state.status != "paused" or not state.awaiting_human_input:
        raise WorkflowNotPausedError(
            f"Cannot resume workflow '{workflow_id}': "
            f"status={state.status!r}, "
            f"awaiting_human_input={state.awaiting_human_input}. "
            "Workflow must be in 'paused' status with awaiting_human_input=True."
        )

    # 3. Validate approval decision value.
    if approval_status not in {"approved", "rejected"}:
        raise InvalidApprovalStatusError(
            f"Invalid approval_status {approval_status!r}. "
            "Must be 'approved' or 'rejected'."
        )

    # 4. Capture gate task identity before any mutation.
    gate_task_id = state.current_task_id  # e.g. "t6"

    if not gate_task_id:
        raise ValueError(
            f"Cannot resume workflow '{workflow_id}': state.current_task_id is "
            "empty. The workflow is paused but has no recorded gate task. "
            "State is corrupt."
        )

    # 5. Locate the gate Task object (needed for _log; corruption guard).
    gate_task: Task | None = next(
        (t for t in state.tasks if t.task_id == gate_task_id),
        None,
    )
    if gate_task is None:
        raise ValueError(
            f"Gate task '{gate_task_id}' not found in state.tasks for "
            f"workflow '{workflow_id}'. State is corrupt."
        )

    # 6. Apply decision atomically — all mutations before any persist call.
    state.awaiting_human_input = False
    state.approval_status = approval_status
    state.human_feedback = human_feedback

    state.human_input_data = (
        human_input_data or {}
    )

    # Store gate output for consistency with the task-output pattern.
    # state.approval_status is the authoritative field (ref: §6.5).
    if gate_task_id in state.outputs:
        raise ValueError(
            f"Gate task '{gate_task_id}' already has output in "
            f"state.outputs for workflow '{workflow_id}'. "
            "State is corrupt."
        )

    state.outputs[gate_task_id] = {
        "approval_status": approval_status,
        "human_feedback": human_feedback,
        "human_input_data": (
            human_input_data or {}
        ),
    }

    # ── 7a. Approved ──────────────────────────────────────────────────
    if approval_status == "approved":
        state.completed_tasks.append(gate_task_id)
        _log(state, gate_task, "completed")
        state.status = "running"
        _save_state(state)  # Checkpoint ⑤ — capture approval before re-entering loop.
        logger.info(
            "[%s] Workflow RESUMED (approved) — gate=%s feedback=%r",
            workflow_id,
            gate_task_id,
            human_feedback,
        )
        return _execute_loop(state)

    # ── 7b. Rejected ──────────────────────────────────────────────────
    else:
        state.completed_tasks.append(gate_task_id)
        feedback_text = human_feedback or "(no comment provided)"
        _log(state, gate_task, "failed", error=f"Rejected: {feedback_text}")
        state.status = "failed"
        state.error_message = f"Manager rejected offer: {feedback_text}"
        state.current_task_id = ""
        state.current_agent = ""
        _save_state(state)  # Checkpoint ⑥ — terminal failed state.
        logger.info(
            "[%s] Workflow TERMINATED (rejected) — gate=%s feedback=%r",
            workflow_id,
            gate_task_id,
            human_feedback,
        )
        return state