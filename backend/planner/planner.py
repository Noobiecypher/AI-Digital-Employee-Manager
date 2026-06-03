import uuid
from models import (
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
from data_loader import (
    enrich_hire_params,
    enrich_onboard_params,
    enrich_sales_params,
    enrich_review_params,
)


# ─────────────────────────────────────────
# TASK DEFINITIONS PER OBJECTIVE
# Each function returns a list of Task objects.
# depends_on uses task_id strings to express order.
# ─────────────────────────────────────────

def _tasks_hire_employee() -> list[Task]:
    return [
        Task(task_id="t1", agent="recruitment", action="draft_jd",             depends_on=[]),
        Task(task_id="t2", agent="recruitment", action="shortlist_candidates",  depends_on=["t1"]),
        Task(task_id="t3", agent="hr",          action="schedule_interview",    depends_on=["t2"]),
        Task(task_id="t4", agent="hr",          action="send_offer",            depends_on=["t3"]),
    ]


def _tasks_onboard_employee() -> list[Task]:
    return [
        Task(task_id="t1", agent="hr", action="onboard_employee", depends_on=[]),
    ]


def _tasks_sales_outreach() -> list[Task]:
    return [
        Task(task_id="t1", agent="research", action="gather_data",          depends_on=[]),
        Task(task_id="t2", agent="sales",    action="draft_outreach",        depends_on=["t1"]),
        Task(task_id="t3", agent="sales",    action="generate_call_script",  depends_on=["t2"]),
        Task(task_id="t4", agent="sales",    action="campaign_summary",      depends_on=["t3"]),
    ]


def _tasks_performance_report() -> list[Task]:
    return [
        Task(task_id="t1", agent="hr",        action="compile_hr_data",       depends_on=[]),
        Task(task_id="t2", agent="sales",     action="compile_sales_data",    depends_on=[]),
        Task(task_id="t3", agent="reporting", action="generate_report",       depends_on=["t1", "t2"]),
    ]


def _tasks_performance_review() -> list[Task]:
    return [
        Task(task_id="t1", agent="hr", action="performance_review", depends_on=[]),
    ]


def _tasks_market_research() -> list[Task]:
    return [
        Task(task_id="t1", agent="research", action="gather_data",      depends_on=[]),
        Task(task_id="t2", agent="research", action="synthesize",        depends_on=["t1"]),
        Task(task_id="t3", agent="research", action="structured_report", depends_on=["t2"]),
    ]


# ─────────────────────────────────────────
# OBJECTIVE → TASK MAP
# ─────────────────────────────────────────

TASK_MAP = {
    "hire_employee":      _tasks_hire_employee,
    "onboard_employee":   _tasks_onboard_employee,
    "sales_outreach":     _tasks_sales_outreach,
    "performance_report": _tasks_performance_report,
    "performance_review": _tasks_performance_review,
    "market_research":    _tasks_market_research,
}


# ─────────────────────────────────────────
# ENRICHMENT ROUTER
# Enriches params for objectives that need
# data fetched from mock JSON files.
# Objectives 4 and 6 need no enrichment
# since all params are manager-inputted.
# ─────────────────────────────────────────

def _enrich_params(objective_id: str, params):
    if objective_id == "hire_employee":
        return enrich_hire_params(params)

    elif objective_id == "onboard_employee":
        return enrich_onboard_params(params)

    elif objective_id == "sales_outreach":
        return enrich_sales_params(params)

    elif objective_id == "performance_review":
        return enrich_review_params(params)

    # performance_report and market_research need no enrichment
    return params


# ─────────────────────────────────────────
# PLANNER AGENT — MAIN ENTRY POINT
# ─────────────────────────────────────────

def run_planner(planner_input: PlannerInput) -> tuple[PlannerOutput, object]:
    """
    Main Planner Agent function.

    Steps:
      1. Enrich params by fetching missing fields from mock data files.
      2. Look up the pre-defined task list for the given objective.
      3. Return a PlannerOutput (workflow_id, objective_id, tasks)
         and the enriched params separately so Person 1's orchestrator
         can attach them to AgentState.

    Args:
        planner_input: PlannerInput containing objective_id and params.

    Returns:
        (PlannerOutput, enriched_params)
    """
    objective_id = planner_input.objective_id

    # Step 1: Enrich params
    enriched_params = _enrich_params(objective_id, planner_input.params)

    # Step 2: Get pre-defined task list
    task_fn = TASK_MAP.get(objective_id)
    if not task_fn:
        raise ValueError(f"Unknown objective_id: '{objective_id}'")
    tasks = task_fn()

    # Step 3: Build output
    output = PlannerOutput(
        workflow_id=f"wf_{uuid.uuid4().hex[:8]}",
        objective_id=objective_id,
        tasks=tasks,
    )

    return output, enriched_params
