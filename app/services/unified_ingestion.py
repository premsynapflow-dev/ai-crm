from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.billing.usage import can_process_ticket, track_ticket_usage
from app.db.models import Client, Complaint, Conversation, UnifiedMessage
from app.services.conversation_threads import find_complaint_for_conversation
from app.services.event_logger import log_event
from app.services.message_events import log_message_event
from app.services.routing_service import RoutingService
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


def _mark_message_processed(
    unified_message: UnifiedMessage,
    *,
    complaint_id: str | None,
    ticket_id: str | None,
    complaint_thread_id: str | None,
    conversation_id: str,
    team_id: str | None = None,
    assigned_team: str | None = None,
    assigned_user: str | None = None,
    assigned_user_id: str | None = None,
    classification_category: str | None = None,
    status: str = "processed",
) -> None:
    unified_message.status = status
    unified_message.retry_count = 0
    unified_message.last_error = None
    unified_message.next_retry_at = None
    payload_updates = {
        "message_id": str(unified_message.id),
        "conversation_id": conversation_id,
    }
    if complaint_id is not None:
        payload_updates["complaint_id"] = complaint_id
    if ticket_id is not None:
        payload_updates["ticket_id"] = ticket_id
    if complaint_thread_id is not None:
        payload_updates["complaint_thread_id"] = complaint_thread_id
    if team_id is not None:
        payload_updates["team_id"] = team_id
    if assigned_team is not None:
        payload_updates["assigned_team"] = assigned_team
    if assigned_user is not None:
        payload_updates["assigned_user"] = assigned_user
    if assigned_user_id is not None:
        payload_updates["assigned_user_id"] = assigned_user_id
    if classification_category is not None:
        payload_updates["classification_category"] = classification_category
    unified_message.raw_payload = {
        **(unified_message.raw_payload or {}),
        **payload_updates,
    }


