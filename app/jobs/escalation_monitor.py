"""
Background job for processing escalations.
Runs periodically to check open tickets and escalate as needed.
"""

import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models import Client, JobQueue
from app.services.escalation_engine import EscalationEngine

logger = logging.getLogger(__name__)


def process_escalations_monitor() -> dict:
    """
    Monitor and process pending escalations for all RBI-regulated clients.
    
    This job:
    1. Queries all active RBI clients
    2. For each client, identifies tickets needing escalation
    3. Performs auto-escalation based on time thresholds
    4. Logs all escalation activities
    
    Returns:
        Statistics about escalations processed
    """
    db = SessionLocal()
    total_stats = {
        "clients_processed": 0,
        "total_checked": 0,
        "total_escalated": 0,
        "total_errors": 0,
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        # Get all RBI-regulated clients
        rbi_clients = (
            db.query(Client)
            .filter(
                Client.is_rbi_regulated == True,
            )
            .all()
        )

        logger.info(f"Starting escalation monitoring for {len(rbi_clients)} RBI clients")

        for client in rbi_clients:
            try:
                engine = EscalationEngine(db)
                stats = engine.process_pending_escalations(client.id)

                logger.info(
                    f"Client {client.id} ({client.name}): "
                    f"checked={stats['checked']}, "
                    f"escalated={stats['escalated']}, "
                    f"errors={stats['errors']}"
                )

                total_stats["clients_processed"] += 1
                total_stats["total_checked"] += stats["checked"]
                total_stats["total_escalated"] += stats["escalated"]
                total_stats["total_errors"] += stats["errors"]

                # Log escalations if any
                if stats["escalations"]:
                    logger.info(f"Escalations: {stats['escalations']}")

            except Exception as e:
                logger.error(f"Error processing escalations for client {client.id}: {e}", exc_info=True)
                total_stats["total_errors"] += 1

        logger.info(f"Escalation monitoring completed: {total_stats}")
        return total_stats

    finally:
        db.close()


def process_escalation_job(payload: dict) -> dict:
    """
    Process a single escalation job from the queue.
    
    Payload structure:
    {
        "ticket_id": "uuid-string",
        "reason": "sla_breach|tat_breach|time_threshold",
        "escalated_by": "system|user@email.com",
        "metadata": {...}
    }
    """
    db = SessionLocal()
    
    try:
        from uuid import UUID
        from app.db.models import Complaint
        from app.services.escalation_engine import EscalationTriggerReason
        
        ticket_id = UUID(payload.get("ticket_id"))
        reason_str = payload.get("reason", "time_threshold")
        escalated_by = payload.get("escalated_by", "system")
        metadata = payload.get("metadata", {})
        
        # Validate reason
        try:
            reason = EscalationTriggerReason[reason_str.upper()]
        except KeyError:
            reason = EscalationTriggerReason.TIME_THRESHOLD
        
        complaint = db.query(Complaint).filter(Complaint.id == ticket_id).first()
        if not complaint:
            return {"success": False, "error": f"Complaint {ticket_id} not found"}
        
        engine = EscalationEngine(db)
        escalation = engine.escalate(
            complaint,
            reason=reason,
            escalated_by=escalated_by,
            metadata=metadata,
        )
        
        logger.info(f"Escalated ticket {ticket_id} to level {escalation.level}")
        
        return {
            "success": True,
            "escalation_id": str(escalation.id),
            "level": escalation.level,
            "escalated_to": escalation.escalated_to,
        }
        
    except Exception as e:
        logger.error(f"Error processing escalation job: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
    finally:
        db.close()


def queue_escalation_job(
    db: Session,
    ticket_id: str,
    reason: str = "time_threshold",
    escalated_by: str = "system",
    metadata: dict = None,
    immediate: bool = False,
) -> JobQueue:
    """
    Queue an escalation job for processing.
    
    Args:
        db: Database session
        ticket_id: UUID of ticket to escalate
        reason: Escalation reason
        escalated_by: Who triggered it
        metadata: Additional context
        immediate: If True, process immediately instead of queueing
    
    Returns:
        Created JobQueue record
    """
    payload = {
        "ticket_id": str(ticket_id),
        "reason": reason,
        "escalated_by": escalated_by,
        "metadata": metadata or {},
    }
    
    if immediate:
        # Process immediately
        result = process_escalation_job(payload)
        logger.info(f"Immediate escalation result: {result}")
    
    # Queue for async processing
    job = JobQueue(
        job_type="process_escalation",
        payload=payload,
        status="queued",
    )
    db.add(job)
    db.commit()
    
    return job
