from datetime import datetime, timedelta, timezone

from app.db.models import JobQueue
from app.db.session import SessionLocal
from app.integrations.email import send_email
from app.integrations.slack import send_slack_alert
from app.services.response_tracking import mark_first_response_by_id


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


def _process_job(job):
    if job.job_type == "send_email":
        send_email(
            to_email=job.payload.get("to_email"),
            subject=job.payload.get("subject", "Neuronyx Notification"),
            body=job.payload.get("body", ""),
        )
        complaint_id = job.payload.get("complaint_id")
        if complaint_id:
            db = SessionLocal()
            try:
                if mark_first_response_by_id(db, complaint_id):
                    db.commit()
            except Exception:
                db.rollback()
            finally:
                db.close()
    elif job.job_type == "send_slack":
        send_slack_alert(
            job.payload.get("text", ""),
            webhook_url=job.payload.get("webhook_url"),
        )
    elif job.job_type == "sync_integration":
        return


def process_jobs(batch_size=20):
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        jobs = (
            db.query(JobQueue)
            .filter(
                JobQueue.status == "queued",
                (JobQueue.scheduled_for.is_(None)) | (JobQueue.scheduled_for <= now),
            )
            .order_by(JobQueue.created_at.asc())
            .limit(batch_size)
            .all()
        )
        for job in jobs:
            try:
                job.status = "processing"
                db.flush()
                _process_job(job)
                job.status = "done"
                job.processed_at = now
                job.last_error = None
            except Exception as exc:
                job.retry_count += 1
                job.status = "failed" if job.retry_count >= 3 else "queued"
                job.last_error = str(exc)
        db.commit()
        return len(jobs)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
