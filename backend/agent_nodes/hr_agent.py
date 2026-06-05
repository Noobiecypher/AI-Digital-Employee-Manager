import os
import sys
import json
from datetime import date, timedelta
import anthropic
from pydantic import BaseModel

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from models import (
    AgentState,
    HireEmployeeParams,
    OnboardEmployeeParams,
    PerformanceReportParams,
    PerformanceReviewParams,
)
from data_loader import _load, get_role_info


# ─────────────────────────────────────────
# OUTPUT SCHEMAS
# ─────────────────────────────────────────

class SendOfferOutput(BaseModel):
    candidate_name: str
    role: str
    offer_letter: str
    offered_salary_range: str
    joining_date_proposed: str          # YYYY-MM-DD


class OnboardEmployeeOutput(BaseModel):
    employee_name: str
    checklist: list[str]
    welcome_email: str
    buddy_assigned: str
    tools_to_provision: list[str]


class DepartmentHRData(BaseModel):
    department: str
    headcount: int
    attrition_count: int


class CompileHRDataOutput(BaseModel):
    report_period: str
    departments_data: list[DepartmentHRData]
    total_headcount: int
    total_attrition: int


class PerformanceReviewOutput(BaseModel):
    employee_name: str
    role: str
    review_period: str
    review_summary: str
    goals_completion_rate: float
    rating_given: float
    strengths: list[str]
    improvements: list[str]
    recommended_action: str             # "promote" | "retain" | "pip"


class HRAgentOutput(BaseModel):
    task_id: str
    action: str
    status: str                         # "completed" | "failed" | "needs_approval"
    result: (
        SendOfferOutput       |
        OnboardEmployeeOutput |
        CompileHRDataOutput   |
        PerformanceReviewOutput
    )


# ─────────────────────────────────────────
# CLAUDE CLIENT
# Only used by performance_review
# ─────────────────────────────────────────

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
MODEL  = "claude-sonnet-4-20250514"


def _call_claude(system_prompt: str, user_prompt: str) -> str:
    response = client.messages.create(
        model=MODEL,
        max_tokens=1000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}]
    )
    return response.content[0].text


def _parse_json(raw: str) -> dict:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    return json.loads(cleaned.strip())


def _get_current_task(state: AgentState):
    for task in state.tasks:
        if task.task_id == state.current_task_id:
            return task
    raise ValueError(f"Task '{state.current_task_id}' not found in state.tasks")


# ─────────────────────────────────────────
# TEMPLATES
# ─────────────────────────────────────────

OFFER_LETTER_TEMPLATE = """
Dear {candidate_name},

We are delighted to offer you the position of {role} at WorkforceAI, 
within our {department} department based in {location}.

After careful consideration, we are pleased to extend this offer with 
the following details:

  Position   : {role}
  Department : {department}
  Location   : {location}
  Employment : {job_type}
  Salary     : {salary_range}
  Joining    : {joining_date}

Please confirm your acceptance of this offer within 5 working days by 
replying to this letter. We will follow up with your formal contract, 
onboarding details, and next steps shortly after.

We are excited to have you join our team and look forward to working 
with you.

Warm regards,
HR Team
WorkforceAI
""".strip()

WELCOME_EMAIL_TEMPLATE = """
Subject: Welcome to WorkforceAI, {employee_name}!

Dear {employee_name},

We are thrilled to welcome you to WorkforceAI as our new {role} 
in the {department} department!

Your journey begins on {joining_date}. Here are a few things to 
know before you start:

  Manager : {manager_name}
  Buddy   : {buddy}
  Mode    : {work_mode}

Your buddy {buddy} will be your go-to person for any questions 
during your first few weeks. Your manager {manager_name} will 
connect with you on Day 1 to walk you through your role and goals.

Please find your onboarding checklist attached. We recommend 
completing it in order during your first two weeks.

We are so glad to have you on board!

Warm regards,
HR Team
WorkforceAI
""".strip()

# Tools provisioned based on work mode
TOOLS_BY_MODE = {
    "remote":  ["Slack", "Zoom", "Jira", "GitHub", "Notion", "VPN Access"],
    "onsite":  ["Slack", "Jira", "GitHub", "Office Access Card", "Laptop Setup"],
    "hybrid":  ["Slack", "Zoom", "Jira", "GitHub", "Notion", "VPN Access", "Office Access Card"],
}


# ─────────────────────────────────────────
# ACTION 1 — SEND OFFER
# Pure Python + template — no Claude needed
# Triggered by: hire_employee objective
# ─────────────────────────────────────────

