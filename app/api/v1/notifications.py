from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.auth import resolve_current_client_user
from app.db.models import EventLog
from app.db.session import get_db

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications-v1"])

_EVENT_TITLES = {
    "complaint_received": "New complaint received",
    "complaint_escalated": "Complaint escalated",
    "frontend_escalation": "Complaint escalated",
    "complaint_resolved": "Complaint resolved",
    "complaint_reopened": "Complaint reopened",
    "ai_reply_queued_for_review": "AI reply queued for review",
    "ai_reply_rejected": "AI reply rejected",
    "ai_reply_sent": "AI reply sent",
    "agent_review_requested": "Agent review requested",
}

_EVENT_SEVERITY = {
    "complaint_received": "info",
    "complaint_escalated": "high",
    "frontend_escalation": "high",
    "complaint_resolved": "success",
    "complaint_reopened": "medium",
    "ai_reply_queued_for_review": "medium",
    "ai_reply_rejected": "medium",
    "ai_reply_sent": "success",
    "agent_review_requested": "medium",
}


def _notification_message(payload: dict, event_type: str) -> str:
    summary = str(payload.get("summary") or "").strip()
    ticket_id = str(payload.get("ticket_id") or "").strip()

    if event_type == "complaint_received" and ticket_id:
        return f"Ticket {ticket_id} is waiting in the complaints inbox."
    if event_type in {"complaint_escalated", "frontend_escalation"} and ticket_id:
        return f"Ticket {ticket_id} has been escalated for faster attention."
    if event_type == "complaint_resolved" and ticket_id:
        return f"Ticket {ticket_id} has been marked as resolved."
    if event_type == "complaint_reopened" and ticket_id:
        return f"Ticket {ticket_id} has been reopened."
    if event_type == "ai_reply_queued_for_review" and ticket_id:
        return f"AI drafted a response for ticket {ticket_id} and needs review."
    if event_type == "ai_reply_sent" and ticket_id:
        return f"A reply was sent for ticket {ticket_id}."
    if summary:
        return summary[:160]
    return _EVENT_TITLES.get(event_type, "Notification")


@router.get("")
def list_notifications(
    request: Request,
    limit: int = 15,
    db: Session = Depends(get_db),
):
    user = resolve_current_client_user(request, db)
    safe_limit = max(1, min(limit, 50))
    event_types = tuple(_EVENT_TITLES.keys())

    events = (
        db.query(EventLog)
        .filter(
            EventLog.client_id == user.client_id,
            EventLog.event_type.in_(event_types),
        )
        .order_by(EventLog.created_at.desc())
        .limit(safe_limit)
        .all()
    )

    items = []
    for event in events:
        payload = event.payload or {}
        items.append(
            {
                "id": str(event.id),
                "event_type": event.event_type,
                "title": _EVENT_TITLES.get(event.event_type, "Notification"),
                "message": _notification_message(payload, event.event_type),
                "severity": _EVENT_SEVERITY.get(event.event_type, "info"),
                "created_at": event.created_at.isoformat() if event.created_at else None,
                "ticket_id": payload.get("ticket_id"),
                "complaint_id": payload.get("complaint_id"),
                "href": "/complaints",
                "payload": payload,
            }
        )

    return {"items": items}
