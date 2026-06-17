"""
recruitment_agent.py
--------------------
Recruitment Agent for the AI Digital Employee Platform.

Handles hire_employee workflow: t1 through t5.

    t1 - generate_job_description   (+ embed script generation)
    t2 - identify_required_skills
    t3 - shortlist_candidates       (+ resume parsing, follow-up emails)
    t4 - schedule_interviews        (+ Google Calendar integration)
    t5 - prepare_offer              (+ offer follow-up email)

Inherits BaseAgent. Workflow Executor calls agent.run(task, state).
Returns output dict per task_contracts.md. Never mutates AgentState directly.

============================================================
INTEGRATION STATUS — READ BEFORE EDITING
============================================================
The following features are built as standalone modules in
recruitment_modules/ and are functional independently, but their
FULL wiring into this agent depends on Person 1 delivering:

    1. Updated models.py — Candidate needs resume_text/email/phone fields,
       InterviewSchedule needs meet_link/event_id fields
    2. Applications stored in DB (replacing candidates.json)
    3. data_loader.get_applications(job_id) function
    4. Real embed script serving endpoint (JOB_FORM_BASE_URL)

Until then, this file runs in HYBRID MODE:
    - Resume parsing module is wired in but falls back to mock
      candidates.json if no resume files are provided.
    - Calendar scheduling is wired in but falls back to hardcoded
      date slots if Calendar API credentials are not configured.
    - Embed script uses a placeholder URL.
    - Follow-up emails send if SMTP env vars are configured, else
      they're skipped silently (logged, not raised).

Search for "TODO(person1)" to find every spot that needs their input.
============================================================

Requirements:
    pip install langchain langchain-ollama pypdf python-docx
    pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
    Ollama running locally: ollama serve
"""

import os
from datetime import datetime, timedelta

from base_agent import BaseAgent
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

