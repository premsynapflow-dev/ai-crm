from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.billing.usage import can_process_ticket, track_ticket_usage
from app.db.models import Client, Conversation, UnifiedMessage
from app.services.event_logger import log_event
from app.services.message_events import log_message_event
from app.utils.logging import get_logger

logger = get_logger(__name__)


class IncomingMessage(BaseModel):
    client_id: uuid.UUID | str
    channel: str
    external_message_id: str
    external_thread_id: str | None = None
    sender_id: str | None = None
    sender_name: str | None = None
    message_text: str = Field(default="", max_length=50000)
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    direction: str = "inbound"
    status: str = "received"
    raw_payload: dict[str, Any] = Field(default_factory=dict)


def _as_uuid(value: uuid.UUID | str) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


def _normalize_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def ensure_conversation(
    db: Session,
    *,
    client_id: uuid.UUID | str,
    channel: str,
    external_thread_id: str,
    customer_id: str | None,
    timestamp: datetime,
    status: str = "open",
) -> Conversation:
    normalized_client_id = _as_uuid(client_id)
    normalized_timestamp = _normalize_timestamp(timestamp)
    bind = db.get_bind()

    if bind is not None and bind.dialect.name.startswith("postgresql"):
        stmt = (
            pg_insert(Conversation)
            .values(
                client_id=normalized_client_id,
                channel=channel,
                external_thread_id=external_thread_id,
                customer_id=customer_id,
                last_message_at=normalized_timestamp,
                status=status,
            )
            .on_conflict_do_update(
                index_elements=["client_id", "channel", "external_thread_id"],
                set_={
                    "last_message_at": normalized_timestamp,
                    "customer_id": customer_id if customer_id else Conversation.customer_id,
                    "status": status,
                },
            )
            .returning(Conversation.id)
        )
        conversation_id = db.execute(stmt).scalar_one()
        conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if conversation is None:
            raise RuntimeError("Conversation upsert failed")
        return conversation

    conversation = (
        db.query(Conversation)
        .filter(
            Conversation.client_id == normalized_client_id,
            Conversation.channel == channel,
            Conversation.external_thread_id == external_thread_id,
        )
        .first()
    )
    if conversation is None:
        conversation = Conversation(
            client_id=normalized_client_id,
            channel=channel,
            external_thread_id=external_thread_id,
            customer_id=customer_id,
            last_message_at=normalized_timestamp,
            status=status,
        )
        db.add(conversation)
    else:
        conversation.last_message_at = normalized_timestamp
        if customer_id and not conversation.customer_id:
            conversation.customer_id = customer_id
        conversation.status = status
    db.flush()
    return conversation


def _customer_fields_for_message(message: IncomingMessage) -> tuple[str | None, str | None]:
    if message.channel in {"gmail", "email"}:
        return message.sender_id, None
    if message.channel == "whatsapp":
        return None, message.sender_id
    return None, None


def _resolve_message_conversation(db: Session, message: IncomingMessage) -> Conversation:
    external_thread_id = message.external_thread_id or message.external_message_id
    return ensure_conversation(
        db,
        client_id=message.client_id,
        channel=message.channel,
        external_thread_id=external_thread_id,
        customer_id=message.sender_id,
        timestamp=message.timestamp,
    )


def process_incoming_message(db: Session, message: IncomingMessage) -> dict[str, Any]:
    existing = (
        db.query(UnifiedMessage)
        .filter(
            UnifiedMessage.channel == message.channel,
            UnifiedMessage.external_message_id == message.external_message_id,
        )
        .first()
    )
    if existing is not None:
        return {
            "status": "duplicate",
            "message_id": str(existing.id),
            "external_message_id": existing.external_message_id,
        }

    conversation = _resolve_message_conversation(db, message)
    unified_message = UnifiedMessage(
        client_id=_as_uuid(message.client_id),
        channel=message.channel,
        external_message_id=message.external_message_id,
        external_thread_id=conversation.external_thread_id,
        sender_id=message.sender_id,
        sender_name=message.sender_name,
        message_text=message.message_text,
        attachments=message.attachments,
        timestamp=_normalize_timestamp(message.timestamp),
        direction=message.direction,
        status=message.status,
        raw_payload={
            **message.raw_payload,
            "conversation_id": str(conversation.id),
        },
    )
    db.add(unified_message)
    db.flush()

    client = db.query(Client).filter(Client.id == _as_uuid(message.client_id)).first()
    if client is None:
        raise ValueError("Client not found for incoming message")

    log_message_event(
        db,
        message=unified_message,
        event_type="message_received",
        payload={
            "channel": message.channel,
            "direction": message.direction,
            "conversation_id": str(conversation.id),
            "external_message_id": message.external_message_id,
        },
    )
    log_event(
        db,
        client.id,
        "channel_message_ingested",
        {
            "channel": message.channel,
            "external_message_id": message.external_message_id,
            "direction": message.direction,
            "conversation_id": str(conversation.id),
        },
    )

    if message.direction != "inbound":
        conversation.last_message_at = unified_message.timestamp
        db.flush()
        return {
            "status": "stored",
            "message_id": str(unified_message.id),
            "conversation_id": str(conversation.id),
        }

    if not can_process_ticket(client.id):
        unified_message.status = "quota_blocked"
        log_message_event(
            db,
            message=unified_message,
            event_type="message_processed",
            payload={
                "outcome": "quota_blocked",
                "conversation_id": str(conversation.id),
            },
        )
        log_event(
            db,
            client.id,
            "channel_message_quota_blocked",
            {
                "channel": message.channel,
                "external_message_id": message.external_message_id,
                "conversation_id": str(conversation.id),
            },
        )
        db.flush()
        return {
            "status": "quota_blocked",
            "message_id": str(unified_message.id),
            "conversation_id": str(conversation.id),
        }

    customer_email, customer_phone = _customer_fields_for_message(message)
    from app.intake.webhook import _process_complaint_for_client

    complaint = _process_complaint_for_client(
        db=db,
        client=client,
        message=message.message_text,
        source=message.channel,
        customer_email=customer_email,
        customer_phone=customer_phone,
        return_complaint=True,
    )

    unified_message.status = "processed"
    unified_message.retry_count = 0
    unified_message.last_error = None
    unified_message.next_retry_at = None
    unified_message.raw_payload = {
        **(unified_message.raw_payload or {}),
        "complaint_id": str(complaint.id),
        "ticket_id": complaint.ticket_id,
        "complaint_thread_id": complaint.thread_id,
        "conversation_id": str(conversation.id),
    }
    conversation.last_message_at = unified_message.timestamp
    track_ticket_usage(client.id)

    log_message_event(
        db,
        message=unified_message,
        event_type="message_processed",
        payload={
            "conversation_id": str(conversation.id),
            "complaint_id": str(complaint.id),
            "ticket_id": complaint.ticket_id,
        },
    )
    if complaint.ai_reply:
        log_message_event(
            db,
            message=unified_message,
            event_type="reply_generated",
            payload={
                "complaint_id": str(complaint.id),
                "ticket_id": complaint.ticket_id,
                "reply_status": complaint.ai_reply_status,
                "confidence": complaint.ai_reply_confidence,
            },
        )
    db.flush()

    logger.info(
        "Processed inbound %s message %s for client %s into complaint %s",
        message.channel,
        message.external_message_id,
        client.id,
        complaint.id,
    )
    return {
        "status": "processed",
        "message_id": str(unified_message.id),
        "conversation_id": str(conversation.id),
        "complaint_id": str(complaint.id),
        "ticket_id": complaint.ticket_id,
    }
