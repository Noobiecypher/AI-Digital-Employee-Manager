"""
notification_routes.py
======================
GET  /api/notifications          — list notifications for the logged-in user
PATCH /api/notifications/:id/read — mark one as read
PATCH /api/notifications/read-all — mark all as read
"""
from __future__ import annotations
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from backend.auth.dependencies import get_current_user
from backend.database.mongo import get_client

notification_router = APIRouter()

def _col():
    client = get_client()
    return client["ai_digital_employee"]["notifications"]


@notification_router.get("/notifications")
async def list_notifications(
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("user_id") or current_user.get("id")
    docs = list(
        _col()
        .find({"user_id": user_id}, {"_id": 0})
        .sort("created_at", -1)
        .limit(50)
    )
    unread = sum(1 for d in docs if not d.get("read"))
    return {"total": len(docs), "unread": unread, "items": docs}


@notification_router.patch("/notifications/{notification_id}/read")
async def mark_read(
    notification_id: str,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("user_id") or current_user.get("id")
    _col().update_one(
        {"notification_id": notification_id, "user_id": user_id},
        {"$set": {"read": True}},
    )
    return {"ok": True}


@notification_router.patch("/notifications/read-all")
async def mark_all_read(
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("user_id") or current_user.get("id")
    result = _col().update_many(
        {"user_id": user_id, "read": False},
        {"$set": {"read": True}},
    )
    return {"ok": True, "updated": result.modified_count}