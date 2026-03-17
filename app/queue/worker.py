from datetime import datetime, timedelta, timezone
import threading
import time

from app.db.models import Client, Complaint
from app.db.session import SessionLocal
from app.analytics.customer_pulse import detect_complaint_spikes
from app.queue.simple_queue import process_jobs
from app.replies.send_reply import send_complaint_reply
from app.utils.logging import get_logger

logger = get_logger(__name__)
_stop_event = threading.Event()
_worker_thread = None
_last_spike_check_at = None
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

        db.commit()
        return len(complaints_for_follow_up) + len(complaints_to_resolve)
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


def worker_loop(interval_seconds=30):
    logger.info("Simple queue worker started")
    while not _stop_event.is_set():
        try:
            processed = process_jobs()
            if processed:
                logger.info("Processed %s queued jobs", processed)
            follow_up_actions = process_follow_up_automation()
            if follow_up_actions:
                logger.info("Processed %s follow-up automation actions", follow_up_actions)
            spikes = process_spike_detection()
            if spikes:
                logger.info("Detected %s complaint spikes", spikes)
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
