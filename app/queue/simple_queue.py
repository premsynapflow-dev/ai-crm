import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict

from app.db.models import JobQueue, Complaint, Client
from app.db.session import SessionLocal
from app.integrations.email import send_email
from app.integrations.slack import send_slack_alert
from app.intelligence.classifier import classify_message_async
from app.intelligence.prompt_builder import get_prompt_config_for_client
from app.intelligence.reply_engine import generate_ai_reply_async
from app.services.customer_history import get_customer_memory
from app.replies.send_reply import send_complaint_reply
from app.services.response_tracking import mark_first_response_by_id
from app.utils.logging import get_logger

logger = get_logger(__name__)


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


def process_sync_integration_job(payload: Dict):
    # Placeholder for integration sync job
    return


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
        complaint.intent = classification["intent"]
        complaint.category = classification["category"]
        complaint.sentiment = classification["sentiment"]
        complaint.urgency_score = classification["urgency_score"]
        complaint.priority = classification["priority"]
        complaint.recommended_action = classification["recommended_action"]
        complaint.confidence = classification["confidence"]
        complaint.summary = classification["summary"]
        
        # Generate AI reply
        customer_history = get_customer_memory(
            db, 
            complaint.customer_email, 
            limit=5
        )
        reply_payload = await generate_ai_reply_async(
            complaint, 
            customer_history,
            custom_config  # Pass custom config
        )
        
        complaint.ai_reply = reply_payload["reply_text"]
        complaint.ai_reply_confidence = reply_payload["confidence_score"]
        
        # Auto-send if confidence high
        if reply_payload["confidence_score"] > 0.75:
            send_result = send_complaint_reply(
                db=db,
                complaint=complaint,
                client=client,
                reply_text=complaint.ai_reply,
            )
            if send_result.get("sent"):
                complaint.ai_reply_status = "sent"
            else:
                complaint.ai_reply_status = "agent_review"
        else:
            complaint.ai_reply_status = "agent_review"
        
        complaint.status = "PROCESSED"
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
