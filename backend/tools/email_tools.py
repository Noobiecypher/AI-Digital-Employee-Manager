"""
email_followup.py
------------------
Standalone module — no dependency on Person 1's work.

Sends candidate follow-up emails at each recruitment stage via SMTP.
Plug this into recruitment_agent.py once candidate email is available
(currently missing in mock candidates.json — added manually for testing,
will come from resume_parser.py output in production).

Requirements:
    Set these environment variables:
        SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM_NAME
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging; logger = logging.getLogger(__name__)
from backend.agent_nodes.llm import llm


# ==========================================================
# SMTP CONFIG
# ==========================================================

SMTP_HOST      = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT      = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER      = os.getenv("SMTP_USER", "")
SMTP_PASSWORD  = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "Recruitment Team")


# ==========================================================
# STAGE TEMPLATES
# ==========================================================

class FollowUpStage:
    APPLICATION_RECEIVED = "application_received"
    SHORTLISTED          = "shortlisted"
    REJECTED              = "rejected"
    INTERVIEW_SCHEDULED  = "interview_scheduled"
    OFFER_EXTENDED       = "offer_extended"


_STAGE_PROMPTS = {
    FollowUpStage.APPLICATION_RECEIVED: (
        "Write a brief, warm email confirming receipt of {candidate_name}'s "
        "application for the {role} position. Mention next steps will follow "
        "within a few business days."
    ),
    FollowUpStage.SHORTLISTED: (
        "Write a brief, encouraging email informing {candidate_name} that "
        "they have been shortlisted for the {role} position and that an "
        "interview will be scheduled shortly."
    ),
    FollowUpStage.REJECTED: (
        "Write a brief, respectful, and kind email informing {candidate_name} "
        "that they were not selected to move forward for the {role} position. "
        "Thank them for their time and encourage future applications."
    ),
    FollowUpStage.INTERVIEW_SCHEDULED: (
        "Write a brief email confirming an interview for {candidate_name} "
        "for the {role} position, scheduled on {interview_date} at {interview_time}. "
        "Mention the interview will be conducted via {mode}."
    ),
    FollowUpStage.OFFER_EXTENDED: (
        "Write a brief, congratulatory email informing {candidate_name} that "
        "they have been selected for the {role} position and that a formal "
        "offer letter is attached/will follow separately."
    ),
}

_STAGE_SUBJECTS = {
    FollowUpStage.APPLICATION_RECEIVED: "Application Received — {role}",
    FollowUpStage.SHORTLISTED:          "You've Been Shortlisted — {role}",
    FollowUpStage.REJECTED:              "Update on Your Application — {role}",
    FollowUpStage.INTERVIEW_SCHEDULED:  "Interview Scheduled — {role}",
    FollowUpStage.OFFER_EXTENDED:       "Congratulations! Offer for {role}",
}


# ==========================================================
# EMAIL GENERATION
# ==========================================================

def generate_followup_email(stage: str, **context) -> str:
    """
    Generates email body text for a given follow-up stage using LLM.

    context kwargs depend on stage, e.g.:
        candidate_name, role, interview_date, interview_time, mode
    """

    if stage not in _STAGE_PROMPTS:
        raise ValueError(f"Unknown follow-up stage: '{stage}'")

    instruction = _STAGE_PROMPTS[stage].format(**context)

    prompt = f"""
You are an HR recruiter writing a candidate email.

{instruction}

Keep it under 120 words. Professional and friendly tone.
Write only the email body. No subject line. No placeholders like [Name].
"""

    response = llm.invoke(prompt)
    return response.content.strip()


# ==========================================================
# EMAIL SENDING
# ==========================================================

def send_followup_email(
    to_email: str,
    stage: str,
    **context
) -> bool:
    """
    Generates and sends a follow-up email for the given stage.

    Returns True on success, False on failure (logs error, does not raise —
    a failed notification should not crash the recruitment workflow).
    """

    if not to_email:
        print(f"[email_followup] Skipped — no email address for stage '{stage}'")
        return False

    try:
        body = generate_followup_email(stage, **context)
        subject = _STAGE_SUBJECTS[stage].format(**context)

        msg = MIMEMultipart()
        msg["From"]    = f"{SMTP_FROM_NAME} <{SMTP_USER}>"
        msg["To"]      = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)

        return True

    except Exception as e:
        logger.error("Failed to send '%s' email to %s: %s", stage, to_email, e)
        return False


# ==========================================================
# BATCH HELPER
# ==========================================================

def notify_candidates(
    candidates: list[dict],
    stage: str,
    role: str,
) -> dict:
    """
    Sends the same stage notification to multiple candidates.

    candidates: list of dicts, each must have "name" and "email" keys.

    Returns: { "sent": int, "failed": int, "failed_emails": list[str] }
    """

    sent, failed, failed_emails = 0, 0, []

    for candidate in candidates:
        success = send_followup_email(
            to_email       = candidate.get("email", ""),
            stage          = stage,
            candidate_name = candidate.get("name", "Candidate"),
            role           = role,
        )
        if success:
            sent += 1
        else:
            failed += 1
            failed_emails.append(candidate.get("email", "unknown"))

    return {"sent": sent, "failed": failed, "failed_emails": failed_emails}
