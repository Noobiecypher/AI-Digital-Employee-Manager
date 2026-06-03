import os
import sys
import json
from datetime import date, timedelta
import anthropic
from pydantic import BaseModel

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from models import AgentState, HireEmployeeParams
from data_loader import _load


# ─────────────────────────────────────────
# OUTPUT SCHEMAS
# ─────────────────────────────────────────

class DraftJDOutput(BaseModel):
    job_description: str
    required_skills: list[str]
    nice_to_have_skills: list[str]
    experience_years: int
    job_type: str
    location: str


class CandidateResult(BaseModel):
    name: str
    matched_skills: list[str]
    unmatched_skills: list[str]
    match_score: float


class ShortlistOutput(BaseModel):
    shortlisted: list[CandidateResult]
    rejected: list[CandidateResult]
    shortlist_threshold_used: float


class InterviewSlot(BaseModel):
    candidate: str
    round: int
    suggested_date: str             # YYYY-MM-DD
    duration_mins: int


class ScheduleInterviewOutput(BaseModel):
    interview_plan: list[InterviewSlot]


class RecruitmentAgentOutput(BaseModel):
    task_id: str
    action: str
    status: str                     # "completed" | "failed" | "needs_approval"
    result: DraftJDOutput | ShortlistOutput | ScheduleInterviewOutput


# ─────────────────────────────────────────
# CLAUDE CLIENT
# Only used by draft_jd
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
# ACTION 1 — DRAFT JD
# Uses Claude — generates written JD content
# ─────────────────────────────────────────

def draft_jd(state: AgentState) -> AgentState:
    """
    Reads:  state.params → role, department, experience_years,
                           skills_required, job_type, location
    Writes: state.outputs[task_id] → RecruitmentAgentOutput(DraftJDOutput)
            state.completed_tasks
    """
    task   = _get_current_task(state)
    params = state.params

    if not isinstance(params, HireEmployeeParams):
        raise ValueError("draft_jd requires HireEmployeeParams")

    system_prompt = """
You are a professional HR recruitment specialist.
Your job is to write clear, attractive job descriptions for open positions.
You must respond ONLY with a valid JSON object — no explanation, no markdown, no preamble.
The JSON must exactly match this structure:
{
  "job_description": "<full JD as a string>",
  "required_skills": ["skill1", "skill2"],
  "nice_to_have_skills": ["skill1", "skill2"],
  "experience_years": <integer>,
  "job_type": "<full_time|part_time|contract>",
  "location": "<city or Remote>"
}
"""

    user_prompt = f"""
Write a job description for the following position:

Role: {params.role}
Department: {params.department}
Experience Required: {params.experience_years} years
Required Skills: {', '.join(params.skills_required)}
Job Type: {params.job_type}
Location: {params.location}

Generate 3-5 nice-to-have skills that complement the required skills.
Keep the job description professional, concise, and appealing to candidates.
"""

    raw    = _call_claude(system_prompt, user_prompt)
    parsed = _parse_json(raw)
    result = DraftJDOutput(**parsed)

    output = RecruitmentAgentOutput(
        task_id=task.task_id,
        action="draft_jd",
        status="completed",
        result=result,
    )

    state.outputs[task.task_id] = output.model_dump()
    state.completed_tasks.append(task.task_id)

    return state


# ─────────────────────────────────────────
# ACTION 2 — SHORTLIST CANDIDATES
# Pure Python — no Claude needed
# ─────────────────────────────────────────

SHORTLIST_THRESHOLD = 0.60


