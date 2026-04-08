from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import ChannelConnection, Client, Complaint, UnifiedMessage
from app.db.session import SessionLocal
from app.inboxes.models import Inbox
from app.services.event_logger import log_event
from app.services.message_events import log_message_event
from app.services.retry_service import handle_failed_send
from app.services.unified_ingestion import ensure_conversation
from app.utils.logging import get_logger

logger = get_logger(__name__)


def _latest_inbound_for_complaint(db: Session, complaint: Complaint) -> UnifiedMessage | None:
    query = (
        db.query(UnifiedMessage)
        .filter(
            UnifiedMessage.client_id == complaint.client_id,
            UnifiedMessage.channel == complaint.source,
            UnifiedMessage.direction == "inbound",
        )
        .order_by(UnifiedMessage.timestamp.desc())
    )

    try:
        linked = query.filter(
            UnifiedMessage.raw_payload["complaint_id"].as_string() == str(complaint.id)
        ).first()
        if linked is not None:
            return linked
    except Exception:
        logger.debug("JSON complaint lookup unavailable for complaint %s", complaint.id)

    if complaint.thread_id:
        threaded = query.filter(UnifiedMessage.external_thread_id == complaint.thread_id).first()
        if threaded is not None:
            return threaded

    sender_id = complaint.customer_email if complaint.source in {"gmail", "email"} else complaint.customer_phone
    if not sender_id:
        return query.first()
    return query.filter(UnifiedMessage.sender_id == sender_id).first()


def _resolve_connection(db: Session, inbound_message: UnifiedMessage | None, complaint: Complaint) -> ChannelConnection | Inbox | None:
    connection_id = None
    inbox_id = None
    account_identifier = None
    if inbound_message and isinstance(inbound_message.raw_payload, dict):
        connection_id = inbound_message.raw_payload.get("connection_id")
        inbox_id = inbound_message.raw_payload.get("inbox_id")
        account_identifier = inbound_message.raw_payload.get("account_identifier")
    if inbox_id:
        inbox = db.query(Inbox).filter(Inbox.id == inbox_id, Inbox.is_active == True).first()
        if inbox is not None:
            return inbox
    if connection_id:
        return db.query(ChannelConnection).filter(ChannelConnection.id == connection_id).first()

    if complaint.source == "gmail":
        inbox_query = db.query(Inbox).filter(
            Inbox.tenant_id == complaint.client_id,
            Inbox.provider_type == "gmail",
            Inbox.is_active == True,
        )
        if account_identifier:
            inbox = inbox_query.filter(Inbox.email_address == account_identifier).first()
            if inbox is not None:
                return inbox
        inbox = inbox_query.order_by(Inbox.created_at.desc()).first()
        if inbox is not None:
            return inbox

    account_identifier = account_identifier or (complaint.customer_email if complaint.source in {"gmail", "email"} else complaint.customer_phone)
    channel_type = complaint.source if complaint.source in {"gmail", "whatsapp"} else "email"
    query = db.query(ChannelConnection).filter(
        ChannelConnection.client_id == complaint.client_id,
        ChannelConnection.channel_type == channel_type,
        ChannelConnection.status == "active",
    )
    if account_identifier:
        specific = query.filter(ChannelConnection.account_identifier == account_identifier).first()
        if specific is not None:
            return specific
    return query.order_by(ChannelConnection.created_at.desc()).first()


