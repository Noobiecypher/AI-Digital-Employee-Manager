"""
notification_service.py
=======================
Lightweight helper to insert notification documents into MongoDB.
The user identifier used is the ObjectId string (what get_current_user
returns as 'user_id' after converting _id → user_id in user_repository).
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Literal
from bson import ObjectId

from backend.database.mongo import get_client

NotifType = Literal[
    "workflow_started",
    "workflow_paused",
    "workflow_approved",
    "workflow_rejected",
    "workflow_completed",
    "workflow_failed",
    "goal_assigned",
    "goal_submitted",
    "goal_approved",
    "goal_rejected",
]

def _col():
    client = get_client()
    return client["ai_digital_employee"]["notifications"]

def _users_col():
    client = get_client()
    return client["ai_digital_employee"]["users"]

def _get_user_ids_by_roles(roles: list[str]) -> list[str]:
    """Return ObjectId strings for users with any of the given roles."""
    try:
        docs = _users_col().find({"role": {"$in": roles}}, {"_id": 1})
        return [str(d["_id"]) for d in docs]
    except Exception:
        return []

def _get_employee_user_ids(employee_name: str) -> list[str]:
    """Return ObjectId strings for employee users linked to employee_name."""
    try:
        docs = _users_col().find(
            {"employee_name": employee_name, "role": "employee"},
            {"_id": 1}
        )
        return [str(d["_id"]) for d in docs]
    except Exception:
        return []

def push(
    *,
    notif_type: NotifType,
    title: str,
    message: str,
    recipient_user_ids: list[str],
    link: str | None = None,
    meta: dict | None = None,
) -> None:
    """Insert one notification per recipient. Never raises."""
    if not recipient_user_ids:
        return
    try:
        now = datetime.now(timezone.utc).isoformat()
        docs = [
            {
                "notification_id": str(uuid.uuid4()),
                "user_id": uid,
                "type": notif_type,
                "title": title,
                "message": message,
                "link": link,
                "meta": meta or {},
                "read": False,
                "created_at": now,
            }
            for uid in recipient_user_ids
        ]
        _col().insert_many(docs)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Notification push failed: %s", exc)


# ── Convenience factories ────────────────────────────────────────────────────

def notify_workflow_started(workflow_id: str, objective_id: str) -> None:
    label = objective_id.replace("_", " ").title()
    push(
        notif_type="workflow_started",
        title="Workflow Started",
        message=f'"{label}" workflow has been initiated.',
        recipient_user_ids=_get_user_ids_by_roles(["admin", "manager"]),
        link=f"/workflows/{workflow_id}",
        meta={"workflow_id": workflow_id, "objective_id": objective_id},
    )

def notify_workflow_failed(workflow_id: str, objective_id: str) -> None:
    label = objective_id.replace("_", " ").title()
    push(
        notif_type="workflow_failed",
        title="Workflow Failed",
        message=f'"{label}" workflow encountered an error and failed.',
        recipient_user_ids=_get_user_ids_by_roles(["admin", "manager"]),
        link=f"/workflows/{workflow_id}",
        meta={"workflow_id": workflow_id, "objective_id": objective_id},
    )

def notify_workflow_paused(workflow_id: str, objective_id: str) -> None:
    label = objective_id.replace("_", " ").title()
    push(
        notif_type="workflow_paused",
        title="Approval Required",
        message=f'"{label}" workflow is waiting for your approval.',
        recipient_user_ids=_get_user_ids_by_roles(["admin", "manager"]),
        link=f"/workflows/{workflow_id}",
        meta={"workflow_id": workflow_id, "objective_id": objective_id},
    )

def notify_workflow_approved(workflow_id: str, objective_id: str) -> None:
    label = objective_id.replace("_", " ").title()
    push(
        notif_type="workflow_approved",
        title="Workflow Approved",
        message=f'"{label}" workflow was approved and is now running.',
        recipient_user_ids=_get_user_ids_by_roles(["admin", "manager"]),
        link=f"/workflows/{workflow_id}",
        meta={"workflow_id": workflow_id, "objective_id": objective_id},
    )

def notify_workflow_rejected(workflow_id: str, objective_id: str) -> None:
    label = objective_id.replace("_", " ").title()
    push(
        notif_type="workflow_rejected",
        title="Workflow Rejected",
        message=f'"{label}" workflow was rejected.',
        recipient_user_ids=_get_user_ids_by_roles(["admin", "manager"]),
        link=f"/workflows/{workflow_id}",
        meta={"workflow_id": workflow_id, "objective_id": objective_id},
    )

def notify_workflow_completed(workflow_id: str, objective_id: str) -> None:
    label = objective_id.replace("_", " ").title()
    push(
        notif_type="workflow_completed",
        title="Workflow Completed",
        message=f'"{label}" workflow has completed successfully.',
        recipient_user_ids=_get_user_ids_by_roles(["admin", "manager"]),
        link=f"/workflows/{workflow_id}",
        meta={"workflow_id": workflow_id, "objective_id": objective_id},
    )

def notify_goal_assigned(employee_name: str, review_period: str) -> None:
    push(
        notif_type="goal_assigned",
        title="New Goals Assigned",
        message=f"Goals have been set for you for {review_period}.",
        recipient_user_ids=_get_employee_user_ids(employee_name),
        link=f"/goals/{employee_name}/{review_period}",
        meta={"employee_name": employee_name, "review_period": review_period},
    )

def notify_goal_submitted(employee_name: str, review_period: str) -> None:
    push(
        notif_type="goal_submitted",
        title="Goal Update Submitted",
        message=f"{employee_name} submitted goal progress for {review_period} — awaiting your review.",
        recipient_user_ids=_get_user_ids_by_roles(["admin", "manager"]),
        link=f"/goals/{employee_name}/{review_period}",
        meta={"employee_name": employee_name, "review_period": review_period},
    )

def notify_goal_reviewed(employee_name: str, review_period: str, approved: bool) -> None:
    push(
        notif_type="goal_approved" if approved else "goal_rejected",
        title="Goals " + ("Approved ✓" if approved else "Rejected"),
        message=f"Your goal update for {review_period} was {'approved' if approved else 'rejected'} by your manager.",
        recipient_user_ids=_get_employee_user_ids(employee_name),
        link=f"/goals/{employee_name}/{review_period}",
        meta={"employee_name": employee_name, "review_period": review_period},
    )