from datetime import datetime, timedelta, timezone
import threading

from app.config import get_settings
from app.db.models import Client, Complaint, RBIComplaint
from app.db.session import SessionLocal
from app.analytics.customer_pulse import detect_complaint_spikes
from app.queue.simple_queue import process_jobs
from app.replies.send_reply import send_complaint_reply
from app.services.inbox_poller import poll_all_inboxes, poll_connector_connections
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
_last_connector_poll_at = None
_last_embedding_run_at = None
_last_revenue_risk_at = None
_last_forecast_at = None
_last_approval_expiry_at = None
_last_outcome_check_at = None
_last_feedback_loop_at = None
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


def process_connector_poll():
    global _last_connector_poll_at
    now = datetime.now(timezone.utc)
    # Poll universal connectors (Google Reviews, Trustpilot, etc.) every 10 minutes.
    if _last_connector_poll_at and (now - _last_connector_poll_at).total_seconds() < 600:
        return None

    result = poll_connector_connections(max_results=50)
    _last_connector_poll_at = now
    return result


def process_embeddings():
    """Generate complaint embeddings for clustering — runs every 4 hours."""
    global _last_embedding_run_at
    now = datetime.now(timezone.utc)
    if _last_embedding_run_at and (now - _last_embedding_run_at).total_seconds() < 14400:
        return None

    db = SessionLocal()
    try:
        from app.services.complaint_clustering import generate_embeddings_batch
        clients = db.query(Client).all()
        total = 0
        for client in clients:
            try:
                n = generate_embeddings_batch(db, str(client.id), batch_size=50)
                total += n
            except Exception as exc:
                if "does not exist" not in str(exc).lower():
                    logger.warning("Embedding gen failed for client %s: %s", client.id, exc)
        _last_embedding_run_at = now
        return total
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def process_forecasts():
    """Run EWMA surge forecasting for all clients — every hour."""
    global _last_forecast_at
    now = datetime.now(timezone.utc)
    if _last_forecast_at and (now - _last_forecast_at).total_seconds() < 3600:
        return None

    db = SessionLocal()
    try:
        from app.services.forecasting import run_forecast
        clients = db.query(Client).all()
        total_alerts = 0
        for client in clients:
            try:
                results = run_forecast(db, str(client.id), horizon_hours=24)
                total_alerts += sum(1 for r in results if r.get("alert_triggered"))
            except Exception as exc:
                if "does not exist" not in str(exc).lower():
                    logger.warning("Forecast failed for client %s: %s", client.id, exc)
        _last_forecast_at = now
        return total_alerts
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def process_outcome_measurements():
    """Measure deferred workflow outcomes (T+48h) — every 30 minutes."""
    global _last_outcome_check_at
    now = datetime.now(timezone.utc)
    if _last_outcome_check_at and (now - _last_outcome_check_at).total_seconds() < 1800:
        return None

    db = SessionLocal()
    try:
        from app.services.outcome_tracker import process_pending_outcomes
        count = process_pending_outcomes(db, batch_size=50)
        _last_outcome_check_at = now
        return count
    except Exception as exc:
        if "does not exist" not in str(exc).lower():
            logger.warning("Outcome measurement failed: %s", exc)
        return None
    finally:
        db.close()


def process_feedback_loop():
    """Run autonomous weight recalibration — once per week."""
    global _last_feedback_loop_at
    now = datetime.now(timezone.utc)
    if _last_feedback_loop_at and (now - _last_feedback_loop_at).total_seconds() < 604800:
        return None

    db = SessionLocal()
    try:
        from app.services.feedback_loop import run_feedback_loop_for_all
        result = run_feedback_loop_for_all(db)
        _last_feedback_loop_at = now
        logger.info(
            "Feedback loop complete: calibrated=%s skipped=%s",
            result.get("calibrated"), result.get("skipped"),
        )
        return result
    except Exception as exc:
        if "does not exist" not in str(exc).lower():
            logger.warning("Feedback loop failed: %s", exc)
        return None
    finally:
        db.close()


def process_approval_expiry():
    """Expire timed-out approval requests — every 5 minutes."""
    global _last_approval_expiry_at
    now = datetime.now(timezone.utc)
    if _last_approval_expiry_at and (now - _last_approval_expiry_at).total_seconds() < 300:
        return None

    db = SessionLocal()
    try:
        from app.services.approval_service import expire_timed_out_approvals
        expired = expire_timed_out_approvals(db)
        _last_approval_expiry_at = now
        return expired
    except Exception as exc:
        if "does not exist" not in str(exc).lower():
            logger.warning("Approval expiry failed: %s", exc)
        return None
    finally:
        db.close()


