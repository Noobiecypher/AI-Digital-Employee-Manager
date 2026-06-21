from __future__ import annotations

from backend.database.workflow_repository import WorkflowRepository
from typing import Any

from fastapi import (
    APIRouter,
    BackgroundTasks,
    HTTPException,
    Query,
)

from pydantic import ValidationError

# --- REPORTING AGENT ADDITIONS ---
import os
import json
from backend.tools.reporting_tools import calculate_workflow_metrics
from backend.agent_nodes.reporting_agent import ReportingAgent
# ---------------------------------


from backend.models import (
    PlannerInput,
    HireEmployeeParams,
    OnboardEmployeeParams,
    SalesOutreachParams,
    PerformanceReportParams,
    PerformanceReviewParams,
    MarketResearchParams,
)

from backend.execution.workflow_executor import (
    
    create_workflow,
    execute_workflow,
    load_state,
    resume_workflow,
    list_workflow_ids,
    WorkflowNotFoundError,
    WorkflowNotPausedError,
    InvalidApprovalStatusError,
)

from backend.api.schemas import (
    StartWorkflowRequest,
    ResumeWorkflowRequest,
    StartWorkflowResponse,
    ResumeWorkflowResponse,
    WorkflowResponse,
    WorkflowListItem,
    WorkflowListResponse,
)

router = APIRouter()

PARAMS_MODEL_MAP = {
    "hire_employee": HireEmployeeParams,
    "onboard_employee": OnboardEmployeeParams,
    "sales_outreach": SalesOutreachParams,
    "performance_report": PerformanceReportParams,
    "performance_review": PerformanceReviewParams,
    "market_research": MarketResearchParams,
}

_repository = WorkflowRepository()

# --- OLLAMA REPORTING AGENT INITIALIZATION ---
try:
    _reporting_agent = ReportingAgent()
except Exception as e:
    _reporting_agent = None
    print(f"Warning: ReportingAgent failed to initialize. Ollama engine might be stopped: {e}")
# ---------------------------------------------


def error_response(
    status_code: int,
    code: str,
    message: str,
    field: str | None = None,
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "error": {
                "code": code,
                "message": message,
                "field": field,
                "details": None,
            }
        },
    )


def build_planner_input(
    objective_id: str,
    raw_params: dict[str, Any],
) -> PlannerInput:

    model_class = PARAMS_MODEL_MAP.get(objective_id)

    if model_class is None:
        raise error_response(
            422,
            "INVALID_OBJECTIVE",
            (
                f"Invalid objective_id '{objective_id}'."
            ),
            "objective_id",
        )

    try:
        params = model_class(**raw_params)

    except ValidationError as e:
        first = e.errors()[0]

        field = ".".join(
            str(x)
            for x in first["loc"]
        )

        raise error_response(
            422,
            "INVALID_PARAMS",
            first["msg"],
            f"params.{field}",
        )

    return PlannerInput(
        objective_id=objective_id,
        params=params,
    )


def map_executor_error(exc: Exception):

    if isinstance(exc, WorkflowNotFoundError):
        return error_response(
            404,
            "WORKFLOW_NOT_FOUND",
            str(exc),
        )

    if isinstance(exc, WorkflowNotPausedError):
        return error_response(
            409,
            "WORKFLOW_NOT_PAUSED",
            str(exc),
        )

    if isinstance(exc, InvalidApprovalStatusError):
        return error_response(
            422,
            "INVALID_APPROVAL_STATUS",
            str(exc),
            "approval_status",
        )

    return error_response(
        500,
        "INTERNAL_SERVER_ERROR",
        str(exc),
    )


def build_workflow_response(state) -> WorkflowResponse:

    workflow_meta = _repository.get_timestamps(
        state.workflow_id
    )

    result = None

    if (
        state.status == "completed"
        and state.completed_tasks
    ):
        last_task = state.completed_tasks[-1]
        result = state.outputs.get(last_task)

    return WorkflowResponse(
        workflow_id=state.workflow_id,
        objective_id=state.objective_id,
        status=state.status,
        current_task_id=state.current_task_id,
        current_agent=state.current_agent,
        awaiting_human_input=state.awaiting_human_input,
        approval_status=state.approval_status,

        approval_context=(
            state.outputs.get("t5")
            if state.status == "paused"
            and state.awaiting_human_input
            else None
        ),
        human_feedback=state.human_feedback,
        error_message=state.error_message,
        result=result,
        created_at=workflow_meta.get(
            "created_at"
        ),
        updated_at=workflow_meta.get(
            "updated_at"
        ),
    )


@router.post(
    "/start",
    status_code=202,
    response_model=StartWorkflowResponse,
)
async def start_workflow_route(
    body: StartWorkflowRequest,
    background_tasks: BackgroundTasks,
):

    planner_input = build_planner_input(
        body.objective_id,
        body.params,
    )

    try:
        state = create_workflow(
            planner_input
    )

    except ValueError as e:
        raise error_response(
            422,
            "INVALID_WORKFLOW",
            str(e),
        )


    background_tasks.add_task(
        execute_workflow,
        state.workflow_id,
    )

    return StartWorkflowResponse(
        workflow_id=state.workflow_id,
        objective_id=state.objective_id,
        status="running",
        message=(
            f"Workflow started. "
            f"Poll GET /workflows/"
            f"{state.workflow_id} for status."
        ),
    )


