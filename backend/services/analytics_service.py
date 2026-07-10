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
from datetime import datetime, timezone, timedelta

from backend.database.workflow_repository import WorkflowRepository

_repository = WorkflowRepository()

# Only include workflows from the last 7 days in chart data
CHART_DAYS = 7


def generate_analytics_payload() -> dict:
    """
    Generate analytics payload from persisted workflows.

    Returns
    -------
    {
        "metrics": {...},
        "charts": [...],           # last 7 days only, with real dates
        "objective_distribution": {...},
        "reporting_input": {...}
    }
    """

    # Use the new method that returns (state, created_at) pairs
    rows = _repository.list_workflow_states_with_timestamps()

    # ----------------------------------------------------------
    # Empty database case
    # ----------------------------------------------------------

    if not rows:
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
            "reporting_input": {
                "workflow_statistics": metrics,
                "workflow_distribution": {},
                "agent_usage": {},
            },
        }

    # ----------------------------------------------------------
    # Status counts (all workflows)
    # ----------------------------------------------------------

    status_counts   = Counter(state.status          for state, _ in rows)
    approval_counts = Counter(state.approval_status for state, _ in rows)
    objective_counts = Counter(state.objective_id   for state, _ in rows)

    # ----------------------------------------------------------
    # KPI cards
    # ----------------------------------------------------------

    total_workflows = len(rows)
    completed       = status_counts.get("completed", 0)
    terminal        = completed + status_counts.get("failed", 0)
    success_rate    = round((completed / terminal) * 100, 1) if terminal > 0 else 0.0

    metrics = {
        "total_workflows": total_workflows,
        "success_rate":    success_rate,
        "completed":       completed,
        "failed":          status_counts.get("failed",  0),
        "paused":          status_counts.get("paused",  0),
        "running":         status_counts.get("running", 0),
        "approved":        approval_counts.get("approved", 0),
        "rejected":        approval_counts.get("rejected", 0),
    }

    # ----------------------------------------------------------
    # Chart data — last 7 days only, with real created_at dates
    # ----------------------------------------------------------

    now      = datetime.now(timezone.utc)
    cutoff   = now - timedelta(days=CHART_DAYS)

    charts = []
    for state, created_at in rows:

        # Filter to last 7 days
        if created_at is not None:
            # Make timezone-aware if naive (older documents)
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            if created_at < cutoff:
                continue

        agents = sorted({
            log.get("agent", "Unknown")
            for log in state.execution_log
            if log.get("agent") != "human"
        })
        assigned_agent = ", ".join(agents) if agents else "Unknown"

        # Format date as "Mon DD" e.g. "Jul 03"
        if created_at is not None:
            date_str = created_at.strftime("%b %d")
        else:
            date_str = now.strftime("%b %d")  # fallback to today

        charts.append({
            "workflow_name":  (
                f"{state.objective_id.replace('_', ' ').title()} "
                f"({state.workflow_id[-6:]})"
            ),
            "assigned_agent":    assigned_agent,
            "execution_status":  state.status,
            "created_at":        created_at.isoformat() if created_at else None,
            "date":              date_str,
        })

    # ----------------------------------------------------------
    # Agent usage analytics (all workflows)
    # ----------------------------------------------------------

    agent_usage: Counter = Counter()
    for state, _ in rows:
        for log in state.execution_log:
            agent = log.get("agent", "unknown")
            agent_usage[agent] += 1

    # ----------------------------------------------------------
    # Reporting Agent input
    # ----------------------------------------------------------

    reporting_input = {
        "workflow_statistics":  metrics,
        "workflow_distribution": dict(objective_counts),
        "agent_usage":           dict(agent_usage),
    }

    return {
        "metrics":                metrics,
        "charts":                 charts,
        "objective_distribution": dict(objective_counts),
        "reporting_input":        reporting_input,
    }