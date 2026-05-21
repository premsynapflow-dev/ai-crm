from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import get_settings
from app.db.models import JobQueue
from app.utils.logging import get_logger

logger = get_logger(__name__)

REDIS_QUEUE_KEY = "synapflow:jobs:queued"


@dataclass
class QueueEnvelope:
    id: str
    job_type: str
    payload: dict[str, Any]
    backend: str
    retry_count: int = 0
    raw: Any = None


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class PostgresQueueBackend:
    name = "postgres"

    def enqueue(self, db, job_type: str, payload: dict[str, Any], scheduled_for=None):
        job = JobQueue(job_type=job_type, payload=payload, scheduled_for=scheduled_for)
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    def fetch(self, db, limit: int = 10) -> list[QueueEnvelope]:
        now = datetime.now(timezone.utc)
        lease_until = now + timedelta(minutes=15)
        (
            db.query(JobQueue)
            .filter(JobQueue.status == "processing", JobQueue.scheduled_for.isnot(None), JobQueue.scheduled_for <= now)
            .update({JobQueue.status: "queued"}, synchronize_session=False)
        )
        query = (
            db.query(JobQueue)
            .filter(
                JobQueue.status == "queued",
                (JobQueue.scheduled_for.is_(None)) | (JobQueue.scheduled_for <= now),
            )
            .order_by(JobQueue.scheduled_for.asc().nullsfirst(), JobQueue.created_at.asc())
        )
        if db.get_bind() is not None and db.get_bind().dialect.name.startswith("postgresql"):
            query = query.with_for_update(skip_locked=True)
        jobs = query.limit(limit).all()
        for job in jobs:
            job.status = "processing"
            job.scheduled_for = lease_until
        if jobs:
            db.commit()
        return [
            QueueEnvelope(
                id=str(job.id),
                job_type=job.job_type,
                payload=job.payload or {},
                retry_count=int(job.retry_count or 0),
                backend=self.name,
                raw=job,
            )
            for job in jobs
        ]

    def mark_processing(self, db, envelope: QueueEnvelope) -> None:
        envelope.raw.status = "processing"
        db.commit()

    def mark_completed(self, db, envelope: QueueEnvelope) -> None:
        envelope.raw.status = "completed"
        envelope.raw.scheduled_for = None
        envelope.raw.processed_at = datetime.now(timezone.utc)
        db.commit()

    def mark_failed(self, db, envelope: QueueEnvelope, error: Exception) -> None:
        job = envelope.raw
        job.retry_count = int(job.retry_count or 0) + 1
        if job.retry_count >= 3:
            job.status = "dead_letter"
        else:
            job.status = "queued"
            job.scheduled_for = datetime.now(timezone.utc) + timedelta(seconds=min(300, 2 ** job.retry_count * 10))
        job.last_error = str(error)
        db.commit()

    def health(self, db) -> dict[str, Any]:
        pending = db.query(JobQueue).filter(JobQueue.status == "queued").count()
        processing = db.query(JobQueue).filter(JobQueue.status == "processing").count()
        failed = db.query(JobQueue).filter(JobQueue.status == "failed").count()
        dead_letter = db.query(JobQueue).filter(JobQueue.status == "dead_letter").count()
        return {
            "backend": self.name,
            "available": True,
            "pending": pending,
            "processing": processing,
            "failed": failed,
            "dead_letter": dead_letter,
        }


class RedisQueueBackend:
    name = "redis"

    def __init__(self, redis_url: str):
        self.redis_url = redis_url

    def _client(self):
        try:
            import redis
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("redis package is not installed") from exc
        return redis.Redis.from_url(self.redis_url, decode_responses=True)

    def enqueue(self, db, job_type: str, payload: dict[str, Any], scheduled_for=None):
        envelope = {
            "id": str(uuid.uuid4()),
            "job_type": job_type,
            "payload": payload or {},
            "retry_count": 0,
            "scheduled_for": scheduled_for.isoformat() if hasattr(scheduled_for, "isoformat") else scheduled_for,
            "created_at": _utcnow_iso(),
        }
        self._client().rpush(REDIS_QUEUE_KEY, json.dumps(envelope))
        return envelope

    def fetch(self, db, limit: int = 10) -> list[QueueEnvelope]:
        client = self._client()
        jobs: list[QueueEnvelope] = []
        for _ in range(limit):
            raw = client.lpop(REDIS_QUEUE_KEY)
            if raw is None:
                break
            data = json.loads(raw)
            jobs.append(
                QueueEnvelope(
                    id=data["id"],
                    job_type=data["job_type"],
                    payload=data.get("payload") or {},
                    retry_count=int(data.get("retry_count") or 0),
                    backend=self.name,
                    raw=data,
                )
            )
        return jobs

    def mark_processing(self, db, envelope: QueueEnvelope) -> None:
        return None

    def mark_completed(self, db, envelope: QueueEnvelope) -> None:
        return None

    def mark_failed(self, db, envelope: QueueEnvelope, error: Exception) -> None:
        data = dict(envelope.raw or {})
        data["retry_count"] = int(data.get("retry_count") or 0) + 1
        data["last_error"] = str(error)
        if data["retry_count"] < 3:
            self._client().rpush(REDIS_QUEUE_KEY, json.dumps(data))
        else:
            self._client().rpush(f"{REDIS_QUEUE_KEY}:dead_letter", json.dumps(data))

    def health(self, db) -> dict[str, Any]:
        client = self._client()
        client.ping()
        return {
            "backend": self.name,
            "available": True,
            "pending": int(client.llen(REDIS_QUEUE_KEY)),
            "processing": None,
            "failed": None,
            "dead_letter": int(client.llen(f"{REDIS_QUEUE_KEY}:dead_letter")),
        }


def get_queue_backend():
    settings = get_settings()
    requested = settings.queue_backend
    if requested in {"auto", "redis"} and settings.redis_url.strip():
        try:
            backend = RedisQueueBackend(settings.redis_url.strip())
            backend._client().ping()
            return backend
        except Exception as exc:
            if requested == "redis":
                raise
            logger.warning("Redis queue unavailable; falling back to Postgres queue: %s", exc)
    return PostgresQueueBackend()


def queue_health(db) -> dict[str, Any]:
    try:
        return get_queue_backend().health(db)
    except Exception as exc:
        return {"backend": "redis", "available": False, "error": str(exc)}
