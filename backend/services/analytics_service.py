"""
analytics_service.py
====================

Aggregates workflow execution data from MongoDB and prepares
dashboard analytics payloads for the frontend and ReportingAgent.

Layering
--------
API Route
    ↓
AnalyticsService
    ↓
WorkflowRepository
    ↓
MongoDB
"""

from collections import Counter

from backend.database.workflow_repository import (
    WorkflowRepository,
)


_repository = WorkflowRepository()


def generate_analytics_payload() -> dict:
    """
    Generate analytics payload from persisted workflows.

    Returns
    -------
    {
        "metrics": {...},
        "charts": [...],
        "reporting_input": {...}
    }
    """

    workflows = _repository.list_workflow_states()

    # ----------------------------------------------------------
    # Empty database case
    # ----------------------------------------------------------

    if not workflows:

        metrics = {
            "total_workflows": 0,
            "success_rate": 0.0,
            "completed": 0,
            "failed": 0,
            "paused": 0,
            "running": 0,
            "approved": 0,
            "rejected": 0,
        }

        return {
            "metrics": metrics,
            "charts": [],
            "objective_distribution": {},
            "reporting_input" : {
                "workflow_statistics": metrics,
                "workflow_distribution": {},
                "agent_usage": {}
            }
        }

    # ----------------------------------------------------------
    # Status counts
    # ----------------------------------------------------------

    status_counts = Counter(
        workflow.status
        for workflow in workflows
    )

    approval_counts = Counter(
        workflow.approval_status
        for workflow in workflows
    )

    objective_counts = Counter(
        workflow.objective_id
        for workflow in workflows
    )

    # ----------------------------------------------------------
    # KPI cards
    # ----------------------------------------------------------

    total_workflows = len(workflows)

    completed = status_counts.get(
        "completed",
        0,
    )

    terminal_workflows = (
    completed
    + status_counts.get("failed", 0)
    )

    if terminal_workflows == 0:
        success_rate = 0.0
    else:
        success_rate = round(
            (completed / terminal_workflows) * 100,
            1,
        )

    metrics = {
        "total_workflows": total_workflows,

        "success_rate": success_rate,

        "completed": completed,

        "failed": status_counts.get(
            "failed",
            0,
        ),

        "paused": status_counts.get(
            "paused",
            0,
        ),

        "running": status_counts.get(
            "running",
            0,
        ),

        "approved": approval_counts.get(
            "approved",
            0,
        ),

        "rejected": approval_counts.get(
            "rejected",
            0,
        ),
    }

    # ----------------------------------------------------------
    # Chart data for frontend
    # ----------------------------------------------------------

    charts = []

    for index, workflow in enumerate(workflows):

        agents = sorted(
            {
                log.get("agent", "Unknown")
                for log in workflow.execution_log
                if log.get("agent") != "human"
            }
        )

        assigned_agent = ", ".join(agents)

        if not assigned_agent:
            assigned_agent = "Unknown"

        charts.append(
            {
                "id": index + 1,

                "workflow_name":
                    f"{workflow.objective_id.replace('_', ' ').title()} "
                    f"({workflow.workflow_id[-6:]})",

                "assigned_agent":
                    assigned_agent,

                "execution_status":
                    workflow.status,
            }
        )

    # ----------------------------------------------------------
    # Agent usage analytics
    # ----------------------------------------------------------

    agent_usage = Counter()

    for workflow in workflows:

        for log in workflow.execution_log:

            agent = log.get(
                "agent",
                "unknown",
            )

            agent_usage[agent] += 1

    # ----------------------------------------------------------
    # Reporting Agent input
    # ----------------------------------------------------------

    reporting_input = {
        "workflow_statistics": metrics,

        "workflow_distribution":
            dict(objective_counts),

        "agent_usage":
            dict(agent_usage),
    }

    return {
        "metrics": metrics,
        "charts": charts,

        "objective_distribution":
            dict(objective_counts),

        "reporting_input": reporting_input,
}