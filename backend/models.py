from pydantic import BaseModel
from typing import Union


# ─────────────────────────────────────────
# INPUT PARAM MODELS (one per objective)
# ─────────────────────────────────────────

class HireEmployeeParams(BaseModel):
    # Manager inputs
    role: str
    department: str
    job_type: str                   # "full_time" | "part_time" | "contract"
    # Fetched from departments.json
    experience_years: int = 0
    skills_required: list[str] = []
    location: str = ""


class OnboardEmployeeParams(BaseModel):
    # Manager inputs
    employee_name: str
    # Fetched from employees.json
    role: str = ""
    department: str = ""
    joining_date: str = ""
    manager_name: str = ""
    work_mode: str = ""             # "remote" | "onsite" | "hybrid"


class SalesOutreachParams(BaseModel):
    # Manager inputs
    target_segment: str
    outreach_channels: list[str]    # e.g. ["email", "linkedin"]
    campaign_goal: str
    # Fetched from products.json
    product_name: str = ""
    pain_points: list[str] = []


class PerformanceReportParams(BaseModel):
    # All manager inputs
    report_period: str
    departments: list[str]
    metrics_to_include: list[str]
    report_type: str                # "executive_summary" | "detailed" | "kpi_dashboard"


class PerformanceReviewParams(BaseModel):
    # Manager inputs
    employee_name: str
    review_period: str
    manager_comments: str
    # Fetched from employees.json
    role: str = ""
    department: str = ""
    # Fetched from goals.json
    goals_set: list[str] = []
    goals_achieved: list[str] = []
    # Fetched from departments.json
    rating_scale: int = 5


class MarketResearchParams(BaseModel):
    # All manager inputs
    research_topic: str
    competitors: list[str]
    focus_areas: list[str]
    output_format: str              # "bullet_summary" | "detailed_report" | "comparison_table"


# ─────────────────────────────────────────
# TOP LEVEL PLANNER INPUT
# ─────────────────────────────────────────

class PlannerInput(BaseModel):
    objective_id: str
    params: Union[
        HireEmployeeParams,
        OnboardEmployeeParams,
        SalesOutreachParams,
        PerformanceReportParams,
        PerformanceReviewParams,
        MarketResearchParams,
    ]


# ─────────────────────────────────────────
# PLANNER OUTPUT MODELS
# ─────────────────────────────────────────

class Task(BaseModel):
    task_id: str
    agent: str                      # "hr" | "recruitment" | "sales" | "research" | "reporting"
    action: str
    depends_on: list[str]           # task_ids that must complete first, [] if no dependency


class PlannerOutput(BaseModel):
    workflow_id: str
    objective_id: str
    tasks: list[Task]


# ─────────────────────────────────────────
# AGENT STATE
# Shared state object passed through every
# node in Person 1's LangGraph graph.
# Every agent reads from and writes to this.
# ─────────────────────────────────────────

class AgentState(BaseModel):
    workflow_id: str
    objective_id: str

    # Full enriched params from Planner — agents read from this
    params: Union[
        HireEmployeeParams,
        OnboardEmployeeParams,
        SalesOutreachParams,
        PerformanceReportParams,
        PerformanceReviewParams,
        MarketResearchParams,
    ]

    # Full task list from Planner
    tasks: list[Task]

    # task_id of the task currently being executed
    current_task_id: str = ""

    # Completed task_ids
    completed_tasks: list[str] = []

    # Agent outputs keyed by task_id
    # e.g. { "t1": { ...DraftJDOutput... }, "t2": { ...ShortlistOutput... } }
    outputs: dict = {}

    # Overall workflow status
    status: str = "running"         # "running" | "paused" | "completed" | "failed"

    # Populated by Person 4's UI when manager approves/rejects
    human_feedback: str | None = None
