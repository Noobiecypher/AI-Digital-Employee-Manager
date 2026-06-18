"""
resume_parser.py
-----------------
Standalone module — no dependency on Person 1's work.

Extracts text from PDF/DOCX resumes and uses LLM to parse it into
structured candidate data.

Once Person 1 updates models.py with resume fields on Candidate,
this module's output plugs directly into shortlist_candidates().

Requirements:
    pip install pypdf python-docx
"""

import json
import re
from pathlib import Path

from pypdf import PdfReader
from docx import Document

from backend.agent_nodes.llm import llm


# ==========================================================
# TEXT EXTRACTION
# ==========================================================

def extract_text_from_resume(file_path: str) -> str:
    """
    Extracts raw text from a resume file.
    Supports .pdf and .docx. Raises ValueError for unsupported types.
    """

    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return _extract_pdf_text(file_path)
    elif suffix == ".docx":
        return _extract_docx_text(file_path)
    else:
        raise ValueError(
            f"Unsupported resume format '{suffix}'. Only .pdf and .docx are supported."
        )


def _extract_pdf_text(file_path: str) -> str:
    reader = PdfReader(file_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    return text.strip()


def _extract_docx_text(file_path: str) -> str:
    doc = Document(file_path)
    text = "\n".join(para.text for para in doc.paragraphs)
    return text.strip()


# ==========================================================
# STRUCTURED PARSING VIA LLM
# ==========================================================

def parse_resume_to_candidate_data(
    resume_text: str,
    role_applied: str = "",
) -> dict:
    """
    Uses LLM to convert raw resume text into structured candidate data.

    Returns a dict matching the shape needed for the Candidate model:
        {
            "name": str,
            "email": str,
            "phone": str,
            "skills": list[str],
            "experience_years": int,
            "education": str,
            "resume_text": str   # original extracted text, kept for audit
        }

    NOTE: Once Person 1 updates the Candidate model in models.py to
    include these fields, this dict can be passed directly into
    Candidate(**parsed_data).
    """

    if not resume_text.strip():
        raise ValueError("Resume text is empty — cannot parse.")

    prompt = f"""
You are a resume parsing assistant. Extract structured information from
the resume text below. The candidate applied for the role: {role_applied or "Not specified"}.

Resume Text:
{resume_text[:6000]}

Return ONLY valid JSON in this exact structure, no extra text, no markdown:

{{
    "name": "<full name>",
    "email": "<email address or empty string>",
    "phone": "<phone number or empty string>",
    "skills": ["<skill1>", "<skill2>"],
    "experience_years": <integer, total years of relevant experience>,
    "education": "<highest qualification, one line>"
}}
"""

    response = llm.invoke(prompt)
    content = response.content.strip()

    parsed = _safe_json_parse(content)

    parsed["resume_text"] = resume_text

    return parsed


def _safe_json_parse(content: str) -> dict:
    """
    LLMs sometimes wrap JSON in markdown fences or add stray text.
    This extracts the first valid JSON object found.
    """

    # Strip markdown code fences if present
    content = re.sub(r"^```(?:json)?", "", content.strip())
    content = re.sub(r"```$", "", content.strip())

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # Fallback: find the first { ... } block
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise ValueError(f"Could not parse LLM output as JSON: {content[:200]}")


# ==========================================================
# COMBINED ENTRY POINT
# ==========================================================

def process_resume(file_path: str, role_applied: str = "") -> dict:
    """
    One-call entry point: file path in, structured candidate dict out.

    Usage:
        candidate_data = process_resume("/path/to/resume.pdf", role_applied="Backend Engineer")
    """

    text = extract_text_from_resume(file_path)
    return parse_resume_to_candidate_data(text, role_applied=role_applied)

"""
calendar_scheduler.py
-----------------------
Standalone module — no dependency on Person 1's work.

Integrates with Google Calendar API to:
    1. Check interviewer's free/busy slots
    2. Book an interview as a calendar event
    3. Return event_id and Google Meet link

Once Person 1 adds meet_link/event_id fields to InterviewSchedule in
models.py, this module's output plugs directly into schedule_interviews().

Requirements:
    pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib

Setup:
    1. Create a Google Cloud project, enable Calendar API
    2. Create a Service Account, download credentials JSON
    3. Share the interviewer's calendar with the service account email
    4. Set GOOGLE_CALENDAR_CREDENTIALS_PATH env var to the JSON file path
"""

import os
from datetime import datetime, timedelta

from google.oauth2 import service_account
from googleapiclient.discovery import build


# ==========================================================
# CONFIG
# ==========================================================

CREDENTIALS_PATH = os.getenv(
    "GOOGLE_CALENDAR_CREDENTIALS_PATH",
    "credentials.json"
)
SCOPES = ["https://www.googleapis.com/auth/calendar"]

WORKING_HOURS_START = 10   # 10 AM
WORKING_HOURS_END   = 17   # 5 PM
SLOT_DURATION_MINUTES = 45


# ==========================================================
# AUTH
# ==========================================================

def _get_calendar_service():
    credentials = service_account.Credentials.from_service_account_file(
        CREDENTIALS_PATH, scopes=SCOPES
    )
    return build("calendar", "v3", credentials=credentials)


# ==========================================================
# FREE SLOT LOOKUP
# ==========================================================

def get_free_slots(
    calendar_id: str,
    days_ahead: int = 7,
    num_slots_needed: int = 1,
) -> list[dict]:
    """
    Finds free interview slots in the interviewer's calendar over the
    next `days_ahead` days, within working hours.

    Returns: [{"start": ISO datetime, "end": ISO datetime}, ...]
    """

    service = _get_calendar_service()

    now = datetime.utcnow()
    time_min = now.isoformat() + "Z"
    time_max = (now + timedelta(days=days_ahead)).isoformat() + "Z"

    freebusy_query = {
        "timeMin": time_min,
        "timeMax": time_max,
        "items": [{"id": calendar_id}],
    }

    result = service.freebusy().query(body=freebusy_query).execute()
    busy_periods = result["calendars"][calendar_id]["busy"]

    free_slots = []
    current_day = now.date()

    while len(free_slots) < num_slots_needed and current_day <= (now + timedelta(days=days_ahead)).date():

        for hour in range(WORKING_HOURS_START, WORKING_HOURS_END):

            slot_start = datetime.combine(
                current_day, datetime.min.time()
            ).replace(hour=hour)
            slot_end = slot_start + timedelta(minutes=SLOT_DURATION_MINUTES)

            if slot_start <= now:
                continue

            overlaps = any(
                slot_start < datetime.fromisoformat(b["end"].rstrip("Z"))
                and slot_end > datetime.fromisoformat(b["start"].rstrip("Z"))
                for b in busy_periods
            )

            if not overlaps:
                free_slots.append({
                    "start": slot_start.isoformat(),
                    "end":   slot_end.isoformat(),
                })

            if len(free_slots) >= num_slots_needed:
                break

        current_day += timedelta(days=1)

    return free_slots


# ==========================================================
# BOOK INTERVIEW
# ==========================================================

def book_interview(
    calendar_id: str,
    candidate_name: str,
    candidate_email: str,
    interviewer_email: str,
    start_time: str,
    end_time: str,
    role: str,
) -> dict:
    """
    Creates a calendar event with a Google Meet link, invites both parties.

    Returns: {"event_id": str, "meet_link": str, "start": str, "end": str}
    """

    service = _get_calendar_service()

    event_body = {
        "summary": f"Interview — {candidate_name} for {role}",
        "description": f"Interview for the {role} position.",
        "start": {"dateTime": start_time, "timeZone": "UTC"},
        "end":   {"dateTime": end_time, "timeZone": "UTC"},
        "attendees": [
            {"email": candidate_email},
            {"email": interviewer_email},
        ],
        "conferenceData": {
            "createRequest": {
                "requestId": f"interview-{datetime.utcnow().timestamp()}",
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },
    }

    created_event = service.events().insert(
        calendarId=calendar_id,
        body=event_body,
        conferenceDataVersion=1,
        sendUpdates="all",
    ).execute()

    meet_link = (
        created_event.get("conferenceData", {})
        .get("entryPoints", [{}])[0]
        .get("uri", "")
    )

    return {
        "event_id":  created_event.get("id", ""),
        "meet_link": meet_link,
        "start":     start_time,
        "end":       end_time,
    }


# ==========================================================
# COMBINED ENTRY POINT
# ==========================================================

def schedule_interview_for_candidate(
    calendar_id: str,
    interviewer_email: str,
    candidate_name: str,
    candidate_email: str,
    role: str,
) -> dict:
    """
    One-call entry point: finds the next free slot and books it.

    Falls back gracefully — if Calendar API is unavailable, raises
    an exception that the caller (recruitment_agent.py) can catch
    and fall back to hardcoded scheduling.
    """

    slots = get_free_slots(calendar_id, num_slots_needed=1)

    if not slots:
        raise ValueError(f"No free interview slots found for {interviewer_email}")

    slot = slots[0]

    booking = book_interview(
        calendar_id        = calendar_id,
        candidate_name      = candidate_name,
        candidate_email     = candidate_email,
        interviewer_email   = interviewer_email,
        start_time          = slot["start"],
        end_time            = slot["end"],
        role                = role,
    )

    return booking

"""
embed_script_generator.py
---------------------------
Standalone module — no dependency on Person 1's work.

Generates an embeddable <script> tag for a job posting that companies
can paste into any external website to render an application form.

NOTE: The script currently points to a placeholder endpoint
(JOB_FORM_BASE_URL). Once Person 1 builds the actual form-serving
endpoint, update that constant — nothing else changes.
"""

import os
import uuid


# ==========================================================
# CONFIG
# ==========================================================

# Placeholder — Person 1 will provide the real endpoint once the
# application form serving infrastructure is built.
JOB_FORM_BASE_URL = os.getenv(
    "JOB_FORM_BASE_URL",
    "https://careers.yourcompany.com/embed"
)


# ==========================================================
# SCRIPT GENERATION
# ==========================================================

def generate_job_id() -> str:
    """Generates a unique job ID for embedding."""
    return f"job_{uuid.uuid4().hex[:10]}"


def generate_embed_script(job_id: str, role: str) -> str:
    """
    Generates an embeddable script tag for a given job posting.

    Usage by the hiring company:
        Paste the returned string into their website's HTML.
        It will render an application form for this specific job.

    Returns: the full <script> tag as a string.
    """

    return (
        f'<script src="{JOB_FORM_BASE_URL}/widget.js" '
        f'data-job-id="{job_id}" '
        f'data-role="{role}" '
        f'async></script>'
    )


def generate_application_link(job_id: str) -> str:
    """
    Generates a direct shareable link to the application form,
    as an alternative to embedding (e.g. for social media posts).
    """
    return f"{JOB_FORM_BASE_URL}/apply/{job_id}"
