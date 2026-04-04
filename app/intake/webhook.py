from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.billing.usage import can_process_ticket, track_ticket_usage
from app.billing.plans import PLANS
from app.dependencies.auth import require_api_key
from app.db.models import Client, Complaint
from app.db.session import get_db
from app.intelligence.classifier import classify_message, summarize_if_needed
from app.queue.simple_queue import queue_job
from app.middleware.feature_gate import has_feature_access
from app.services.action_executor import execute_action
from app.services.audit_logs import append_audit_log
from app.services.auto_reply_hardened import HardenedAutoReplyService
from app.services.assignment import assign_team
from app.services.customer_profile import CustomerProfileService
from app.services.event_logger import log_event
from app.services.rbi_compliance import RBIComplianceService
from app.services.sla_manager import SLAManager
from app.services.ticket_state_machine import TicketStateMachine
from app.services.sentiment import analyze_sentiment
from app.services.rules_engine import get_matching_rules
from app.utils.logging import get_logger
from app.utils.sanitize import sanitize_email, sanitize_message, sanitize_phone
from app.utils.ticket import generate_thread_id, generate_ticket_id
from app.workflow.dispatcher import dispatch_action
from app.workflow.rule_engine import decide_action

router = APIRouter(prefix="/webhook", tags=["webhook"])
logger = get_logger(__name__)


def _fallback_sentiment_details(raw_score: float | int | None) -> dict:
    score = float(raw_score or 0.0)
    if score <= -0.6:
        return {"score": 5, "label": "furious", "indicators": []}
    if score <= -0.25:
        return {"score": 4, "label": "angry", "indicators": []}
    if score < 0.15:
        return {"score": 3, "label": "frustrated", "indicators": []}
    if score < 0.45:
        return {"score": 2, "label": "upset", "indicators": []}
    return {"score": 1, "label": "calm", "indicators": []}


class ComplaintRequest(BaseModel):
    message: str = Field(..., max_length=10000)
    source: str = Field(default="api", min_length=1, max_length=50)
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None
    ticket_id: Optional[str] = None


class EmailWebhookRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(..., alias="from")
    subject: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)


class WhatsAppWebhookRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(..., alias="From")
    body: str = Field(..., alias="Body", min_length=1)


def _process_complaint_for_client(
    db: Session,
    client: Client,
    message: str,
    source: str,
    customer_email: Optional[str],
    customer_phone: Optional[str],
    incoming_ticket_id: Optional[str] = None,
    return_complaint: bool = False,
) -> str | Complaint:
    # Single unified AI classification call (Gemini - free tier)
    classification = classify_message(message)
    summary = summarize_if_needed(message, classification)

    intent = classification["intent"]
    recommended_action = classification["recommended_action"]
    confidence = classification["confidence"]
    priority = classification["priority"]
    category = classification["category"]
    sentiment_score = classification["sentiment"]
    urgency = classification["urgency_score"]
    assigned_team = assign_team(category, intent)
    plan = PLANS.get(client.plan_id, PLANS["starter"])
    sentiment_details = _fallback_sentiment_details(sentiment_score)
    if plan.get("feature_flags", {}).get("sentiment_analysis"):
        sentiment_details = {
            **sentiment_details,
            **analyze_sentiment(summary or message),
        }

    # Decide final workflow action (ESCALATE_HIGH or AUTO_REPLY)
    _ACTION_MAP = {
        "escalate": "ESCALATE_HIGH",
        "notify_sales": "NOTIFY_SALES",
        "support_ticket": "AUTO_REPLY",
        "auto_reply": "AUTO_REPLY",
        "product_feedback": "PRODUCT_FEEDBACK",
    }
    action = _ACTION_MAP.get(recommended_action) or decide_action(
        category=category,
        sentiment=sentiment_score,
        urgency=urgency,
    )
    ticket_id = incoming_ticket_id or generate_ticket_id()
    thread_id = generate_thread_id()

    complaint = Complaint(
        client_id=client.id,
        summary=summary,
        source=source or "api",
        customer_email=customer_email,
        customer_phone=customer_phone,
        intent=intent,
        recommended_action=recommended_action,
        confidence=confidence,
        priority=priority,
        category=category,
        sentiment=sentiment_score,
        sentiment_score=sentiment_details.get("score"),
        sentiment_label=sentiment_details.get("label"),
        sentiment_indicators=sentiment_details.get("indicators"),
        urgency_score=urgency,
        assigned_team=assigned_team,
        assigned_to=assigned_team,
        ticket_id=ticket_id,
        thread_id=thread_id,
        status=action,
        state="new",
    )
    db.add(complaint)
    db.flush()
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
    CustomerProfileService(db).sync_customer_for_complaint(
        complaint,
        interaction_type="ticket",
        interaction_channel=source or "api",
        commit=False,
    )
    TicketStateMachine(db).ensure_ticket_number(complaint, commit=False)
    SLAManager(db).refresh_ticket_deadline(complaint, commit=False)
    TicketStateMachine(db).sync_from_legacy(
        complaint,
        transitioned_by=client.name,
        reason="Initial ticket classification",
        metadata={"source": source or "api"},
        commit=False,
    )

    rules = get_matching_rules(db, client.id, classification)

    for rule in rules:
        execute_action(rule, complaint, client)

    SLAManager(db).refresh_ticket_deadline(complaint, commit=False)
    TicketStateMachine(db).sync_from_legacy(
        complaint,
        transitioned_by=client.name,
        reason="Complaint ingestion workflow",
        metadata={"source": source or "api"},
        commit=False,
    )

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
        RBIComplianceService(db).register_rbi_complaint(complaint, commit=False)

    queue_entry = HardenedAutoReplyService(db).generate_and_queue_reply(complaint, commit=False)
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

    if return_complaint:
        return complaint
    return action


