import uuid

from backend.models import (
    PlannerInput,
    PlannerOutput,
    Task,
    HireEmployeeParams,
    OnboardEmployeeParams,
    SalesOutreachParams,
    PerformanceReportParams,
    PerformanceReviewParams,
    MarketResearchParams,
)
from backend.planner.data_loader import (
    enrich_hire_params,
    enrich_onboard_params,
    enrich_sales_params,
    enrich_review_params,
)
from backend.planner.workflow_definitions import WORKFLOWS


# ─────────────────────────────────────────
# ENRICHED PARAMS TYPE ALIAS
#
# Covers all supported (post-enrichment) param
# models. Used as the planner's output type for
# params, giving callers a precise contract
# instead of a generic `object`.
# ─────────────────────────────────────────

EnrichedParams = (
    HireEmployeeParams
    | OnboardEmployeeParams
    | SalesOutreachParams
    | PerformanceReportParams
    | PerformanceReviewParams
    | MarketResearchParams
)


# ─────────────────────────────────────────
# ENRICHMENT ROUTER
#
# Maps objective_id -> enrichment function.
# Objectives not present here require no
# enrichment (params are fully manager-supplied).
# ─────────────────────────────────────────

ENRICHMENT_MAP = {
    "hire_employee":      enrich_hire_params,
    "onboard_employee":   enrich_onboard_params,
    "sales_outreach":     enrich_sales_params,
    "performance_review": enrich_review_params,
}


def _enrich_params(objective_id: str, params: EnrichedParams) -> EnrichedParams:
    """
    Enrich params using mock-data-backed enrichment functions.

    performance_report and market_research require no enrichment
    and are returned unchanged.
    """
    enrich_fn = ENRICHMENT_MAP.get(objective_id)

    if enrich_fn is None:
        return params

    return enrich_fn(params)


# ─────────────────────────────────────────
# WORKFLOW RETRIEVAL
#
# Returns a defensive deep copy of the predefined
# task list for the given objective_id, so that
# downstream mutation of tasks (e.g. by the
# orchestrator or LangGraph state) can never
# affect the shared WORKFLOWS definition.
# ─────────────────────────────────────────

def _get_workflow_tasks(objective_id: str) -> list[Task]:
    workflow = WORKFLOWS.get(objective_id)

    if workflow is None:
        raise ValueError(
            f"No workflow defined for objective_id: '{objective_id}'"
        )

    return [task.model_copy(deep=True) for task in workflow]


# ─────────────────────────────────────────
# PLANNER AGENT — MAIN ENTRY POINT
# ─────────────────────────────────────────

def run_planner(
    planner_input: PlannerInput,
) -> tuple[PlannerOutput, EnrichedParams]:
    """
    Main Planner Agent function.

    The Planner is non-AI. Objectives, workflows, and tasks are
    all predefined. The Planner's responsibilities are limited to:

      1. Validate objective_id.
      2. Enrich params via data_loader.
      3. Retrieve the predefined task list from WORKFLOWS.
      4. Generate a unique workflow execution ID.
      5. Build and return PlannerOutput, alongside the
         enriched params (for the orchestrator to attach
         to AgentState).

    The Planner does NOT call LLMs, generate tasks dynamically,
    execute tasks, perform routing, create AgentState, implement
    human approval logic, use LangGraph, or access any database.

    Args:
        planner_input: PlannerInput containing objective_id and params.

    Returns:
        (PlannerOutput, enriched_params)

    Raises:
        ValueError: if objective_id has no corresponding workflow.
    """
    objective_id = planner_input.objective_id

    # Step 1: Validate objective_id and retrieve predefined tasks.
    # Done first so unknown objectives fail fast, before any
    # enrichment side effects (mock data lookups) occur.
    tasks = _get_workflow_tasks(objective_id)

    # Step 2: Enrich params using mock data sources.
    enriched_params = _enrich_params(objective_id, planner_input.params)

    # Step 3: Generate a unique workflow execution ID.
    workflow_id = f"wf_{uuid.uuid4()}"

    # Step 4: Build PlannerOutput.
    output = PlannerOutput(
        workflow_id=workflow_id,
        objective_id=objective_id,
        tasks=tasks,
    )

    return output, enriched_params