"""
backend/tools/outreach_tools.py
===============================
Outreach sending (Person 3) — SMTP.

IMPORTANT: this is a POST-APPROVAL action. The Sales Agent only *drafts* outreach;
nothing here should run until the approval gate has approved the draft. Wire
send_approved_outreach() into the approve handler (Person 4 frontend / executor),
not into the draft-generation agent — that keeps the "respect approval
boundaries" guarantee intact.

Safe by default: if SMTP isn't configured or OUTREACH_TEST_MODE is on, it returns
a dry-run plan instead of sending — so demos never accidentally email real people.
Standard library only (smtplib).

Env:
  SMTP_HOST, SMTP_PORT (default 587), SMTP_USER, SMTP_PASS, SMTP_FROM
  OUTREACH_TEST_MODE=1   force dry-run even if SMTP is configured
"""

from __future__ import annotations

import os
import smtplib
import ssl
from email.mime.text import MIMEText


def _split_subject(email_text: str, default_subject: str) -> tuple[str, str]:
    """Pull a 'Subject: ...' first line out of a drafted email, if present."""
    text = (email_text or "").strip()
    first, _, rest = text.partition("\n")
    low = first.lower()
    if low.startswith("subject:"):
        return first.split(":", 1)[1].strip() or default_subject, rest.strip()
    # handle "Email 1 — Subject: ..." style
    if "subject:" in low:
        subj = first[low.index("subject:") + 8:].strip()
        return (subj or default_subject), rest.strip()
    return default_subject, text


def send_outreach(to_addresses: list[str], subject: str, body: str, sender: str | None = None) -> dict:
    """Send one email via SMTP. Returns a status dict; never raises."""
    sender = sender or os.environ.get("SMTP_FROM") or os.environ.get("SMTP_USER") or "no-reply@example.com"
    host = os.environ.get("SMTP_HOST")
    user = os.environ.get("SMTP_USER")
    pw = os.environ.get("SMTP_PASS")
    port = int(os.environ.get("SMTP_PORT", "587"))
    test_mode = (
        os.environ.get("OUTREACH_TEST_MODE", "").lower() in ("1", "true", "yes")
        or not (host and user and pw)
    )
    plan = {"to": list(to_addresses), "subject": subject, "from": sender}

    if test_mode:
        return {"status": "dry_run", "sent": False,
                "reason": "SMTP not configured or test mode on", **plan}
    try:
        msg = MIMEText(body, _charset="utf-8")
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = ", ".join(to_addresses)
        ctx = ssl.create_default_context()
        with smtplib.SMTP(host, port, timeout=15) as s:
            s.starttls(context=ctx)
            s.login(user, pw)
            s.sendmail(sender, list(to_addresses), msg.as_string())
        return {"status": "sent", "sent": True, **plan}
    except Exception as e:
        return {"status": "failed", "sent": False, "error": str(e), **plan}


def send_approved_outreach(email_sequence: list[str], recipients: list[str]) -> list[dict]:
    """Send an approved email_sequence (the Sales Agent's output) to recipients.
    Call ONLY after the approval gate has approved the drafts."""
    results = []
    for i, email_text in enumerate(email_sequence or [], 1):
        subject, body = _split_subject(email_text, default_subject=f"Quick note ({i})")
        results.append(send_outreach(recipients, subject, body))
    return results
