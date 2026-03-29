from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import Complaint


def mark_first_response(
    db: Session,
    complaint: Complaint,
    responded_at: datetime | None = None,
) -> bool:
    if complaint.first_response_at is not None:
        return False

    now = responded_at or datetime.now(timezone.utc)
    created_at = complaint.created_at
    if created_at is None:
        try:
            db.refresh(complaint)
            created_at = complaint.created_at
        except Exception:
            created_at = None

    if created_at is None:
        created_at = now
    elif created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    complaint.first_response_at = now
    complaint.response_time_seconds = max(0, int((now - created_at).total_seconds()))
    from app.services.sla_manager import SLAManager

    if hasattr(db, "query"):
        SLAManager(db).refresh_ticket_deadline(complaint, commit=False)

    if hasattr(db, "flush"):
        db.flush()
    return True


def mark_first_response_by_id(
    db: Session,
    complaint_id,
    responded_at: datetime | None = None,
) -> bool:
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if complaint is None:
        return False
    return mark_first_response(db, complaint, responded_at=responded_at)
