from __future__ import annotations

from datetime import datetime, timezone
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import CustomerEvent


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_uuid(value: uuid.UUID | str | None) -> uuid.UUID | None:
    if value is None or value == "":
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def log_customer_event(
    db: Session,
    *,
    client_id: uuid.UUID | str,
    event_type: str,
    source: str,
    metadata: dict[str, Any] | None = None,
    customer_id: uuid.UUID | str | None = None,
    conversation_id: uuid.UUID | str | None = None,
    message_id: uuid.UUID | str | None = None,
    workflow_execution_id: uuid.UUID | str | None = None,
    complaint_id: uuid.UUID | str | None = None,
    source_event_id: uuid.UUID | str | None = None,
    actor_type: str | None = None,
    actor_id: str | None = None,
    event_timestamp: datetime | None = None,
    sentiment_score: float | None = None,
    risk_delta: float | None = None,
) -> CustomerEvent:
    payload = dict(metadata or {})
    parsed_client_id = _as_uuid(client_id)
    if parsed_client_id is None:
        raise ValueError("customer_events require a tenant-scoped client_id")
    event = CustomerEvent(
        client_id=parsed_client_id,
        customer_id=_as_uuid(customer_id or payload.get("customer_id")),
        conversation_id=_as_uuid(conversation_id or payload.get("conversation_id")),
        message_id=_as_uuid(message_id or payload.get("message_id")),
        workflow_execution_id=_as_uuid(workflow_execution_id or payload.get("workflow_execution_id")),
        complaint_id=_as_uuid(complaint_id or payload.get("complaint_id")),
        source=source or payload.get("source") or "unknown",
        source_event_id=_as_uuid(source_event_id),
        event_type=event_type,
        actor_type=actor_type or payload.get("actor_type") or "system",
        actor_id=str(actor_id or payload.get("actor_id")) if actor_id or payload.get("actor_id") else None,
        event_timestamp=event_timestamp or _utcnow(),
        metadata_json=payload,
        sentiment_score=_as_float(sentiment_score if sentiment_score is not None else payload.get("sentiment")),
        risk_delta=_as_float(risk_delta if risk_delta is not None else payload.get("risk_delta")),
    )
    db.add(event)
    db.flush()
    return event


def mirror_legacy_event(
    db: Session,
    legacy_event: Any,
    *,
    metadata: dict[str, Any] | None = None,
    message_id: uuid.UUID | str | None = None,
) -> CustomerEvent | None:
    client_id = _as_uuid(getattr(legacy_event, "client_id", None))
    if client_id is None:
        return None

    payload = dict(metadata if metadata is not None else (getattr(legacy_event, "payload", None) or {}))
    customer_id = getattr(legacy_event, "customer_id", None) or payload.get("customer_id")
    # customer_events.customer_id is NOT NULL — skip mirror if customer isn't resolved yet.
    if not customer_id:
        return None
    return log_customer_event(
        db,
        client_id=client_id,
        customer_id=customer_id,
        complaint_id=getattr(legacy_event, "complaint_id", None) or payload.get("complaint_id"),
        conversation_id=payload.get("conversation_id"),
        message_id=message_id or getattr(legacy_event, "message_id", None) or payload.get("message_id"),
        workflow_execution_id=payload.get("workflow_execution_id"),
        source_event_id=getattr(legacy_event, "id", None),
        event_type=getattr(legacy_event, "event_type"),
        source=getattr(legacy_event, "source", None) or payload.get("source") or "legacy",
        actor_type=getattr(legacy_event, "actor_type", None) or payload.get("actor_type") or "system",
        actor_id=payload.get("actor_id"),
        event_timestamp=getattr(legacy_event, "event_timestamp", None) or getattr(legacy_event, "created_at", None),
        sentiment_score=getattr(legacy_event, "sentiment_score", None),
        risk_delta=getattr(legacy_event, "risk_delta", None),
        metadata=payload,
    )