def _enforce_usage_limit(client: Client) -> None:
    if not can_process_ticket(client.id):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "message": "Monthly ticket limit exceeded",
                "upgrade_url": "/portal/upgrade",
            },
        )


@router.post("/complaint")
def process_complaint(
    payload: ComplaintRequest,
    client: Client = Depends(require_api_key),
    db: Session = Depends(get_db),
) -> dict:
    try:
        # Sanitize inputs
        message = sanitize_message(payload.message)
        customer_email = sanitize_email(payload.customer_email)
        customer_phone = sanitize_phone(payload.customer_phone)

        if not message:
            raise HTTPException(400, "Message cannot be empty")

        _enforce_usage_limit(client)

        # Create complaint immediately with minimal processing
        ticket_id = payload.ticket_id or generate_ticket_id()
        thread_id = generate_thread_id()

        complaint = Complaint(
            client_id=client.id,
            summary=message[:200],  # Temporary summary
            source=payload.source or "api",
            customer_email=customer_email,
            customer_phone=customer_phone,
            ticket_id=ticket_id,
            thread_id=thread_id,
            status="PROCESSING",
            category="general",  # Will be updated by AI
            sentiment=0.0,
            urgency_score=0.3,
            priority=2,
            state="new",
        )
        db.add(complaint)
        db.flush()
        CustomerProfileService(db).sync_customer_for_complaint(
            complaint,
            interaction_type="ticket",
            interaction_channel=payload.source or "api",
            commit=False,
        )
        TicketStateMachine(db).ensure_ticket_number(complaint, commit=False)
        SLAManager(db).refresh_ticket_deadline(complaint, commit=False)
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
        db.commit()

        # Queue AI processing in background
        queue_job(db, "process_complaint_ai", {
            "complaint_id": str(complaint.id),
            "message": message,
        })

        # Track usage
        track_ticket_usage(client.id)

        # Return immediately
        return {
            "status": "queued",
            "ticket_id": ticket_id,
            "message": "Complaint received and processing started",
        }

    except HTTPException:
        raise
    except OperationalError:
        db.rollback()
        logger.error("Database unavailable while processing complaint.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporarily unavailable",
        )
    except Exception as exc:
        db.rollback()
        logger.exception("Complaint processing failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Complaint processing failed",
        ) from exc


@router.post("/email")
def process_email_webhook(
    payload: EmailWebhookRequest,
    client: Client = Depends(require_api_key),
    db: Session = Depends(get_db),
) -> dict:
    try:
        _enforce_usage_limit(client)
        from app.services.unified_ingestion import IncomingMessage, process_incoming_message
        incoming_message = IncomingMessage(
            client_id=client.id,
            channel="email",
            external_message_id=payload.subject,  # Use subject as unique id for demo; replace as needed
            sender_id=payload.from_,
            sender_name=None,
            message_text=f"{payload.subject} {payload.text}".strip(),
            direction="inbound",
            status="received",
            raw_payload=payload.model_dump() if hasattr(payload, 'model_dump') else dict(payload),
        )
        result = process_incoming_message(db, incoming_message)
        db.commit()
        track_ticket_usage(client.id)
        action = result
    except HTTPException:
        raise
    except OperationalError:
        db.rollback()
        logger.error("Database unavailable while processing email webhook.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporarily unavailable",
        )
    except Exception as exc:
        db.rollback()
        logger.exception("Email webhook processing failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Complaint processing failed",
        ) from exc

    return {"status": "processed", "action": action}


@router.post("/whatsapp")
def process_whatsapp_webhook(
    payload: WhatsAppWebhookRequest,
    client: Client = Depends(require_api_key),
    db: Session = Depends(get_db),
) -> dict:
    try:
        _enforce_usage_limit(client)
        from app.services.unified_ingestion import IncomingMessage, process_incoming_message
        incoming_message = IncomingMessage(
            client_id=client.id,
            channel="whatsapp",
            external_message_id=payload.body[:32],  # Use body hash/part as unique id for demo
            sender_id=payload.from_,
            sender_name=None,
            message_text=payload.body,
            direction="inbound",
            status="received",
            raw_payload=payload.model_dump() if hasattr(payload, 'model_dump') else dict(payload),
        )
        result = process_incoming_message(db, incoming_message)
        db.commit()
        track_ticket_usage(client.id)
        action = result
    except HTTPException:
        raise
    except OperationalError:
        db.rollback()
        logger.error("Database unavailable while processing whatsapp webhook.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporarily unavailable",
        )
    except Exception as exc:
        db.rollback()
        logger.exception("WhatsApp webhook processing failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Complaint processing failed",
        ) from exc

    return {"status": "processed", "action": action}