def send_offer(state: AgentState) -> AgentState:
    """
    Reads:  state.params → role, department, location, job_type
            state.outputs[t2] → shortlisted candidates (recruitment agent)
            departments.json  → salary_range for the role
    Writes: state.outputs[task_id] → HRAgentOutput(SendOfferOutput)
            state.completed_tasks
            state.status → "paused" (needs manager approval before sending)
    """
    task   = _get_current_task(state)
    params = state.params

    if not isinstance(params, HireEmployeeParams):
        raise ValueError("send_offer requires HireEmployeeParams")

    # Read top candidate from shortlist output (t2)
    shortlist_task_id = task.depends_on[0]
    shortlist_output  = state.outputs.get(shortlist_task_id, {})
    shortlisted       = shortlist_output.get("result", {}).get("shortlisted", [])

    if not shortlisted:
        output = HRAgentOutput(
            task_id=task.task_id,
            action="send_offer",
            status="failed",
            result=SendOfferOutput(
                candidate_name="N/A",
                role=params.role,
                offer_letter="No candidates available for offer.",
                offered_salary_range="N/A",
                joining_date_proposed="N/A",
            ),
        )
        state.outputs[task.task_id] = output.model_dump()
        state.completed_tasks.append(task.task_id)
        state.status = "failed"
        return state

    # Top candidate = highest match score (already sorted by recruitment agent)
    top_candidate  = shortlisted[0]["name"]

    # Fetch salary range from departments.json
    role_info      = get_role_info(params.department, params.role)
    salary_range   = role_info["salary_range"]

    # Joining date = 30 days from today
    joining_date   = (date.today() + timedelta(days=30)).strftime("%Y-%m-%d")

    offer_letter   = OFFER_LETTER_TEMPLATE.format(
        candidate_name = top_candidate,
        role           = params.role,
        department     = params.department,
        location       = params.location,
        job_type       = params.job_type.replace("_", " ").title(),
        salary_range   = salary_range,
        joining_date   = joining_date,
    )

    result = SendOfferOutput(
        candidate_name        = top_candidate,
        role                  = params.role,
        offer_letter          = offer_letter,
        offered_salary_range  = salary_range,
        joining_date_proposed = joining_date,
    )

    output = HRAgentOutput(
        task_id=task.task_id,
        action="send_offer",
        status="needs_approval",
        result=result,
    )

    state.outputs[task.task_id] = output.model_dump()
    state.completed_tasks.append(task.task_id)
    state.status = "paused"

    return state


# ─────────────────────────────────────────
# ACTION 2 — ONBOARD EMPLOYEE
# Pure Python + templates — no Claude needed
# Triggered by: onboard_employee objective
# ─────────────────────────────────────────

def onboard_employee(state: AgentState) -> AgentState:
    """
    Reads:  state.params → employee_name, role, department,
                           joining_date, manager_name, work_mode
            departments.json → onboarding_checklist for the role
            employees.json   → buddy (first colleague in same department)
    Writes: state.outputs[task_id] → HRAgentOutput(OnboardEmployeeOutput)
            state.completed_tasks
    """
    task   = _get_current_task(state)
    params = state.params

    if not isinstance(params, OnboardEmployeeParams):
        raise ValueError("onboard_employee requires OnboardEmployeeParams")

    # Fetch role-specific onboarding checklist
    role_info = get_role_info(params.department, params.role)
    checklist = role_info["onboarding_checklist"]

    # Tools based on work mode
    tools = TOOLS_BY_MODE.get(params.work_mode, TOOLS_BY_MODE["hybrid"])

    # Assign buddy — first employee in same department (excluding new employee)
    all_employees = _load("employees.json")
    buddy = next(
        (e["employee_name"] for e in all_employees
         if e["department"] == params.department
         and e["employee_name"] != params.employee_name),
        "To be assigned"
    )

    welcome_email = WELCOME_EMAIL_TEMPLATE.format(
        employee_name = params.employee_name,
        role          = params.role,
        department    = params.department,
        joining_date  = params.joining_date,
        manager_name  = params.manager_name,
        buddy         = buddy,
        work_mode     = params.work_mode.title(),
    )

    result = OnboardEmployeeOutput(
        employee_name      = params.employee_name,
        checklist          = checklist,
        welcome_email      = welcome_email,
        buddy_assigned     = buddy,
        tools_to_provision = tools,
    )

    output = HRAgentOutput(
        task_id=task.task_id,
        action="onboard_employee",
        status="completed",
        result=result,
    )

    state.outputs[task.task_id] = output.model_dump()
    state.completed_tasks.append(task.task_id)

    return state


# ─────────────────────────────────────────
# ACTION 3 — COMPILE HR DATA
# Pure Python — no Claude needed
# Triggered by: performance_report objective
# ─────────────────────────────────────────