def shortlist_candidates(state: AgentState) -> AgentState:
    """
    Reads:  state.params → role, skills_required
            state.outputs[t1] → required_skills from draft_jd
    Writes: state.outputs[task_id] → RecruitmentAgentOutput(ShortlistOutput)
            state.completed_tasks
            state.status → "paused" (always needs manager approval)

    Logic:
      - Loads candidates from candidates.json filtered by role
      - Computes match_score = matched_skills / required_skills
      - Candidates with score >= SHORTLIST_THRESHOLD → shortlisted
      - Rest → rejected
    """
    task   = _get_current_task(state)
    params = state.params

    if not isinstance(params, HireEmployeeParams):
        raise ValueError("shortlist_candidates requires HireEmployeeParams")

    # Read required_skills from draft_jd output if available, else fall back to params
    prev_task_id    = task.depends_on[0]
    prev_output     = state.outputs.get(prev_task_id, {})
    required_skills = prev_output.get("result", {}).get("required_skills", params.skills_required)

    # Load and filter candidates by role
    all_candidates  = _load("candidates.json")
    role_candidates = [
        c for c in all_candidates
        if c["role_applied"].lower() == params.role.lower()
    ]

    if not role_candidates:
        output = RecruitmentAgentOutput(
            task_id=task.task_id,
            action="shortlist_candidates",
            status="failed",
            result=ShortlistOutput(
                shortlisted=[],
                rejected=[],
                shortlist_threshold_used=SHORTLIST_THRESHOLD,
            ),
        )
        state.outputs[task.task_id] = output.model_dump()
        state.completed_tasks.append(task.task_id)
        state.status = "failed"
        return state

    shortlisted = []
    rejected    = []

    for candidate in role_candidates:
        candidate_skills = [s.lower() for s in candidate["skills"]]
        matched   = [s for s in required_skills if s.lower() in candidate_skills]
        unmatched = [s for s in required_skills if s.lower() not in candidate_skills]
        score     = round(len(matched) / len(required_skills), 2) if required_skills else 0.0

        entry = CandidateResult(
            name=candidate["name"],
            matched_skills=matched,
            unmatched_skills=unmatched,
            match_score=score,
        )

        if score >= SHORTLIST_THRESHOLD:
            shortlisted.append(entry)
        else:
            rejected.append(entry)

    # Sort shortlisted by score descending
    shortlisted.sort(key=lambda c: c.match_score, reverse=True)

    result = ShortlistOutput(
        shortlisted=shortlisted,
        rejected=rejected,
        shortlist_threshold_used=SHORTLIST_THRESHOLD,
    )

    output = RecruitmentAgentOutput(
        task_id=task.task_id,
        action="shortlist_candidates",
        status="needs_approval",
        result=result,
    )

    state.outputs[task.task_id] = output.model_dump()
    state.completed_tasks.append(task.task_id)
    state.status = "paused"         # tells Person 1's graph to interrupt here

    return state


# ─────────────────────────────────────────
# ACTION 3 — SCHEDULE INTERVIEW
# Pure Python — no Claude needed
# ─────────────────────────────────────────

ROUND_CONFIG = [
    {"round": 1, "label": "Technical Screen",  "duration_mins": 45},
    {"round": 2, "label": "Culture Fit",        "duration_mins": 30},
]
MAX_INTERVIEWS_PER_DAY = 3


def _next_working_day(d: date) -> date:
    """Returns the next Monday-Friday date after d."""
    d += timedelta(days=1)
    while d.weekday() >= 5:          # 5 = Saturday, 6 = Sunday
        d += timedelta(days=1)
    return d


def schedule_interview(state: AgentState) -> AgentState:
    """
    Reads:  state.params → role
            state.outputs[t2] → shortlisted candidates from shortlist_candidates
    Writes: state.outputs[task_id] → RecruitmentAgentOutput(ScheduleInterviewOutput)
            state.completed_tasks

    Logic:
      - 2 rounds per candidate (technical + culture fit)
      - Spreads across working days (Mon-Fri)
      - Max MAX_INTERVIEWS_PER_DAY interviews per day
      - Starts one week from today
    """
    task   = _get_current_task(state)
    params = state.params

    if not isinstance(params, HireEmployeeParams):
        raise ValueError("schedule_interview requires HireEmployeeParams")

    # Read shortlisted candidates from previous task output
    prev_task_id = task.depends_on[0]
    prev_output  = state.outputs.get(prev_task_id, {})
    shortlisted  = prev_output.get("result", {}).get("shortlisted", [])

    if not shortlisted:
        output = RecruitmentAgentOutput(
            task_id=task.task_id,
            action="schedule_interview",
            status="failed",
            result=ScheduleInterviewOutput(interview_plan=[]),
        )
        state.outputs[task.task_id] = output.model_dump()
        state.completed_tasks.append(task.task_id)
        state.status = "failed"
        return state

    # Start scheduling one week from today
    current_day        = date.today() + timedelta(weeks=1)
    # Make sure we start on a working day
    while current_day.weekday() >= 5:
        current_day = _next_working_day(current_day)

    interviews_on_day  = 0
    interview_plan     = []

    for candidate in shortlisted:
        for round_cfg in ROUND_CONFIG:
            # Move to next working day if daily limit reached
            if interviews_on_day >= MAX_INTERVIEWS_PER_DAY:
                current_day       = _next_working_day(current_day)
                interviews_on_day = 0

            interview_plan.append(InterviewSlot(
                candidate=candidate["name"],
                round=round_cfg["round"],
                suggested_date=current_day.strftime("%Y-%m-%d"),
                duration_mins=round_cfg["duration_mins"],
            ))

            interviews_on_day += 1

    result = ScheduleInterviewOutput(interview_plan=interview_plan)

    output = RecruitmentAgentOutput(
        task_id=task.task_id,
        action="schedule_interview",
        status="completed",
        result=result,
    )

    state.outputs[task.task_id] = output.model_dump()
    state.completed_tasks.append(task.task_id)

    return state