from pydantic import BaseModel, Field
from typing import Union


# ==========================================================
# INPUT PARAM MODELS
# ==========================================================

class HireEmployeeParams(BaseModel):
    role: str
    department: str
    job_type: str

    # Enriched from department/role data
    experience_years: int = 0
    skills_required: list[str] = []
    location: str = ""
    salary_range: str = ""


class OnboardEmployeeParams(BaseModel):
    employee_name: str

    # Enriched from employee data
    role: str = ""
    department: str = ""
    joining_date: str = ""
    manager_name: str = ""
    work_mode: str = ""


class SalesOutreachParams(BaseModel):
    target_segment: str
    outreach_channels: list[str]
    campaign_goal: str

    # Enriched from product data
    product_name: str = ""
    pain_points: list[str] = []


class PerformanceReportParams(BaseModel):
    report_period: str
    departments: list[str]
    metrics_to_include: list[str]
    report_type: str


class PerformanceReviewParams(BaseModel):
    employee_name: str
    review_period: str
    manager_comments: str

    # Enriched from employee data
    role: str = ""
    department: str = ""

    # Enriched from goals data
    goals_set: list[str] = []
    goals_achieved: list[str] = []

    # Enriched from department data
    rating_scale: int = 5


class MarketResearchParams(BaseModel):
    research_topic: str
    competitors: list[str]
    focus_areas: list[str]
    output_format: str

# ==========================================================
# SHARED WORKFLOW OUTPUT MODELS
# ==========================================================

class Candidate(BaseModel):
    name: str
    skills: list[str] = []
    experience_years: int = 0
    match_score: float = 0.0
    email: str = ""
    phone: str = ""



# ==========================================================
# HIRE EMPLOYEE OUTPUTS
# ==========================================================

class OfferDetails(BaseModel):
    candidate_name: str
    role: str
    department: str
    salary: int
    location: str
    job_type: str


class InterviewSchedule(BaseModel):
    candidate_name: str
    interviewer: str
    date: str
    time: str
    meet_link: str = ""
    event_id: str = ""


# ==========================================================
# ONBOARD EMPLOYEE OUTPUTS
# ==========================================================

class EmployeeDetails(BaseModel):
    employee_id: str
    name: str
    role: str
    department: str
    manager_name: str
    joining_date: str
    work_mode: str


class OnboardingPlan(BaseModel):
    duration_days: int
    milestones: list[str] = []


class WelcomePackage(BaseModel):
    documents: list[str] = []
    resources: list[str] = []


# ==========================================================
# SALES OUTREACH OUTPUTS
# ==========================================================

class MarketData(BaseModel):
    target_segment: str
    pain_points: list[str] = []
    market_trends: list[str] = []


class CompetitorAnalysis(BaseModel):
    competitors: list[str] = []
    strengths: list[str] = []
    weaknesses: list[str] = []


class OutreachStrategy(BaseModel):
    campaign_goal: str
    channels: list[str] = []
    key_messages: list[str] = []


# ==========================================================
# PERFORMANCE REPORT OUTPUTS
# ==========================================================

class HRMetrics(BaseModel):
    metrics: dict = Field(default_factory=dict)


class SalesMetrics(BaseModel):
    metrics: dict = Field(default_factory=dict)


class AggregatedMetrics(BaseModel):
    hr_metrics: dict = Field(default_factory=dict)
    sales_metrics: dict = Field(default_factory=dict)


class KPIDashboard(BaseModel):
    kpis: dict = Field(default_factory=dict)


# ==========================================================
# PERFORMANCE REVIEW OUTPUTS
# ==========================================================

class GoalData(BaseModel):
    goals_set: list[str] = []
    goals_achieved: list[str] = []


class PerformanceEvaluation(BaseModel):
    strengths: list[str] = []
    weaknesses: list[str] = []
    summary: str = ""


# ==========================================================
# MARKET RESEARCH OUTPUTS
# ==========================================================

class ResearchData(BaseModel):
    topic: str
    competitors: list[str] = []
    focus_areas: list[str] = []


class StructuredReport(BaseModel):
    findings: list[str] = []
    recommendations: list[str] = []
    summary: str = ""

# ==========================================================
# PLANNER INPUT
# ==========================================================

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


# ==========================================================
# TASK MODEL
# ==========================================================

class Task(BaseModel):
    task_id: str

    # recruitment | hr | sales | research | reporting | human
    agent: str

    # generate_job_description etc.
    action: str

    # Task IDs that must complete before this task can run
    depends_on: list[str]


# ==========================================================
# PLANNER OUTPUT
# ==========================================================

class PlannerOutput(BaseModel):
    workflow_id: str
    objective_id: str
    tasks: list[Task]


# ==========================================================
# SHARED WORKFLOW STATE
# Passed through all LangGraph nodes
# ==========================================================

class AgentState(BaseModel):

    workflow_id: str
    objective_id: str

    # Fully enriched parameters
    params: Union[
        HireEmployeeParams,
        OnboardEmployeeParams,
        SalesOutreachParams,
        PerformanceReportParams,
        PerformanceReviewParams,
        MarketResearchParams,
    ]

    # Complete workflow task list
    tasks: list[Task]

    # Current task being executed
    current_task_id: str = ""

    # Current agent executing
    current_agent: str = ""

    # Completed task IDs
    completed_tasks: list[str] = Field(default_factory=list)

    # Outputs produced by agents
    #
    # Example:
    # {
    #     "t1": {...},
    #     "t2": {...}
    # }
    outputs: dict[str, dict] = Field(default_factory=dict)

    # Execution trace for debugging/auditing
    #
    # Example:
    # [
    #     {
    #         "task_id": "t1",
    #         "agent": "recruitment",
    #         "status": "completed"
    #     }
    # ]
    execution_log: list[dict] = Field(default_factory=list)

    # running | paused | completed | failed
    status: str = "running"

    approval_status: str = "pending"
    # pending | approved | rejected

    awaiting_human_input: bool = False

    # Manager approval/rejection comments
    human_feedback: str | None = None

    # Failure reason if status == failed
    error_message: str | None = None