def compile_hr_data(state: AgentState) -> AgentState:
    """
    Reads:  state.params → departments, report_period
            employees.json → headcount and attrition per department
    Writes: state.outputs[task_id] → HRAgentOutput(CompileHRDataOutput)
            state.completed_tasks
    """
    task   = _get_current_task(state)
    params = state.params

    if not isinstance(params, PerformanceReportParams):
        raise ValueError("compile_hr_data requires PerformanceReportParams")

    all_employees = _load("employees.json")
    one_year_ago  = date.today() - timedelta(days=365)

    departments_data = []
    total_headcount  = 0
    total_attrition  = 0

    for dept_name in params.departments:
        dept_employees = [
            e for e in all_employees
            if e["department"].lower() == dept_name.lower()
        ]
        headcount = len(dept_employees)
        attrition = sum(
            1 for e in dept_employees
            if date.fromisoformat(e["joining_date"]) < one_year_ago
        )

        departments_data.append(DepartmentHRData(
            department=dept_name,
            headcount=headcount,
            attrition_count=attrition,
        ))

        total_headcount += headcount
        total_attrition += attrition

    result = CompileHRDataOutput(
        report_period    = params.report_period,
        departments_data = departments_data,
        total_headcount  = total_headcount,
        total_attrition  = total_attrition,
    )

    output = HRAgentOutput(
        task_id=task.task_id,
        action="compile_hr_data",
        status="completed",
        result=result,
    )

    state.outputs[task.task_id] = output.model_dump()
    state.completed_tasks.append(task.task_id)

    return state


# ─────────────────────────────────────────
# ACTION 4 — PERFORMANCE REVIEW
# Uses Claude — only action that needs it
# Triggered by: performance_review objective
# ─────────────────────────────────────────

def performance_review(state: AgentState) -> AgentState:
    """
    Reads:  state.params → employee_name, role, department,
                           goals_set, goals_achieved, manager_comments,
                           rating_scale, review_period
    Writes: state.outputs[task_id] → HRAgentOutput(PerformanceReviewOutput)
            state.completed_tasks
            state.status → "paused" (needs manager approval before sharing)
    """
    task   = _get_current_task(state)
    params = state.params

    if not isinstance(params, PerformanceReviewParams):
        raise ValueError("performance_review requires PerformanceReviewParams")

    # Compute in Python — never let Claude decide this
    goals_completion_rate = (
        round(len(params.goals_achieved) / len(params.goals_set), 2)
        if params.goals_set else 0.0
    )

    system_prompt = """
You are a senior HR manager writing an official employee performance review.
You must respond ONLY with a valid JSON object — no explanation, no markdown, no preamble.
The JSON must exactly match this structure:
{
  "review_summary": "<2-3 paragraph written review>",
  "rating_given": <float e.g. 4.2>,
  "strengths": ["strength1", "strength2", "strength3"],
  "improvements": ["area1", "area2"],
  "recommended_action": "<promote|retain|pip>"
}
Be professional, fair, and constructive.
recommended_action must be exactly one of: promote, retain, pip
pip means Performance Improvement Plan — only use if performance is clearly poor.
"""

    user_prompt = f"""
Write a performance review for:

Name            : {params.employee_name}
Role            : {params.role}
Department      : {params.department}
Review Period   : {params.review_period}
Rating Scale    : out of {params.rating_scale}

Goals Set       : {params.goals_set}
Goals Achieved  : {params.goals_achieved}
Completion Rate : {goals_completion_rate * 100:.0f}%

Manager Comments: {params.manager_comments}

Based on the above, generate:
- A 2-3 paragraph professional review summary
- 2-3 strengths
- 1-2 areas for improvement
- A fair numeric rating out of {params.rating_scale}
- recommended_action: promote, retain, or pip
"""

    raw    = _call_claude(system_prompt, user_prompt)
    parsed = _parse_json(raw)

    result = PerformanceReviewOutput(
        employee_name         = params.employee_name,
        role                  = params.role,
        review_period         = params.review_period,
        goals_completion_rate = goals_completion_rate,  # always from Python
        review_summary        = parsed["review_summary"],
        rating_given          = parsed["rating_given"],
        strengths             = parsed["strengths"],
        improvements          = parsed["improvements"],
        recommended_action    = parsed["recommended_action"],
    )

    output = HRAgentOutput(
        task_id=task.task_id,
        action="performance_review",
        status="needs_approval",
        result=result,
    )

    state.outputs[task.task_id] = output.model_dump()
    state.completed_tasks.append(task.task_id)
    state.status = "paused"

    return state