def process_incoming_message(db: Session, message: IncomingMessage) -> dict[str, Any]:
    existing = (
        db.query(UnifiedMessage)
        .filter(
            UnifiedMessage.channel == message.channel,
            UnifiedMessage.external_message_id == message.external_message_id,
        )
        .first()
    )
    reprocessing_quota_blocked = False
    if existing is not None:
        if existing.status == "quota_blocked" and message.direction == "inbound" and can_process_ticket(existing.client_id):
            reprocessing_quota_blocked = True
        else:
            return {
                "status": "duplicate",
                "message_id": str(existing.id),
                "external_message_id": existing.external_message_id,
            }

    conversation = _resolve_message_conversation(db, message)
    if reprocessing_quota_blocked and existing is not None:
        unified_message = existing
        unified_message.external_thread_id = conversation.external_thread_id
        unified_message.sender_id = message.sender_id
        unified_message.sender_name = message.sender_name
        unified_message.message_text = message.message_text
        unified_message.attachments = message.attachments
        unified_message.timestamp = _normalize_timestamp(message.timestamp)
        unified_message.status = message.status
        unified_message.raw_payload = {
            **(unified_message.raw_payload or {}),
            **message.raw_payload,
            "conversation_id": str(conversation.id),
        }
        db.flush()
    else:
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

    if reprocessing_quota_blocked:
        log_message_event(
            db,
            message=unified_message,
            event_type="message_reprocessed",
            payload={
                "outcome": "quota_recovered",
                "conversation_id": str(conversation.id),
                "external_message_id": message.external_message_id,
            },
        )
    else:
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

    existing_complaint = find_complaint_for_conversation(
        db,
        client_id=client.id,
        channel=message.channel,
        external_thread_id=conversation.external_thread_id,
    )

    if existing_complaint is None and not can_process_ticket(client.id):
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
    # Unify: Use the same logic as _process_complaint_for_client, but inline here to avoid duplicate logic
    from app.services.customer_profile import CustomerProfileService
    from app.services.ticket_state_machine import TicketStateMachine
    from app.services.sla_manager import SLAManager
    from app.services.auto_reply_hardened import HardenedAutoReplyService
    from app.services.rbi_compliance import RBIComplianceService
    from app.services.audit_logs import append_audit_log
    from app.services.classification_service import build_client_classification_config, classification_to_action
    from app.middleware.feature_gate import has_feature_access
    from app.intelligence.classifier import classify_message, summarize_if_needed
    from app.utils.ticket import generate_ticket_id
    from app.workflow.dispatcher import dispatch_action
    from app.services.rules_engine import get_matching_rules
    # ---
    client_config = build_client_classification_config(db, client)
    classification = classify_message(message.message_text, client_config)
    summary = summarize_if_needed(message.message_text, classification)
    intent = classification["intent"]
    recommended_action = classification["recommended_action"]
    confidence = classification["confidence"]
    priority = classification["priority"]
    category = classification["category"]
    sentiment_score = classification["sentiment"]
    urgency = classification["urgency_score"]
    spam_filtered = str(category or "").strip().lower() == "spam" and existing_complaint is None

    if spam_filtered:
        _mark_message_processed(
            unified_message,
            complaint_id=None,
            ticket_id=None,
            complaint_thread_id=None,
            conversation_id=str(conversation.id),
            classification_category=category,
            status="spam_filtered",
        )
        conversation.last_message_at = unified_message.timestamp
        log_message_event(
            db,
            message=unified_message,
            event_type="message_processed",
            payload={
                "outcome": "spam_filtered",
                "message_id": str(unified_message.id),
                "conversation_id": str(conversation.id),
                "category": category,
            },
        )
        db.flush()
        return {
            "status": "spam_filtered",
            "message_id": str(unified_message.id),
            "conversation_id": str(conversation.id),
        }

    action = classification_to_action(classification)
    is_new_complaint = existing_complaint is None
    complaint = existing_complaint or Complaint(
        client_id=client.id,
        ticket_id=generate_ticket_id(),
        thread_id=conversation.external_thread_id,
        source=message.channel or "api",
        state="new",
    )
    if is_new_complaint:
        db.add(complaint)

    was_resolved = complaint.resolution_status == "resolved"
    previous_reply_sent_at = complaint.ai_reply_sent_at

    complaint.thread_id = conversation.external_thread_id
    complaint.summary = summary
    complaint.source = message.channel or complaint.source or "api"
    complaint.customer_email = customer_email or complaint.customer_email
    complaint.customer_phone = customer_phone or complaint.customer_phone
    complaint.intent = intent
    complaint.recommended_action = recommended_action
    complaint.confidence = confidence
    complaint.priority = priority
    complaint.category = category
    complaint.sentiment = sentiment_score
    complaint.urgency_score = urgency
    complaint.status = action
    complaint.resolution_status = "open"
    complaint.resolved_at = None
    db.flush()
    routing_result = RoutingService(db).route_ticket(
        complaint,
        classification,
        commit=False,
        routed_by=client.name or "system:routing",
    )
    if routing_result.assigned_user_id is not None:
        conversation.assigned_to = routing_result.assigned_user_id

    if is_new_complaint:
        append_audit_log(
            db,
            entity_type="ticket",
            entity_id=complaint.id,
            action="ticket_created",
            performed_by=client.name,
            old_value=None,
            new_value={
                "ticket_id": complaint.ticket_id,
                "status": complaint.status,
                "resolution_status": complaint.resolution_status,
                "source": complaint.source,
                "rbi_category_code": complaint.rbi_category_code,
                "tat_status": complaint.tat_status,
            },
        )
    else:
        if was_resolved:
            complaint.reopened_count = int(complaint.reopened_count or 0) + 1
            complaint.last_reopened_at = datetime.now(timezone.utc)
            log_event(
                db,
                client.id,
                "complaint_reopened",
                {
                    "ticket_id": complaint.ticket_id,
                    "complaint_id": str(complaint.id),
                    "summary": complaint.summary,
                },
            )
        append_audit_log(
            db,
            entity_type="ticket",
            entity_id=complaint.id,
            action="ticket_customer_reply_received",
            performed_by=message.sender_id or message.sender_name or "customer",
            old_value=None,
            new_value={
                "ticket_id": complaint.ticket_id,
                "status": complaint.status,
                "resolution_status": complaint.resolution_status,
                "thread_id": complaint.thread_id,
            },
        )
        if previous_reply_sent_at is not None:
            response_gap_seconds = int(max((unified_message.timestamp - previous_reply_sent_at).total_seconds(), 0))
            HardenedAutoReplyService(db).record_feedback(
                complaint,
                customer_responded=True,
                customer_response_sentiment=sentiment_score,
                time_to_customer_response_seconds=response_gap_seconds,
                commit=False,
            )
    CustomerProfileService(db).sync_customer_for_complaint(
        complaint,
        interaction_type="ticket",
        interaction_channel=message.channel or "api",
        commit=False,
    )
    TicketStateMachine(db).ensure_ticket_number(complaint, commit=False)
    SLAManager(db).refresh_ticket_deadline(complaint, commit=False)
    TicketStateMachine(db).sync_from_legacy(
        complaint,
        transitioned_by=client.name,
        reason="Initial ticket classification",
        metadata={"source": message.channel or "api"},
        commit=False,
    )
    rules = get_matching_rules(db, client.id, classification)
    for rule in rules:
        from app.services.action_executor import execute_action
        execute_action(rule, complaint, client)
    SLAManager(db).refresh_ticket_deadline(complaint, commit=False)
    TicketStateMachine(db).sync_from_legacy(
        complaint,
        transitioned_by=client.name,
        reason="Complaint ingestion workflow",
        metadata={"source": message.channel or "api"},
        commit=False,
    )
    if is_new_complaint:
        log_event(
            db,
            client.id,
            "complaint_received",
            {
                "ticket_id": complaint.ticket_id,
                "complaint_id": str(complaint.id),
                "summary": complaint.summary,
                "category": complaint.category,
                "priority": complaint.priority,
                "source": complaint.source,
                "status": complaint.status,
            },
        )
    if client.is_rbi_regulated and has_feature_access(client, "rbi_compliance", db=db):
        if complaint.rbi_complaint is None:
            RBIComplianceService(db).register_rbi_complaint(complaint, commit=False)
        else:
            RBIComplianceService(db).sync_from_complaint(complaint, commit=False)
    queue_entry = HardenedAutoReplyService(db).generate_and_queue_reply(
        complaint,
        custom_config=client_config,
        commit=False,
    )
    if queue_entry.status in {"pending", "rejected"}:
        log_event(
            db,
            client.id,
            "ai_reply_queued_for_review" if queue_entry.status == "pending" else "ai_reply_rejected",
            {
                "ticket_id": complaint.ticket_id,
                "complaint_id": str(complaint.id),
                "summary": complaint.ai_reply,
                "confidence": complaint.ai_reply_confidence,
                "queue_status": queue_entry.status,
            },
        )
    dispatch_action(
        action=action,
        client_name=client.name,
        complaint_id=str(complaint.id),
        summary=summary,
        category=category,
        sentiment=sentiment_score,
        urgency=urgency,
        intent=intent,
        recommended_action=recommended_action,
        client_slack_webhook=client.slack_webhook_url,
        customer_email=customer_email,
        customer_phone=customer_phone,
    )
    _mark_message_processed(
        unified_message,
        complaint_id=str(complaint.id),
        ticket_id=complaint.ticket_id,
        complaint_thread_id=complaint.thread_id,
        conversation_id=str(conversation.id),
        team_id=str(routing_result.team_id) if routing_result.team_id else None,
        assigned_team=routing_result.team_name,
        assigned_user=routing_result.assigned_user,
        assigned_user_id=str(routing_result.assigned_user_id) if routing_result.assigned_user_id else None,
        classification_category=category,
    )
    conversation.last_message_at = unified_message.timestamp
    if is_new_complaint:
        track_ticket_usage(client.id)

    log_message_event(
        db,
        message=unified_message,
        event_type="message_processed",
            payload={
                "conversation_id": str(conversation.id),
                "message_id": str(unified_message.id),
                "complaint_id": str(complaint.id),
                "ticket_id": complaint.ticket_id,
                "team_id": str(routing_result.team_id) if routing_result.team_id else None,
                "assigned_team": routing_result.team_name,
                "assigned_user": routing_result.assigned_user,
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
