from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.db.models import UnifiedMessage
from app.db.session import SessionLocal
from app.services.message_events import log_message_event
from app.utils.logging import get_logger

logger = get_logger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _backoff_delay_seconds(retry_count: int) -> int:
    return min((2 ** retry_count) * 60, 3600)


def handle_failed_send(
    db: Session,
    *,
    message: UnifiedMessage,
    error: str,
    commit: bool = True,
) -> UnifiedMessage:
    next_retry_count = int(message.retry_count or 0) + 1
    delay_seconds = _backoff_delay_seconds(next_retry_count)

    message.retry_count = next_retry_count
    message.last_error = error
    message.next_retry_at = _utcnow() + timedelta(seconds=delay_seconds)
    message.status = "failed"
    db.flush()

    log_message_event(
        db,
        message=message,
        event_type="reply_failed",
        payload={
            "error": error,
            "retry_count": message.retry_count,
            "next_retry_at": message.next_retry_at.isoformat() if message.next_retry_at else None,
        },
    )
    if commit:
        db.commit()
        db.refresh(message)
    return message


def process_retry_queue(limit: int = 20) -> int:
    db = SessionLocal()
    processed = 0
    try:
        due_messages = (
            db.query(UnifiedMessage)
            .filter(
                UnifiedMessage.direction == "outbound",
                UnifiedMessage.status == "failed",
                UnifiedMessage.next_retry_at.isnot(None),
                UnifiedMessage.next_retry_at <= _utcnow(),
            )
            .order_by(UnifiedMessage.next_retry_at.asc())
            .limit(limit)
            .all()
        )

        for message in due_messages:
            try:
                from app.services.channel_router import retry_unified_message_send

                sent = retry_unified_message_send(db, message)
                if sent:
                    processed += 1
                    db.commit()
                else:
                    db.rollback()
            except Exception as exc:
                db.rollback()
                retry_message = db.query(UnifiedMessage).filter(UnifiedMessage.id == message.id).first()
                if retry_message is None:
                    logger.warning("Retry queue lost message %s during retry", message.id)
                    continue
                handle_failed_send(db, message=retry_message, error=str(exc), commit=True)
                logger.exception("Retry send failed for unified message %s: %s", retry_message.id, exc)

        return processed
    finally:
        db.close()