def _persist_outbound_message(
    db: Session,
    *,
    complaint: Complaint,
    client: Client | None,
    inbound_message: UnifiedMessage | None,
    message_text: str,
    outbound_message: UnifiedMessage | None = None,
    status: str = "pending",
) -> UnifiedMessage:
    external_thread_id = (inbound_message.external_thread_id if inbound_message else None) or complaint.thread_id
    conversation = ensure_conversation(
        db,
        client_id=complaint.client_id,
        channel=complaint.source,
        external_thread_id=external_thread_id,
        customer_id=complaint.customer_email if complaint.source in {"gmail", "email"} else complaint.customer_phone,
        timestamp=datetime.now(timezone.utc),
    )

    if outbound_message is None:
        outbound_message = UnifiedMessage(
            client_id=complaint.client_id,
            channel=complaint.source,
            external_message_id=f"pending-{uuid.uuid4()}",
            external_thread_id=conversation.external_thread_id,
            sender_id=None,
            sender_name=client.name if client else "SynapFlow",
            message_text=message_text,
            attachments=[],
            timestamp=datetime.now(timezone.utc),
            direction="outbound",
            status=status,
            raw_payload={},
        )
        db.add(outbound_message)

    outbound_message.external_thread_id = conversation.external_thread_id
    outbound_message.message_text = message_text
    outbound_message.status = status
    outbound_message.timestamp = datetime.now(timezone.utc)
    outbound_message.raw_payload = {
        **(outbound_message.raw_payload or {}),
        "conversation_id": str(conversation.id),
        "complaint_id": str(complaint.id),
        "ticket_id": complaint.ticket_id,
        "source": complaint.source,
        "direction": "outbound",
        "customer_email": complaint.customer_email,
        "customer_phone": complaint.customer_phone,
        "sender_name": client.name if client else "SynapFlow",
    }
    conversation.last_message_at = outbound_message.timestamp
    db.flush()
    return outbound_message


def _mark_outbound_sent(
    db: Session,
    *,
    outbound_message: UnifiedMessage,
    external_message_id: str,
    external_thread_id: str | None,
    sender_id: str | None,
    sender_name: str | None,
    raw_payload: dict[str, Any],
) -> UnifiedMessage:
    outbound_message.external_message_id = external_message_id
    outbound_message.external_thread_id = external_thread_id
    outbound_message.sender_id = sender_id
    outbound_message.sender_name = sender_name
    outbound_message.status = "sent"
    outbound_message.retry_count = 0
    outbound_message.last_error = None
    outbound_message.next_retry_at = None
    outbound_message.timestamp = datetime.now(timezone.utc)
    outbound_message.raw_payload = {
        **(outbound_message.raw_payload or {}),
        **raw_payload,
    }
    db.flush()
    return outbound_message


