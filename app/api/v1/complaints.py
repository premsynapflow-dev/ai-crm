"""
Complaints API endpoints.

SECURITY NOTE: All endpoints MUST filter by client.id to ensure data isolation.
Never return complaints from other clients.

Example of correct filtering:
    complaints = db.query(Complaint).filter(
        Complaint.client_id == client.id
    ).all()
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.v1.auth import decode_token
from app.auth import resolve_current_client_user
from app.billing.usage import can_process_ticket, track_ticket_usage
from app.config import get_settings
from app.db.models import Client, ClientUser, Complaint
from app.db.session import get_db
from app.middleware.feature_gate import ensure_feature_access
from app.intake.webhook import _process_complaint_for_client
from app.replies.send_reply import send_complaint_reply
from app.services.ai import suggest_response
from app.services.auto_reply_hardened import HardenedAutoReplyService
from app.services.customer_profile import CustomerProfileService
from app.services.event_logger import log_event
from app.services.rbi_compliance import RBIComplianceService
from app.services.ticket_state_machine import TicketStateMachine

router = APIRouter(prefix="/api/v1/complaints", tags=["complaints-v1"])
settings = get_settings()


class ComplaintCreateRequest(BaseModel):
    message: str = Field(..., min_length=1)
    source: str = Field(default="api")
    customer_email: str | None = None
    customer_phone: str | None = None
    ticket_id: str | None = None


class ComplaintUpdateRequest(BaseModel):
    status: str | None = None
    resolution_status: str | None = None
    follow_up_status: str | None = None


class ComplaintReplyRequest(BaseModel):
    reply_text: str = Field(..., min_length=1)


def _priority_label(priority: int | None) -> str:
    if priority is None or priority <= 1:
        return "low"
    if priority == 2:
        return "medium"
    if priority in {3, 4}:
        return "high"
    return "critical"


def _sentiment_label(value: float | None) -> str:
    score = float(value or 0)
    if score > 0.2:
        return "positive"
    if score < -0.2:
        return "negative"
    return "neutral"


def _status_label(complaint: Complaint) -> str:
    if complaint.resolution_status == "resolved":
        return "resolved"
    if complaint.status == "ESCALATE_HIGH" or complaint.ai_reply_status == "agent_review":
        return "escalated"
    if complaint.ai_reply or complaint.ai_reply_sent_at or complaint.status not in {"PENDING", "NEW", None}:
        return "in-progress"
    return "new"


def _customer_name(email: str | None) -> str:
    local_part = (email or "").split("@", 1)[0].replace(".", " ").replace("_", " ").strip()
    if local_part:
        return " ".join(part.capitalize() for part in local_part.split())
    return "Customer"


def _serialize_complaint(complaint: Complaint) -> dict[str, object]:
    created_at = complaint.created_at.isoformat() if complaint.created_at else None
    updated_at = complaint.resolved_at.isoformat() if complaint.resolved_at else created_at
    confidence = float(complaint.ai_reply_confidence or complaint.confidence or 0.0) * 100

    return {
        "id": str(complaint.id),
        "customer_name": _customer_name(complaint.customer_email),
        "customer_email": complaint.customer_email or "",
        "customer_phone": complaint.customer_phone or "",
        "subject": complaint.summary,
        "complaint_text": complaint.summary,
        "category": complaint.category,
        "priority": _priority_label(complaint.priority),
        "sentiment": _sentiment_label(complaint.sentiment),
        "status": _status_label(complaint),
        "created_at": created_at,
        "updated_at": updated_at,
        "first_response_at": complaint.first_response_at.isoformat() if complaint.first_response_at else None,
        "resolved_at": complaint.resolved_at.isoformat() if complaint.resolved_at else None,
        "ai_confidence": round(confidence, 2),
        "ai_reply": complaint.ai_reply,
        "ticket_id": complaint.ticket_id,
        "ticket_number": complaint.ticket_number or complaint.ticket_id,
        "customer_id": str(complaint.customer_id) if complaint.customer_id else None,
        "state": complaint.state,
        "state_changed_at": complaint.state_changed_at.isoformat() if complaint.state_changed_at else None,
        "sla_due_at": complaint.sla_due_at.isoformat() if complaint.sla_due_at else None,
        "sla_status": complaint.sla_status,
        "escalation_level": complaint.escalation_level,
        "escalated_at": complaint.escalated_at.isoformat() if complaint.escalated_at else None,
        "escalated_to": complaint.escalated_to,
        "reopened_count": complaint.reopened_count,
        "resolution_status": complaint.resolution_status,
        "sentiment_score": complaint.sentiment_score,
        "sentiment_label": complaint.sentiment_label,
        "sentiment_indicators": complaint.sentiment_indicators or [],
        "assigned_to": complaint.assigned_to or complaint.assigned_team,
        "satisfaction_score": complaint.satisfaction_score or complaint.customer_satisfaction_score,
    }


def _apply_status_update(complaint: Complaint, status_value: str) -> None:
    normalized = status_value.strip().lower()
    if normalized == "resolved":
        complaint.resolution_status = "resolved"
        complaint.status = "RESOLVED"
        complaint.resolved_at = complaint.resolved_at or datetime.now(timezone.utc)
        return
    if normalized == "escalated":
        complaint.resolution_status = "open"
        complaint.status = "ESCALATE_HIGH"
        complaint.ai_reply_status = "agent_review"
        return
    if normalized == "in-progress":
        complaint.resolution_status = "open"
        complaint.status = "IN_PROGRESS"
        return
    if normalized == "new":
        complaint.resolution_status = "open"
        complaint.status = "PENDING"
        return
    complaint.status = status_value


def _get_user_from_token(db: Session, authorization: str | None):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1]
    try:
        data = decode_token(token, "access", settings.access_token_expire_minutes * 60)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc
    user = db.query(ClientUser).filter(ClientUser.id == data.get("sub")).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def _get_authenticated_user(request: Request, db: Session, authorization: str | None):
    if authorization:
        user = _get_user_from_token(db, authorization)
    else:
        user = resolve_current_client_user(request, db)
    request.state.client_id = str(user.client_id)
    request.state.client_user_id = str(user.id)
    return user


def _generate_suggested_response(db: Session, complaint: Complaint, client: Client) -> dict:
    ensure_feature_access(client, "ai_suggested_responses")
    similar = (
        db.query(Complaint)
        .filter(
            Complaint.client_id == client.id,
            Complaint.category == complaint.category,
            Complaint.resolution_status == "resolved",
            Complaint.ai_reply.isnot(None),
        )
        .limit(5)
        .all()
    )
    similar_data = [
        {
            "complaint_text": item.summary,
            "resolution": item.ai_reply,
        }
        for item in similar
    ]
    return suggest_response(complaint.summary, complaint.category, similar_data)


@router.get("")
def list_complaints(
    request: Request,
    page: int = 1,
    page_size: int = 20,
    category: str | None = None,
    priority: str | None = None,
    status: str | None = None,
    search: str | None = None,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _get_authenticated_user(request, db, authorization)
    query = db.query(Complaint).filter(Complaint.client_id == user.client_id)

    if category:
        query = query.filter(Complaint.category == category)
    if priority:
        if priority == "low":
            query = query.filter(or_(Complaint.priority.is_(None), Complaint.priority <= 1))
        elif priority == "medium":
            query = query.filter(Complaint.priority == 2)
        elif priority == "high":
            query = query.filter(Complaint.priority.in_([3, 4]))
        elif priority == "critical":
            query = query.filter(Complaint.priority >= 5)
    if status == "resolved":
        query = query.filter(Complaint.resolution_status == "resolved")
    elif status == "escalated":
        query = query.filter(or_(Complaint.status == "ESCALATE_HIGH", Complaint.ai_reply_status == "agent_review"))
    elif status == "in-progress":
        query = query.filter(
            Complaint.resolution_status != "resolved",
            Complaint.status != "ESCALATE_HIGH",
            or_(Complaint.ai_reply.isnot(None), Complaint.ai_reply_sent_at.isnot(None)),
        )
    elif status == "new":
        query = query.filter(
            Complaint.resolution_status != "resolved",
            Complaint.status != "ESCALATE_HIGH",
            Complaint.ai_reply.is_(None),
        )
    if search:
        like_value = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Complaint.summary.ilike(like_value),
                Complaint.customer_email.ilike(like_value),
                Complaint.ticket_id.ilike(like_value),
            )
        )

    query = query.order_by(Complaint.created_at.desc())
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    total = query.count()
    return {"items": [_serialize_complaint(item) for item in items], "total": total, "page": page, "page_size": page_size}


@router.get("/{complaint_id}")
def get_complaint(
    complaint_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _get_authenticated_user(request, db, authorization)
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id, Complaint.client_id == user.client_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    return _serialize_complaint(complaint)


@router.post("")
def create_complaint(
    payload: ComplaintCreateRequest,
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _get_authenticated_user(request, db, authorization)
    client = db.query(Client).filter(Client.id == user.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    if not can_process_ticket(user.client_id):
        raise HTTPException(status_code=402, detail="Usage limit exceeded")

    action = _process_complaint_for_client(
        db=db,
        client=client,
        message=payload.message,
        source=payload.source,
        customer_email=payload.customer_email,
        customer_phone=payload.customer_phone,
        incoming_ticket_id=payload.ticket_id,
    )
    db.commit()
    track_ticket_usage(user.client_id)
    return {"status": "processed", "action": action}


@router.patch("/{complaint_id}")
def update_complaint(
    complaint_id: str,
    payload: ComplaintUpdateRequest,
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _get_authenticated_user(request, db, authorization)
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id, Complaint.client_id == user.client_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    was_resolved = complaint.resolution_status == "resolved"
    update_data = payload.model_dump(exclude_none=True)
    changed_fields = set(update_data)
    status_value = update_data.pop("status", None)
    if status_value is not None:
        _apply_status_update(complaint, status_value)
        changed_fields.add("status")
    for field, value in update_data.items():
        setattr(complaint, field, value)
    TicketStateMachine(db).sync_from_legacy(
        complaint,
        transitioned_by=user.email,
        reason="Complaint updated via v1 API",
        metadata={"fields": sorted(changed_fields)},
        commit=False,
    )
    CustomerProfileService(db).sync_customer_for_complaint(
        complaint,
        interaction_type="ticket",
        interaction_channel=complaint.source,
        commit=False,
    )
    normalized_status = (status_value or "").strip().lower()
    if normalized_status == "escalated":
        HardenedAutoReplyService(db).record_feedback(
            complaint,
            escalated_after_reply=True,
            commit=False,
        )
        log_event(
            db,
            complaint.client_id,
            "complaint_escalated",
            {
                "ticket_id": complaint.ticket_id,
                "complaint_id": str(complaint.id),
                "summary": complaint.summary,
                "source": "patch_update",
            },
        )
    elif normalized_status == "resolved" and complaint.resolution_status == "resolved":
        log_event(
            db,
            complaint.client_id,
            "complaint_resolved",
            {
                "ticket_id": complaint.ticket_id,
                "complaint_id": str(complaint.id),
                "summary": complaint.summary,
            },
        )
    elif was_resolved and complaint.resolution_status != "resolved":
        HardenedAutoReplyService(db).record_feedback(
            complaint,
            ticket_reopened=True,
            commit=False,
        )
        log_event(
            db,
            complaint.client_id,
            "complaint_reopened",
            {
                "ticket_id": complaint.ticket_id,
                "complaint_id": str(complaint.id),
                "summary": complaint.summary,
            },
        )
    if complaint.rbi_complaint:
        RBIComplianceService(db).sync_from_complaint(complaint, commit=False)
    db.commit()
    db.refresh(complaint)
    return _serialize_complaint(complaint)


@router.post("/{complaint_id}/reply")
def reply_to_complaint(
    complaint_id: str,
    payload: ComplaintReplyRequest,
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _get_authenticated_user(request, db, authorization)
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id, Complaint.client_id == user.client_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    client = db.query(Client).filter(Client.id == user.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    queue_entry = complaint.reply_queue
    if queue_entry and queue_entry.status == "pending":
        approved = HardenedAutoReplyService(db).approve_reply(
            str(queue_entry.id),
            reviewer_email=user.email,
            edited_reply=payload.reply_text,
            commit=False,
        )
        if not approved:
            raise HTTPException(status_code=400, detail="Queue item could not be approved")
        result = {"sent": complaint.ai_reply_status == "sent", "channels": []}
    else:
        result = send_complaint_reply(
            db=db,
            complaint=complaint,
            client=client,
            reply_text=payload.reply_text,
        )
    db.commit()
    db.refresh(complaint)
    return {"complaint": _serialize_complaint(complaint), **result}


@router.post("/{complaint_id}/suggest-reply")
def suggest_reply_for_complaint(
    complaint_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _get_authenticated_user(request, db, authorization)
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id, Complaint.client_id == user.client_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    client = db.query(Client).filter(Client.id == user.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    suggestion = _generate_suggested_response(db, complaint, client)
    complaint.ai_reply = suggestion["suggested_response"]
    complaint.ai_reply_confidence = suggestion["confidence"]
    complaint.ai_reply_status = "pending"
    db.commit()
    db.refresh(complaint)
    return _serialize_complaint(complaint)


@router.get("/{complaint_id}/suggest-response")
def get_suggested_response(
    complaint_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _get_authenticated_user(request, db, authorization)
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id, Complaint.client_id == user.client_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    client = db.query(Client).filter(Client.id == user.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    return _generate_suggested_response(db, complaint, client)


@router.post("/{complaint_id}/escalate")
def escalate_complaint(
    complaint_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _get_authenticated_user(request, db, authorization)
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id, Complaint.client_id == user.client_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    complaint.ai_reply_status = "agent_review"
    complaint.status = "ESCALATE_HIGH"
    complaint.resolution_status = "open"
    complaint.escalation_level = max(int(complaint.escalation_level or 0), 1)
    queue_entry = complaint.reply_queue
    if queue_entry and queue_entry.status == "pending":
        HardenedAutoReplyService(db).reject_reply(
            str(queue_entry.id),
            reviewer_email=user.email,
            reason="Escalated to agent via v1 API",
            commit=False,
        )
    TicketStateMachine(db).sync_from_legacy(
        complaint,
        transitioned_by=user.email,
        reason="Manual escalation via v1 API",
        metadata={"source": "api_v1_complaints"},
        commit=False,
    )
    CustomerProfileService(db).sync_customer_for_complaint(
        complaint,
        interaction_type="ticket",
        interaction_channel=complaint.source,
        commit=False,
    )
    HardenedAutoReplyService(db).record_feedback(
        complaint,
        escalated_after_reply=True,
        commit=False,
    )
    if complaint.rbi_complaint:
        RBIComplianceService(db).sync_from_complaint(complaint, commit=False)
    log_event(
        db,
        complaint.client_id,
        "frontend_escalation",
        {
            "ticket_id": complaint.ticket_id,
            "complaint_id": str(complaint.id),
            "summary": complaint.summary,
        },
    )
    db.commit()
    db.refresh(complaint)
    return _serialize_complaint(complaint)


@router.delete("/{complaint_id}")
def delete_complaint(
    complaint_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _get_authenticated_user(request, db, authorization)
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id, Complaint.client_id == user.client_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    db.delete(complaint)
    db.commit()
    return {"ok": True, "id": complaint_id}
