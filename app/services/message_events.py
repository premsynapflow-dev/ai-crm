from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import MessageEvent, UnifiedMessage


def _as_uuid(value: uuid.UUID | str | None) -> uuid.UUID | None:
    if value is None or value == "":
        return None
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def log_message_event(
    db: Session,
    *,
    message: UnifiedMessage | None = None,
    message_id: uuid.UUID | str | None = None,
    event_type: str,
    payload: dict[str, Any] | None = None,
    customer_id: uuid.UUID | str | None = None,
    complaint_id: uuid.UUID | str | None = None,
    source: str | None = None,
    actor_type: str | None = None,
    event_timestamp: datetime | None = None,
    sentiment_score: float | None = None,
    risk_delta: float | None = None,
) -> MessageEvent:
    payload = payload or {}
    raw_payload = message.raw_payload if message is not None and isinstance(message.raw_payload, dict) else {}
    event = MessageEvent(
        message_id=_as_uuid(message_id) or (message.id if message is not None else None),
        client_id=(message.client_id if message is not None else _as_uuid(payload.get("client_id"))),
        customer_id=_as_uuid(customer_id or payload.get("customer_id") or (message.customer_id if message is not None else None)),
        complaint_id=_as_uuid(complaint_id or payload.get("complaint_id") or raw_payload.get("complaint_id")),
        event_type=event_type,
        source=source or payload.get("source") or (message.channel if message is not None else None),
        actor_type=actor_type or payload.get("actor_type") or ("customer" if message is not None and message.direction == "inbound" else None),
        event_timestamp=event_timestamp or (message.timestamp if message is not None else None) or _utcnow(),
        sentiment_score=_as_float(sentiment_score if sentiment_score is not None else payload.get("sentiment")),
        risk_delta=_as_float(risk_delta if risk_delta is not None else payload.get("risk_delta")),
        payload=payload,
    )
    db.add(event)
    db.flush()
    return event
