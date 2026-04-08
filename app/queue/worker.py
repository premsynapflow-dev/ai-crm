from datetime import datetime, timedelta, timezone
import threading

from app.config import get_settings
from app.db.models import Client, Complaint, RBIComplaint
from app.db.session import SessionLocal
from app.analytics.customer_pulse import detect_complaint_spikes
from app.queue.simple_queue import process_jobs
from app.replies.send_reply import send_complaint_reply
from app.services.inbox_poller import poll_all_inboxes
from app.services.retry_service import process_retry_queue
from app.services.rbi_compliance import RBIComplianceService
from app.services.sla_manager import SLAManager
from app.services.ticket_state_machine import TicketStateMachine
from app.services.escalation_engine import EscalationEngine
from app.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()
_stop_event = threading.Event()
_worker_thread = None
_last_spike_check_at = None
_last_sla_check_at = None
_last_rbi_check_at = None
_last_rbi_report_check_at = None
_last_escalation_check_at = None
_last_inbox_poll_at = None
FOLLOW_UP_TEXT = "Just checking if your issue has been resolved."


def process_follow_up_automation():
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        follow_up_cutoff = now - timedelta(hours=24)
        resolve_cutoff = now - timedelta(hours=48)

        complaints_for_follow_up = (
            db.query(Complaint)
            .filter(
                Complaint.resolution_status == "open",
                Complaint.ai_reply_sent_at.isnot(None),
                Complaint.ai_reply_sent_at <= follow_up_cutoff,
                Complaint.ai_reply_status == "sent",
            )
            .all()
        )
        for complaint in complaints_for_follow_up:
            client = db.query(Client).filter(Client.id == complaint.client_id).first()
            send_complaint_reply(
                db=db,
                complaint=complaint,
                client=client,
                reply_text=FOLLOW_UP_TEXT,
                status_on_success="follow_up_sent",
            )

        complaints_to_resolve = (
            db.query(Complaint)
            .filter(
                Complaint.resolution_status == "open",
                Complaint.ai_reply_sent_at.isnot(None),
                Complaint.ai_reply_sent_at <= resolve_cutoff,
                Complaint.ai_reply_status == "follow_up_sent",
            )
            .all()
        )
        for complaint in complaints_to_resolve:
            complaint.resolution_status = "resolved"
            complaint.resolved_at = now
            complaint.status = "RESOLVED"
            TicketStateMachine(db).sync_from_legacy(
                complaint,
                transitioned_by="system",
                reason="Auto-resolved by follow-up worker",
                metadata={"source": "queue_worker"},
                commit=False,
            )

        db.commit()
        return len(complaints_for_follow_up) + len(complaints_to_resolve)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def process_sla_monitor():
    global _last_sla_check_at
    now = datetime.now(timezone.utc)
    interval = timedelta(minutes=max(1, settings.sla_monitor_interval_minutes))
    if _last_sla_check_at and now - _last_sla_check_at < interval:
        return 0

    db = SessionLocal()
    try:
        sla_manager = SLAManager(db)
        tickets = (
            db.query(Complaint)
            .filter(
                Complaint.resolved_at.is_(None),
                Complaint.sla_due_at.isnot(None),
            )
            .order_by(Complaint.sla_due_at.asc())
            .limit(500)
            .all()
        )
        updated = 0
        for ticket in tickets:
            old_status = ticket.sla_status
            new_status = sla_manager.update_sla_status(ticket)
            if new_status != old_status:
                updated += 1
        db.commit()
        _last_sla_check_at = now
        return updated
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def process_spike_detection():
    global _last_spike_check_at
    now = datetime.now(timezone.utc)
    if _last_spike_check_at and now - _last_spike_check_at < timedelta(hours=1):
        return 0

    db = SessionLocal()
    try:
        clients = db.query(Client).all()
        total_spikes = 0
        for client in clients:
            spikes = detect_complaint_spikes(db, client.id, send_alert=True)
            total_spikes += len(spikes)
        db.commit()
        _last_spike_check_at = now
        return total_spikes
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def process_rbi_tat_monitor():
    global _last_rbi_check_at
    now = datetime.now(timezone.utc)
    interval = timedelta(hours=1)
    if _last_rbi_check_at and now - _last_rbi_check_at < interval:
        return 0

    db = SessionLocal()
    try:
        service = RBIComplianceService(db)
        updated, escalated = service.process_tat_monitor(limit=500)
        db.commit()
        _last_rbi_check_at = now
        return updated + escalated
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def process_rbi_monthly_reports():
    global _last_rbi_report_check_at
    now = datetime.now(timezone.utc)
    report_day = max(1, int(settings.rbi_mis_report_day))
    if now.day < report_day:
        return 0
    if _last_rbi_report_check_at and _last_rbi_report_check_at.date() == now.date():
        return 0

    db = SessionLocal()
    try:
        if now.month == 1:
            report_month = now.replace(year=now.year - 1, month=12, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            report_month = now.replace(month=now.month - 1, day=1, hour=0, minute=0, second=0, microsecond=0)

        service = RBIComplianceService(db)
        clients = (
            db.query(Client)
            .join(RBIComplaint, RBIComplaint.client_id == Client.id)
            .distinct()
            .all()
        )
        generated = 0
        for client in clients:
            service.generate_monthly_mis_report(client.id, report_month, commit=False)
            generated += 1
        db.commit()
        _last_rbi_report_check_at = now
        return generated
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def process_escalations_monitor():
    global _last_escalation_check_at
    now = datetime.now(timezone.utc)
    # Check escalations every 5 minutes
    if _last_escalation_check_at and (now - _last_escalation_check_at).total_seconds() < 300:
        return 0

    db = SessionLocal()
    try:
        rbi_clients = db.query(Client).filter(Client.is_rbi_regulated == True).all()
        total_escalated = 0

        for client in rbi_clients:
            try:
                engine = EscalationEngine(db)
                stats = engine.process_pending_escalations(client.id)
                if stats["escalated"] > 0:
                    logger.info(
                        f"Escalations for {client.name}: checked={stats['checked']}, "
                        f"escalated={stats['escalated']}, errors={stats['errors']}"
                    )
                    total_escalated += stats["escalated"]
            except Exception as e:
                logger.error(f"Error processing escalations for client {client.id}: {e}", exc_info=True)

        _last_escalation_check_at = now
        return total_escalated
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def process_inbox_poll():
    global _last_inbox_poll_at
    now = datetime.now(timezone.utc)
    # Poll all Inbox-backed email providers every 90 seconds.
    if _last_inbox_poll_at and (now - _last_inbox_poll_at).total_seconds() < 90:
        return {"inboxes": 0, "fetched": 0, "processed": 0, "duplicates": 0, "errors": 0}

    result = poll_all_inboxes(max_results=20)
    _last_inbox_poll_at = now
    return result


def worker_loop(interval_seconds=30):
    logger.info("Simple queue worker started")
    while not _stop_event.is_set():
        try:
            processed = process_jobs()
            if processed:
                logger.info("Processed %s queued jobs", processed)
            retried = process_retry_queue()
            if retried:
                logger.info("Retried %s failed channel messages", retried)
            follow_up_actions = process_follow_up_automation()
            if follow_up_actions:
                logger.info("Processed %s follow-up automation actions", follow_up_actions)
            sla_updates = process_sla_monitor()
            if sla_updates:
                logger.info("Processed %s SLA status updates", sla_updates)
            rbi_updates = process_rbi_tat_monitor()
            if rbi_updates:
                logger.info("Processed %s RBI TAT status updates", rbi_updates)
            mis_reports = process_rbi_monthly_reports()
            if mis_reports:
                logger.info("Generated %s RBI MIS reports", mis_reports)
            escalations = process_escalations_monitor()
            if escalations:
                logger.info("Processed %s escalations", escalations)
            spikes = process_spike_detection()
            if spikes:
                logger.info("Detected %s complaint spikes", spikes)
            inbox_poll = process_inbox_poll()
            if inbox_poll["inboxes"] or inbox_poll["fetched"] or inbox_poll["errors"]:
                logger.info(
                    "Polled %s inboxes fetched=%s processed=%s duplicates=%s errors=%s",
                    inbox_poll["inboxes"],
                    inbox_poll["fetched"],
                    inbox_poll["processed"],
                    inbox_poll["duplicates"],
                    inbox_poll["errors"],
                )
        except Exception as exc:
            logger.exception("Queue worker error: %s", exc)
        _stop_event.wait(interval_seconds)


def start_worker_thread(interval_seconds=30):
    global _worker_thread
    if _worker_thread and _worker_thread.is_alive():
        return _worker_thread
    _worker_thread = threading.Thread(target=worker_loop, args=(interval_seconds,), daemon=True, name="simple-queue-worker")
    _worker_thread.start()
    return _worker_thread


def is_worker_alive():
    return bool(_worker_thread and _worker_thread.is_alive() and not _stop_event.is_set())


def stop_worker():
    _stop_event.set()