def send_reply_via_original_channel(
    db: Session,
    complaint: Complaint,
    client: Client | None,
    reply_text: str,
    *,
    allow_retry_enqueue: bool = True,
    outbound_message: UnifiedMessage | None = None,
) -> dict[str, Any]:
    channel = (complaint.source or "").lower()
    if channel not in {"gmail", "email", "whatsapp"}:
        return {"sent": False, "channels": []}

    inbound_message = _latest_inbound_for_complaint(db, complaint)
    outbound_message = _persist_outbound_message(
        db,
        complaint=complaint,
        client=client,
        inbound_message=inbound_message,
        message_text=reply_text,
        outbound_message=outbound_message,
        status="pending",
    )
    log_message_event(
        db,
        message=outbound_message,
        event_type="reply_generated",
        payload={
            "complaint_id": str(complaint.id),
            "ticket_id": complaint.ticket_id,
            "channel": channel,
            "conversation_id": outbound_message.raw_payload.get("conversation_id"),
        },
    )
    connection = _resolve_connection(db, inbound_message, complaint)
    if connection is None:
        logger.warning("No active %s connection found for complaint %s", channel, complaint.id)
        handle_failed_send(
            db,
            message=outbound_message,
            error="No active channel connection found",
            commit=False,
        )
        if allow_retry_enqueue:
            db.flush()
        return {"sent": False, "channels": []}

    try:
        if channel == "gmail":
            from app.integrations.gmail import send_gmail_reply

            send_result = send_gmail_reply(
                connection=connection,
                to_email=complaint.customer_email or (inbound_message.sender_id if inbound_message else ""),
                subject=f"Re: Support Ticket {complaint.ticket_id}",
                body=reply_text,
                thread_id=inbound_message.external_thread_id if inbound_message else None,
                references=inbound_message.external_message_id if inbound_message else None,
            )
            external_message_id = send_result["id"]
            external_thread_id = send_result.get("threadId") or (inbound_message.external_thread_id if inbound_message else None)
            provider_payload = {"provider_response": send_result}
        elif channel == "email":
            from app.integrations.email import send_email

            send_result = send_email(
                to_email=complaint.customer_email or (inbound_message.sender_id if inbound_message else ""),
                subject=f"Re: Support Ticket {complaint.ticket_id}",
                body=reply_text,
                in_reply_to=inbound_message.external_message_id if inbound_message else None,
                references=inbound_message.external_message_id if inbound_message else None,
                include_metadata=True,
            )
            if not send_result.get("sent"):
                raise RuntimeError("SMTP delivery unavailable")
            external_message_id = str(send_result.get("message_id") or f"email-outbound-{uuid.uuid4()}")
            external_thread_id = inbound_message.external_thread_id if inbound_message else complaint.thread_id
            provider_payload = {"provider_response": send_result}
        else:
            from app.integrations.whatsapp import send_whatsapp_text_message

            send_result = send_whatsapp_text_message(
                connection=connection,
                to_phone=complaint.customer_phone or (inbound_message.sender_id if inbound_message else ""),
                body=reply_text,
            )
            external_message_id = send_result["messages"][0]["id"]
            external_thread_id = inbound_message.external_thread_id if inbound_message else complaint.customer_phone
            provider_payload = {"provider_response": send_result}

        outbound_message = _mark_outbound_sent(
            db,
            outbound_message=outbound_message,
            external_message_id=external_message_id,
            external_thread_id=external_thread_id,
            sender_id=connection.email_address if isinstance(connection, Inbox) else connection.account_identifier,
            sender_name=client.name if client else "SynapFlow",
            raw_payload={
                "inbox_id" if isinstance(connection, Inbox) else "connection_id": str(connection.id),
                **provider_payload,
            },
        )
        log_message_event(
            db,
            message=outbound_message,
            event_type="reply_sent",
            payload={
                "complaint_id": str(complaint.id),
                "ticket_id": complaint.ticket_id,
                "channel": channel,
                "external_message_id": external_message_id,
            },
        )
        log_event(
            db,
            complaint.client_id,
            "channel_reply_sent",
            {
                "complaint_id": str(complaint.id),
                "ticket_id": complaint.ticket_id,
                "channel": channel,
                "external_message_id": external_message_id,
            },
        )
        return {"sent": True, "channels": [channel]}
    except Exception as exc:
        logger.exception("Failed to send %s reply for complaint %s: %s", channel, complaint.id, exc)
        handle_failed_send(
            db,
            message=outbound_message,
            error=str(exc),
            commit=False,
        )
        log_event(
            db,
            complaint.client_id,
            "channel_reply_failed",
            {
                "complaint_id": str(complaint.id),
                "ticket_id": complaint.ticket_id,
                "channel": channel,
                "error": str(exc),
            },
        )
        return {"sent": False, "channels": []}


def retry_unified_message_send(db: Session, message: UnifiedMessage) -> bool:
    complaint_id = (message.raw_payload or {}).get("complaint_id")
    if not complaint_id:
        raise ValueError("Retry message is missing complaint_id")
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if complaint is None:
        raise ValueError("Complaint not found for outbound retry")
    client = db.query(Client).filter(Client.id == complaint.client_id).first()
    result = send_reply_via_original_channel(
        db,
        complaint,
        client,
        message.message_text or "",
        allow_retry_enqueue=False,
        outbound_message=message,
    )
    return bool(result["sent"])


def process_outbound_retry(payload: dict[str, Any]) -> None:
    db = SessionLocal()
    try:
        message = None
        if payload.get("message_id"):
            message = db.query(UnifiedMessage).filter(UnifiedMessage.id == payload.get("message_id")).first()
        elif payload.get("complaint_id"):
            message = (
                db.query(UnifiedMessage)
                .filter(
                    UnifiedMessage.direction == "outbound",
                    UnifiedMessage.status == "failed",
                    UnifiedMessage.raw_payload["complaint_id"].as_string() == str(payload.get("complaint_id")),
                )
                .order_by(UnifiedMessage.created_at.desc())
                .first()
            )
        if message is None:
            raise ValueError("Unified message not found for outbound retry")
        result = retry_unified_message_send(db, message)
        if not result:
            raise RuntimeError("Retry delivery did not succeed")
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