@router.get(
    "/{workflow_id}",
    response_model=WorkflowResponse,
)
async def get_workflow_route(
    workflow_id: str,
):
    try:
        state = load_state(workflow_id)

    except ValueError as e:
        raise map_executor_error(e)


    return build_workflow_response(
        state
    )


@router.post(
    "/{workflow_id}/resume",
    status_code=202,
    response_model=ResumeWorkflowResponse,
)
async def resume_workflow_route(
    workflow_id: str,
    body: ResumeWorkflowRequest,
    background_tasks: BackgroundTasks,
):
    try:
        state = load_state(workflow_id)

    except ValueError as e:
        raise map_executor_error(e)

    if body.approval_status not in {
        "approved",
        "rejected",
    }:
        raise error_response(
            422,
            "INVALID_APPROVAL_STATUS",
            (
                f"Invalid approval_status "
                f"'{body.approval_status}'."
            ),
            "approval_status",
        )

    if (
        state.status != "paused"
    ):
        raise error_response(
            409,
            "WORKFLOW_NOT_PAUSED",
            (
                f"Workflow "
                f"'{workflow_id}' "
                f"is not paused."
            ),
        )

    if (
        not state.awaiting_human_input
    ):
        raise error_response(
            409,
            "WORKFLOW_NOT_AWAITING_INPUT",
            (
                f"Workflow "
                f"'{workflow_id}' "
                f"is not awaiting input."
            ),
        )


    if body.approval_status == "rejected":
        result = resume_workflow(
            workflow_id,
            body.approval_status,
            body.human_feedback,
        )

        return ResumeWorkflowResponse(
            workflow_id=workflow_id,
            objective_id=result.objective_id,
            approval_status="rejected",
            status="failed",
            message=(
                "Decision recorded. "
                "Poll GET /workflows/"
                f"{workflow_id} for final status."
            ),
        )

    background_tasks.add_task(
        resume_workflow,
        workflow_id,
        body.approval_status,
        body.human_feedback,
    )

    return ResumeWorkflowResponse(
        workflow_id=workflow_id,
        objective_id=state.objective_id,
        approval_status="approved",
        status="running",
        message=(
            "Decision recorded. "
            "Poll GET /workflows/"
            f"{workflow_id} for final status."
        ),
    )


@router.get(
    "",
    response_model=WorkflowListResponse,
)
async def list_workflows_route(
    status: str | None = Query(
        default=None
    ),
    objective_id: str | None = Query(
        default=None
    ),
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
):

    items = []


    for workflow_id in list_workflow_ids():

        state = load_state(
            workflow_id
        )

        if (
            status
            and state.status != status
        ):
            continue

        if (
            objective_id
            and state.objective_id
            != objective_id
        ):
            continue

        meta = _repository.get_timestamps(
            workflow_id
        )

        items.append(
            WorkflowListItem(
                workflow_id=workflow_id,
                objective_id=state.objective_id,
                status=state.status,
                awaiting_human_input=(
                    state.awaiting_human_input
                ),
                approval_status=(
                    state.approval_status
                ),
                created_at=meta.get(
                    "created_at"
                ),
                updated_at=meta.get(
                    "updated_at"
                ),
            )
        )

    total = len(items)

    paginated = items[
        offset : offset + limit
    ]

    return WorkflowListResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=paginated,
    )

# --- REPORTING AGENT ROUTE ---
@router.get(
    "/report/analytics",
    status_code=200,
)
async def get_latest_report():
    """
    Simulates fetching raw metrics from the Workflow Engine database,
    processing them through the Reporting Agent pipeline, and delivering them to the UI.
    """
    if _reporting_agent is None:
        raise HTTPException(
            status_code=500, 
            detail="Reporting Agent uninitialized. Ensure that Ollama is running locally on your computer with the 'qwen2.5:1.5b' model active."
        )
        
    try:
        # Adjusted path pointing directly to the group's unified mock_data directory
        json_path = os.path.join("backend", "mock_data", "reports.json")
        
        # 1. Read the mock data payload simulating live system states
        with open(json_path, "r") as file:
            raw_logs = json.load(file)
        
        # 2. Run numerical transformations for charts
        structured_kpis = calculate_workflow_metrics(raw_logs)
        
        # 3. Request qualitative summaries from the Reporting Agent
        ai_insights = _reporting_agent.generate_narrative_insights(raw_logs, structured_kpis)
        
        # 4. Construct unified interface payload
        return {
            "workflow_id": raw_logs.get("workflow_id", "unknown"),
            "success": True,
            "metrics": structured_kpis["ui_kpi_cards"],
            "charts": structured_kpis["ui_chart_series"],
            "insights": ai_insights
        }
        
    except FileNotFoundError:
        raise HTTPException(
            status_code=500, 
            detail="Configuration Error: 'backend/mock_data/reports.json' could not be resolved."
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Internal Server Pipeline Error: {str(e)}"
        )
# -----------------------------

