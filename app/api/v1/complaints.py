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
from app.intake.webhook import _process_complaint_for_client
from app.replies.send_reply import send_complaint_reply
from app.services.event_logger import log_event

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
        "ai_confidence": round(confidence, 2),
        "ai_reply": complaint.ai_reply,
        "ticket_id": complaint.ticket_id,
        "resolution_status": complaint.resolution_status,
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
        return _get_user_from_token(db, authorization)
    return resolve_current_client_user(request, db)


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

    update_data = payload.model_dump(exclude_none=True)
    status_value = update_data.pop("status", None)
    if status_value is not None:
        _apply_status_update(complaint, status_value)
    for field, value in update_data.items():
        setattr(complaint, field, value)
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

    result = send_complaint_reply(
        db=db,
        complaint=complaint,
        client=client,
        reply_text=payload.reply_text,
    )
    db.commit()
    db.refresh(complaint)
    return {"complaint": _serialize_complaint(complaint), **result}


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
