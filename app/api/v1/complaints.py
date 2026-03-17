from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.auth import decode_token
from app.billing.usage import can_process_ticket, track_ticket_usage
from app.config import get_settings
from app.db.models import Client, ClientUser, Complaint
from app.db.session import get_db
from app.intake.webhook import _process_complaint_for_client

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


@router.get("")
def list_complaints(page: int = 1, page_size: int = 20, authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    user = _get_user_from_token(db, authorization)
    query = db.query(Complaint).filter(Complaint.client_id == user.client_id).order_by(Complaint.created_at.desc())
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    total = query.count()
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/{complaint_id}")
def get_complaint(complaint_id: str, authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    user = _get_user_from_token(db, authorization)
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id, Complaint.client_id == user.client_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    return complaint


@router.post("")
def create_complaint(payload: ComplaintCreateRequest, authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    user = _get_user_from_token(db, authorization)
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
def update_complaint(complaint_id: str, payload: ComplaintUpdateRequest, authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    user = _get_user_from_token(db, authorization)
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id, Complaint.client_id == user.client_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(complaint, field, value)
    db.commit()
    db.refresh(complaint)
    return complaint