# Standalone modules — functional now, fully wired once Person 1 delivers contracts
from tools.recruitment_tools import(
    process_resume, 
    generate_job_id, 
    generate_embed_script, 
    schedule_interview_for_candidate
)
from tools.email_tools import (
    send_followup_email, 
    notify_candidates, 
    FollowUpStage
)

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
    # Returns: { "job_description": str, "job_id": str, "embed_script": str }
    #
    # NOTE: embed_script and job_id are ADDITIONS beyond the current
    # task_contracts.md spec. TODO(person1): confirm this expanded
    # return shape is acceptable, or formalize it in task_contracts.md.
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
        job_description = response.content.strip()

        # Generate embed script for this job posting
        job_id = generate_job_id()
        embed_script = generate_embed_script(job_id, params.role)

        return {
            "job_description": job_description,
            "job_id":          job_id,
            "embed_script":    embed_script,
        }

    # ----------------------------------------------------------
    # t2 — identify_required_skills
    # Reads: outputs["t1"], state.params (skills_required, experience_years)
    # Returns: { "required_skills": list[str] }
    # Unchanged — no dependency on Person 1's pending work.
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

        skills = [
            line.strip("•-* ").strip()
            for line in content.split("\n")
            if line.strip()
        ]

        all_skills = list({s for s in skills + params.skills_required if s})

        return {"required_skills": all_skills}

    # ----------------------------------------------------------
    # t3 — shortlist_candidates
    # Reads: outputs["t2"], state.params (experience_years, role)
    # Returns: { "shortlisted_candidates": list[Candidate] }
    #
    # HYBRID MODE:
    #   - If resume_files is passed in state.params (not yet a real field —
    #     TODO(person1): add resume_files: list[str] to HireEmployeeParams,
    #     or better, an applications DB table), parses real resumes.
    #   - Otherwise falls back to candidates.json (current mock behavior).
    #
    # Sends "shortlisted" / "rejected" follow-up emails to candidates
    # that have an email address available (resume-parsed candidates only —
    # mock JSON candidates have no email field yet).
    # ----------------------------------------------------------

    def _shortlist_candidates(
        self, task: Task, state: AgentState
    ) -> dict:

        t2     = self.get_output(state, "t2")
        params: HireEmployeeParams = state.params

        required_skills  = t2["required_skills"]
        experience_years = params.experience_years

        # TODO(person1): replace this branch with get_applications(job_id)
        # once applications are stored in DB instead of mock JSON / local files.
        resume_files = getattr(params, "resume_files", None)

        if resume_files:
            raw_candidates = self._parse_resumes(resume_files, params.role)
        else:
            raw_candidates = get_candidates(params.role)

        shortlisted: list[dict] = []
        rejected_candidates: list[dict] = []

        for raw in raw_candidates:

            if raw.get("experience_years", 0) < experience_years:
                rejected_candidates.append(raw)
                continue

            candidate_skills = [s.lower() for s in raw.get("skills", [])]
            matched = sum(
                1 for skill in required_skills
                if skill.lower() in candidate_skills
            )
            match_score = round(
                matched / len(required_skills) if required_skills else 0.0,
                2
            )

            candidate = Candidate(
                name             = raw["name"],
                skills           = raw.get("skills", []),
                experience_years = raw.get("experience_years", 0),
                match_score      = match_score,
            )

            if match_score >= 0.5:
                shortlisted.append({**candidate.model_dump(), "email": raw.get("email", "")})
            else:
                rejected_candidates.append(raw)

        shortlisted.sort(key=lambda c: c["match_score"], reverse=True)

        # Follow-up emails — only sends if email present and SMTP configured.
        # Silently skips otherwise (see email_followup.py docstring).
        if shortlisted:
            notify_candidates(shortlisted, FollowUpStage.SHORTLISTED, role=params.role)
        if rejected_candidates:
            notify_candidates(rejected_candidates, FollowUpStage.REJECTED, role=params.role)

        # Strip email before returning — not part of the Candidate model yet.
        # TODO(person1): add email field to Candidate model so this isn't needed.
        clean_shortlisted = [
            {k: v for k, v in c.items() if k != "email"} for c in shortlisted
        ]

        return {"shortlisted_candidates": clean_shortlisted}

    def _parse_resumes(self, resume_files: list[str], role: str) -> list[dict]:
        """
        Parses a list of resume file paths into candidate dicts.
        Standalone — works today via resume_parser.py regardless of
        Person 1's progress.
        """
        candidates = []
        for file_path in resume_files:
            try:
                parsed = process_resume(file_path, role_applied=role)
                candidates.append(parsed)
            except Exception as e:
                print(f"[shortlist_candidates] Failed to parse {file_path}: {e}")
        return candidates

    # ----------------------------------------------------------
    # t4 — schedule_interviews
    # Reads: outputs["t3"] (shortlisted_candidates)
    # Returns: { "interview_schedule": list[InterviewSchedule] }
    #
    # HYBRID MODE:
    #   - Tries Google Calendar booking first (calendar_scheduler.py).
    #   - Falls back to hardcoded sequential date slots if Calendar API
    #     is not configured or fails (e.g. missing credentials.json).
    #   - meet_link/event_id are returned as extra dict keys but are
    #     NOT yet part of the InterviewSchedule model.
    #     TODO(person1): add meet_link: str = "" and event_id: str = ""
    #     to InterviewSchedule in models.py.
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

        # TODO(person1): interviewer_email and calendar_id should come from
        # departments.json / DB, not be hardcoded placeholders.
        interviewer_email = os.getenv("DEFAULT_INTERVIEWER_EMAIL", "")
        calendar_id        = os.getenv("DEFAULT_CALENDAR_ID", interviewer_email)

        schedule = []
        base_date = datetime.now() + timedelta(days=3)

        for i, candidate in enumerate(shortlisted):

            booking = None

            if calendar_id and interviewer_email:
                try:
                    booking = schedule_interview_for_candidate(
                        calendar_id        = calendar_id,
                        interviewer_email   = interviewer_email,
                        candidate_name      = candidate["name"],
                        candidate_email     = candidate.get("email", ""),
                        role                = params.role,
                    )
                except Exception as e:
                    print(f"[schedule_interviews] Calendar booking failed, "
                          f"falling back to manual slot: {e}")

            if booking:
                entry = InterviewSchedule(
                    candidate_name = candidate["name"],
                    interviewer    = interviewer_email,
                    date           = booking["start"][:10],
                    time           = booking["start"][11:16],
                ).model_dump()
                entry["meet_link"] = booking.get("meet_link", "")
                entry["event_id"]  = booking.get("event_id", "")
            else:
                interview_date = base_date + timedelta(days=i)
                entry = InterviewSchedule(
                    candidate_name = candidate["name"],
                    interviewer    = f"Hiring Manager — {params.department}",
                    date           = interview_date.strftime("%Y-%m-%d"),
                    time           = "10:00 AM",
                ).model_dump()
                entry["meet_link"] = ""
                entry["event_id"]  = ""

            schedule.append(entry)

            # Follow-up email — confirms interview slot to candidate
            send_followup_email(
                to_email         = candidate.get("email", ""),
                stage            = FollowUpStage.INTERVIEW_SCHEDULED,
                candidate_name   = candidate["name"],
                role             = params.role,
                interview_date   = entry["date"],
                interview_time   = entry["time"],
                mode             = "Video Call",
            )

        return {"interview_schedule": schedule}

    # ----------------------------------------------------------
    # t5 — prepare_offer
    # Reads: outputs["t3"] (shortlisted_candidates), state.params
    # Returns: { "offer_details": OfferDetails }
    # Unchanged logic — added offer follow-up email only.
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

        selected = max(shortlisted, key=lambda c: c["match_score"])
        salary = self._parse_salary_midpoint(params.salary_range)

        offer = OfferDetails(
            candidate_name = selected["name"],
            role           = params.role,
            department     = params.department,
            salary         = salary,
            location       = params.location,
            job_type       = params.job_type,
        )

        # Follow-up email — congratulates selected candidate.
        # TODO(person1): selected candidate's email isn't preserved through
        # to t3's output (stripped in shortlist_candidates). Once Candidate
        # model has an email field, remove that stripping step and this
        # will work automatically.
        send_followup_email(
            to_email       = selected.get("email", ""),
            stage          = FollowUpStage.OFFER_EXTENDED,
            candidate_name = selected["name"],
            role           = params.role,
        )

        return {"offer_details": offer.model_dump()}

    # ----------------------------------------------------------
    # PRIVATE HELPERS
    # ----------------------------------------------------------

    def _parse_salary_midpoint(self, salary_range: str) -> int:
        try:
            cleaned = salary_range.replace(",", "").replace(" ", "")
            if "-" in cleaned:
                low, high = cleaned.split("-")
                return (int(low) + int(high)) // 2
            return int(cleaned)
        except Exception:
            return 0