def process_revenue_risk_snapshots():
    """Save daily revenue-at-risk snapshots for all clients — runs once per day."""
    global _last_revenue_risk_at
    now = datetime.now(timezone.utc)
    if _last_revenue_risk_at and (now - _last_revenue_risk_at).total_seconds() < 86400:
        return None

    db = SessionLocal()
    try:
        from app.services.revenue_risk import save_daily_snapshot
        clients = db.query(Client).all()
        saved = 0
        for client in clients:
            try:
                save_daily_snapshot(db, str(client.id), commit=False)
                saved += 1
            except Exception as exc:
                if "does not exist" not in str(exc).lower():
                    logger.warning("Revenue risk snapshot failed for client %s: %s", client.id, exc)
        db.commit()
        _last_revenue_risk_at = now
        return saved
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _run_step(name: str, fn, *args, **kwargs):
    """Run a single worker step, logging and suppressing any exception so other steps still run."""
    try:
        return fn(*args, **kwargs)
    except Exception as exc:
        if "does not exist" in str(exc).lower():
            logger.warning("Worker step %s skipped (schema not ready): %s", name, exc)
        else:
            logger.exception("Worker step %s failed: %s", name, exc)
        return None


def worker_loop(interval_seconds=30):
    logger.info("Simple queue worker started")
    while not _stop_event.is_set():
        from app.monitoring.metrics import flush_metrics
        _run_step("flush_metrics", flush_metrics)

        processed = _run_step("process_jobs", process_jobs)
        if processed:
            logger.info("Processed %s queued jobs", processed)

        retried = _run_step("process_retry_queue", process_retry_queue)
        if retried:
            logger.info("Retried %s failed channel messages", retried)

        follow_up_actions = _run_step("process_follow_up_automation", process_follow_up_automation)
        if follow_up_actions:
            logger.info("Processed %s follow-up automation actions", follow_up_actions)

        sla_updates = _run_step("process_sla_monitor", process_sla_monitor)
        if sla_updates:
            logger.info("Processed %s SLA status updates", sla_updates)

        rbi_updates = _run_step("process_rbi_tat_monitor", process_rbi_tat_monitor)
        if rbi_updates:
            logger.info("Processed %s RBI TAT status updates", rbi_updates)

        mis_reports = _run_step("process_rbi_monthly_reports", process_rbi_monthly_reports)
        if mis_reports:
            logger.info("Generated %s RBI MIS reports", mis_reports)

        escalations = _run_step("process_escalations_monitor", process_escalations_monitor)
        if escalations:
            logger.info("Processed %s escalations", escalations)

        spikes = _run_step("process_spike_detection", process_spike_detection)
        if spikes:
            logger.info("Detected %s complaint spikes", spikes)

        inbox_poll = _run_step("process_inbox_poll", process_inbox_poll)
        if inbox_poll and (inbox_poll["inboxes"] or inbox_poll["fetched"] or inbox_poll["errors"]):
            logger.info(
                "Polled %s inboxes fetched=%s processed=%s duplicates=%s errors=%s",
                inbox_poll["inboxes"],
                inbox_poll["fetched"],
                inbox_poll["processed"],
                inbox_poll["duplicates"],
                inbox_poll["errors"],
            )

        connector_poll = _run_step("process_connector_poll", process_connector_poll)
        if connector_poll and connector_poll.get("fetched"):
            logger.info(
                "Connector poll: connections=%s fetched=%s processed=%s errors=%s",
                connector_poll["connections"],
                connector_poll["fetched"],
                connector_poll["processed"],
                connector_poll["errors"],
            )

        embedded = _run_step("process_embeddings", process_embeddings)
        if embedded:
            logger.info("Generated %s new complaint embeddings", embedded)

        risk_snaps = _run_step("process_revenue_risk_snapshots", process_revenue_risk_snapshots)
        if risk_snaps:
            logger.info("Saved revenue-at-risk snapshots for %s clients", risk_snaps)

        _run_step("process_forecasts", process_forecasts)
        _run_step("process_approval_expiry", process_approval_expiry)
        _run_step("process_outcome_measurements", process_outcome_measurements)
        _run_step("process_feedback_loop", process_feedback_loop)

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
