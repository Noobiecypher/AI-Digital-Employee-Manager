"""
recruitment_agent.py
--------------------
Recruitment Agent for the AI Digital Employee Platform.

Handles hire_employee workflow: t1 through t5.

    t1 - generate_job_description
    t2 - identify_required_skills
    t3 - shortlist_candidates
    t4 - schedule_interviews
    t5 - prepare_offer

Inherits BaseAgent. Workflow Executor calls agent.run(task, state).
Returns output dict per task_contracts.md. Never mutates AgentState directly.

Requirements:
    pip install langchain langchain-ollama
    Ollama running locally: ollama serve
"""

from datetime import datetime, timedelta

from base_agent import BaseAgent, AgentExecutionError
from models import (
    AgentState,
    Task,
    Candidate,
    OfferDetails,
    InterviewSchedule,
    HireEmployeeParams,
)
from data_loader import get_candidates, get_role_info
from core.llm import llm


class RecruitmentAgent(BaseAgent):

    def __init__(self) -> None:
        super().__init__("recruitment")

    # ----------------------------------------------------------
    # DISPATCH
    # ----------------------------------------------------------

    def execute(self, task: Task, state: AgentState) -> dict:

        handlers = {
            "generate_job_description": self._generate_job_description,
            "identify_required_skills": self._identify_required_skills,
            "shortlist_candidates":     self._shortlist_candidates,
            "schedule_interviews":      self._schedule_interviews,
            "prepare_offer":            self._prepare_offer,
        }

        handler = handlers.get(task.action)

        if not handler:
            raise NotImplementedError(
                f"RecruitmentAgent: unknown action '{task.action}'"
            )

        return handler(task, state)

    # ----------------------------------------------------------
    # t1 — generate_job_description
    # Reads: state.params (role, department, job_type, location)
    # Returns: { "job_description": str }
    # ----------------------------------------------------------

    def _generate_job_description(
        self, task: Task, state: AgentState
    ) -> dict:

        params: HireEmployeeParams = state.params

        prompt = f"""
You are a professional HR recruiter. Write a detailed job description.

Role       : {params.role}
Department : {params.department}
Job Type   : {params.job_type}
Location   : {params.location}

The job description must include:
1. Role overview (2-3 sentences)
2. Key responsibilities (5-7 bullet points)
3. Required qualifications
4. What we offer

Be specific, professional, and compelling. Write only the job description.
"""

        response = llm.invoke(prompt)

        return {"job_description": response.content.strip()}

    # ----------------------------------------------------------
    # t2 — identify_required_skills
    # Reads: outputs["t1"], state.params (skills_required, experience_years)
    # Returns: { "required_skills": list[str] }
    # ----------------------------------------------------------

    def _identify_required_skills(
        self, task: Task, state: AgentState
    ) -> dict:

        t1 = self.get_output(state, "t1")
        params: HireEmployeeParams = state.params

        prompt = f"""
You are a technical recruiter. Based on the job description below,
identify the most important required skills for this role.

Job Description:
{t1["job_description"]}

Additional context:
- Experience required : {params.experience_years} years
- Skills already known: {params.skills_required}

Return ONLY a Python-style list of skill strings, one per line, like:
- Python
- FastAPI
- PostgreSQL

No explanation. Just the skill list.
"""

        response = llm.invoke(prompt)
        content  = response.content.strip()

        # Parse bullet list from LLM output
        skills = [
            line.strip("•-* ").strip()
            for line in content.split("\n")
            if line.strip() and line.strip() not in ["", "\n"]
        ]

        # Merge with params.skills_required, deduplicate
        all_skills = list({s for s in skills + params.skills_required if s})

        return {"required_skills": all_skills}

    # ----------------------------------------------------------
    # t3 — shortlist_candidates
    # Reads: outputs["t2"], state.params (experience_years, role)
    # Returns: { "shortlisted_candidates": list[Candidate] }
    # ----------------------------------------------------------

    def _shortlist_candidates(
        self, task: Task, state: AgentState
    ) -> dict:

        t2     = self.get_output(state, "t2")
        params: HireEmployeeParams = state.params

        required_skills  = t2["required_skills"]
        experience_years = params.experience_years

        # Load candidates from mock data
        raw_candidates = get_candidates(params.role)

        shortlisted: list[Candidate] = []

        for raw in raw_candidates:

            # Experience gate — must meet minimum
            if raw.get("experience_years", 0) < experience_years:
                continue

            # Skill match score — % of required skills the candidate has
            candidate_skills = [s.lower() for s in raw.get("skills", [])]
            matched = sum(
                1 for skill in required_skills
                if skill.lower() in candidate_skills
            )
            match_score = round(
                matched / len(required_skills) if required_skills else 0.0,
                2
            )

            # Only shortlist candidates with >= 50% skill match
            if match_score >= 0.5:
                shortlisted.append(
                    Candidate(
                        name             = raw["name"],
                        skills           = raw.get("skills", []),
                        experience_years = raw.get("experience_years", 0),
                        match_score      = match_score,
                    )
                )

        # Sort by match_score descending
        shortlisted.sort(key=lambda c: c.match_score, reverse=True)

        return {
            "shortlisted_candidates": [c.model_dump() for c in shortlisted]
        }

    # ----------------------------------------------------------
    # t4 — schedule_interviews
    # Reads: outputs["t3"] (shortlisted_candidates)
    # Returns: { "interview_schedule": list[InterviewSchedule] }
    # ----------------------------------------------------------

    def _schedule_interviews(
        self, task: Task, state: AgentState
    ) -> dict:

        t3           = self.get_output(state, "t3")
        shortlisted  = t3["shortlisted_candidates"]
        params: HireEmployeeParams = state.params

        if not shortlisted:
            raise ValueError(
                "No shortlisted candidates available to schedule interviews."
            )

        schedule: list[InterviewSchedule] = []
        base_date = datetime.now() + timedelta(days=3)

        for i, candidate in enumerate(shortlisted):
            interview_date = base_date + timedelta(days=i)
            schedule.append(
                InterviewSchedule(
                    candidate_name = candidate["name"],
                    interviewer    = f"Hiring Manager — {params.department}",
                    date           = interview_date.strftime("%Y-%m-%d"),
                    time           = "10:00 AM",
                )
            )

        return {
            "interview_schedule": [s.model_dump() for s in schedule]
        }

    # ----------------------------------------------------------
    # t5 — prepare_offer
    # Reads: outputs["t3"] (shortlisted_candidates), state.params
    # Returns: { "offer_details": OfferDetails }
    # Note: selected candidate = highest match_score from t3
    # ----------------------------------------------------------

    def _prepare_offer(
        self, task: Task, state: AgentState
    ) -> dict:

        t3          = self.get_output(state, "t3")
        shortlisted = t3["shortlisted_candidates"]
        params: HireEmployeeParams = state.params

        if not shortlisted:
            raise ValueError(
                "No shortlisted candidates to prepare offer for."
            )

        # MVP rule: highest match_score = selected candidate
        selected = max(shortlisted, key=lambda c: c["match_score"])

        # Parse salary from salary_range string (take midpoint for MVP)
        salary = self._parse_salary_midpoint(params.salary_range)

        offer = OfferDetails(
            candidate_name = selected["name"],
            role           = params.role,
            department     = params.department,
            salary         = salary,
            location       = params.location,
            job_type       = params.job_type,
        )

        return {"offer_details": offer.model_dump()}

    # ----------------------------------------------------------
    # PRIVATE HELPERS
    # ----------------------------------------------------------

    def _parse_salary_midpoint(self, salary_range: str) -> int:
        """
        Extracts midpoint from salary range strings like '80000-120000'
        or '80,000 - 1,20,000'. Falls back to 0 if unparseable.
        """
        try:
            cleaned = salary_range.replace(",", "").replace(" ", "")
            if "-" in cleaned:
                low, high = cleaned.split("-")
                return (int(low) + int(high)) // 2
            return int(cleaned)
        except Exception:
            return 0