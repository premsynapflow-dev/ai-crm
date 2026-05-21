from datetime import datetime, timezone
import uuid
from typing import Any

from app.db.models import EventLog
from app.services.customer_events import mirror_legacy_event


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_uuid(value: uuid.UUID | str | None) -> uuid.UUID | None:
    if value is None or value == "":
        return None
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def log_event(
    db,
    client_id,
    event_type: str,
    payload: dict | None = None,
    *,
    customer_id=None,
    complaint_id=None,
    source: str | None = None,
    actor_type: str | None = None,
    event_timestamp: datetime | None = None,
    sentiment_score: float | None = None,
    risk_delta: float | None = None,
):
    payload = payload or {}
    event = EventLog(
        client_id=_as_uuid(client_id),
        customer_id=_as_uuid(customer_id or payload.get("customer_id")),
        complaint_id=_as_uuid(complaint_id or payload.get("complaint_id")),
        event_type=event_type,
        source=source or payload.get("source") or payload.get("channel"),
        actor_type=actor_type or payload.get("actor_type"),
        event_timestamp=event_timestamp or _utcnow(),
        sentiment_score=_as_float(sentiment_score if sentiment_score is not None else payload.get("sentiment")),
        risk_delta=_as_float(risk_delta if risk_delta is not None else payload.get("risk_delta")),
        payload=payload,
    )
    db.add(event)
    db.flush()
    mirror_legacy_event(db, event, metadata=payload)
    return event
