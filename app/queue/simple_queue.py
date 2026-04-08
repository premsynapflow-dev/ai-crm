import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict

from app.db.models import ChannelConnection, JobQueue, Complaint, Client
from app.db.session import SessionLocal
from app.inboxes.models import Inbox
from app.integrations.email import send_email
from app.integrations.slack import send_slack_alert
from app.billing.plans import PLANS
from app.intelligence.classifier import classify_message_async
from app.intelligence.prompt_builder import get_prompt_config_for_client
from app.middleware.feature_gate import has_feature_access
from app.services.assignment import assign_team
from app.services.auto_reply_hardened import HardenedAutoReplyService
from app.services.channel_router import process_outbound_retry
from app.services.customer_profile import CustomerProfileService
from app.services.rbi_compliance import RBIComplianceService
from app.services.sla_manager import SLAManager
from app.services.sentiment import analyze_sentiment
from app.services.ticket_state_machine import TicketStateMachine
from app.services.response_tracking import mark_first_response_by_id
from app.utils.logging import get_logger

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


def enqueue_job(job_type, payload, scheduled_for=None):
    db = SessionLocal()
    try:
        job = JobQueue(
            job_type=job_type,
            payload=payload,
            scheduled_for=scheduled_for,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def queue_job(db, job_type, payload, scheduled_for=None):
    """Queue job using an existing DB session"""
    job = JobQueue(
        job_type=job_type,
        payload=payload,
        scheduled_for=scheduled_for,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def process_send_email_job(payload: Dict):
    send_email(
        to_email=payload.get("to_email"),
        subject=payload.get("subject", "SynapFlow Notification"),
        body=payload.get("body", ""),
    )
    complaint_id = payload.get("complaint_id")
    if complaint_id:
        db = SessionLocal()
        try:
            if mark_first_response_by_id(db, complaint_id):
                db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()


def process_send_slack_job(payload: Dict):
    send_slack_alert(
        payload.get("text", ""),
        webhook_url=payload.get("webhook_url"),
    )


def _legacy_connection_to_inbox(db, connection: ChannelConnection) -> Inbox | None:
    metadata = connection.metadata_json or {}
    if connection.channel_type == "gmail":
        email_address = (connection.account_identifier or metadata.get("email_address") or "").strip()
        if not email_address:
            return None
        provider_type = "gmail"
    elif connection.channel_type == "email" and metadata.get("mode") == "imap":
        email_address = (
            metadata.get("email_address")
            or connection.account_identifier
            or metadata.get("imap_username")
            or ""
        ).strip()
        if not email_address or not metadata.get("imap_host") or not connection.access_token:
            return None
        provider_type = "imap"
    else:
        return None

    inbox = (
        db.query(Inbox)
        .filter(
            Inbox.tenant_id == connection.client_id,
            Inbox.email_address == email_address,
        )
        .first()
    )
    if inbox is None:
        inbox = Inbox(
            tenant_id=connection.client_id,
            email_address=email_address,
            provider_type=provider_type,
        )
        db.add(inbox)

    inbox.provider_type = provider_type
    inbox.is_active = connection.status == "active"
    inbox.metadata_json = {
        **(inbox.metadata_json or {}),
        **metadata,
        "legacy_connection_id": str(connection.id),
    }

    if provider_type == "gmail":
        inbox.access_token = connection.access_token
        inbox.refresh_token = connection.refresh_token
        inbox.token_expiry = connection.token_expiry
        inbox.imap_host = None
        inbox.imap_port = None
        inbox.imap_username = None
        inbox.imap_password = None
    else:
        inbox.access_token = None
        inbox.refresh_token = None
        inbox.token_expiry = None
        inbox.imap_host = metadata.get("imap_host")
        inbox.imap_port = int(metadata.get("imap_port") or 993)
        inbox.imap_username = metadata.get("imap_username") or email_address
        inbox.imap_password = connection.access_token
        inbox.imap_use_ssl = bool(metadata.get("imap_use_ssl", inbox.imap_port == 993))

    db.flush()
    logger.info(
        "Routed legacy %s connection=%s through inbox=%s",
        connection.channel_type,
        connection.id,
        inbox.id,
    )
    return inbox


def process_sync_integration_job(payload: Dict):
    db = SessionLocal()
    try:
        from app.services.inbox_poller import poll_inbox

        inbox = None
        if payload.get("inbox_id"):
            inbox = db.query(Inbox).filter(Inbox.id == payload.get("inbox_id")).first()
            if inbox is None:
                logger.warning("Inbox sync skipped; inbox %s not found", payload.get("inbox_id"))
                return
        elif payload.get("connection_id"):
            connection = db.query(ChannelConnection).filter(ChannelConnection.id == payload.get("connection_id")).first()
            if connection is None:
                logger.warning("Integration sync skipped; connection %s not found", payload.get("connection_id"))
                return
            inbox = _legacy_connection_to_inbox(db, connection)

        if inbox is None:
            logger.warning("Integration sync skipped; no inbox source in payload=%s", payload)
            return

        result = poll_inbox(db, inbox)
        db.commit()
        logger.info(
            "Inbox sync job complete inbox=%s provider=%s fetched=%s processed=%s duplicates=%s",
            result["inbox_id"],
            result["provider"],
            result["fetched"],
            result["processed"],
            result["duplicates"],
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def process_send_channel_message_job(payload: Dict):
    process_outbound_retry(payload)


async def process_complaint_ai_job(payload: Dict):
    """Background job: Run AI classification and reply generation"""
    db = SessionLocal()
    try:
        complaint_id = payload.get("complaint_id")
        message = payload.get("message")
        
        complaint = db.query(Complaint).filter(
            Complaint.id == complaint_id
        ).first()
        
        if not complaint:
            logger.error(f"Complaint {complaint_id} not found")
            return
        
        client = db.query(Client).filter(
            Client.id == complaint.client_id
        ).first()

        if not client:
            logger.error(f"Client {complaint.client_id} not found")
            return
        
        # NEW: Get custom prompt config for this client
        custom_config = get_prompt_config_for_client(client)
        
        # Run AI classification with custom config
        classification = await classify_message_async(message, custom_config)
        
        # Update complaint
        TicketStateMachine(db).ensure_ticket_number(complaint, commit=False)
        complaint.intent = classification["intent"]
        complaint.category = classification["category"]
        complaint.sentiment = classification["sentiment"]
        complaint.assigned_to = assign_team(complaint.category, complaint.intent)
        complaint.assigned_team = complaint.assigned_to
        complaint.urgency_score = classification["urgency_score"]
        complaint.priority = classification["priority"]
        complaint.recommended_action = classification["recommended_action"]
        complaint.confidence = classification["confidence"]
        complaint.summary = classification["summary"]
        sentiment_details = _fallback_sentiment_details(classification["sentiment"])
        if PLANS.get(client.plan_id, PLANS["starter"]).get("feature_flags", {}).get("sentiment_analysis"):
            sentiment_details = {
                **sentiment_details,
                **analyze_sentiment(complaint.summary or message),
            }
        complaint.sentiment_score = sentiment_details.get("score")
        complaint.sentiment_label = sentiment_details.get("label")
        complaint.sentiment_indicators = sentiment_details.get("indicators")
        
        # Generate AI reply
        CustomerProfileService(db).sync_customer_for_complaint(
            complaint,
            interaction_type="ticket",
            interaction_channel=complaint.source,
            commit=False,
        )

        if has_feature_access(client, "rbi_compliance", db=db):
            RBIComplianceService(db).register_rbi_complaint(complaint, commit=False)

        await HardenedAutoReplyService(db).generate_and_queue_reply_async(
            complaint,
            custom_config=custom_config,
            commit=False,
        )

        complaint.status = "PROCESSED"
        SLAManager(db).refresh_ticket_deadline(complaint, commit=False)
        TicketStateMachine(db).sync_from_legacy(
            complaint,
            transitioned_by=client.name,
            reason="Background AI processing completed",
            metadata={"job_type": "process_complaint_ai"},
            commit=False,
        )
        db.commit()
        
        logger.info(f"Processed complaint {complaint_id} in background (custom_prompt={custom_config is not None})")
        
    except Exception as e:
        logger.exception(f"Failed to process complaint AI job: {e}")
        db.rollback()
    finally:
        db.close()


# Register job handler
JOB_HANDLERS = {
    "send_email": process_send_email_job,
    "send_slack": process_send_slack_job,
    "send_channel_message": process_send_channel_message_job,
    "sync_integration": process_sync_integration_job,
    "process_complaint_ai": lambda p: asyncio.run(process_complaint_ai_job(p)),
}


def process_jobs() -> int:
    """Process pending jobs"""
    db = SessionLocal()
    try:
        jobs = db.query(JobQueue).filter(
            JobQueue.status == 'queued'
        ).limit(10).all()
        
        for job in jobs:
            try:
                job.status = 'processing'
                db.commit()

                handler = JOB_HANDLERS.get(job.job_type)
                if handler:
                    handler(job.payload)
                    job.status = 'completed'
                    job.processed_at = datetime.now(timezone.utc)
                else:
                    job.status = 'failed'
                    job.last_error = f"Unknown job type: {job.job_type}"

                db.commit()

            except Exception as e:
                job.retry_count += 1
                if job.retry_count >= 3:
                    job.status = 'failed'
                else:
                    job.status = 'queued'
                job.last_error = str(e)
                db.commit()
                logger.exception(f"Job {job.id} failed: {e}")
        
        return len(jobs)
    finally:
        db.close()
