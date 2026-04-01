from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import MessageEvent, UnifiedMessage


def _as_uuid(value: uuid.UUID | str | None) -> uuid.UUID | None:
    if value is None or value == "":
        return None
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


def log_message_event(
    db: Session,
    *,
    message: UnifiedMessage | None = None,
    message_id: uuid.UUID | str | None = None,
    event_type: str,
    payload: dict[str, Any] | None = None,
) -> MessageEvent:
    event = MessageEvent(
        message_id=_as_uuid(message_id) or (message.id if message is not None else None),
        event_type=event_type,
        payload=payload or {},
    )
    db.add(event)
    db.flush()
    return event
