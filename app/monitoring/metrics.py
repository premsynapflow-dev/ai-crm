import asyncio
import concurrent.futures
import threading
from collections import deque
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter
from sqlalchemy import func

from app.db.models import MonitoringMetric
from app.db.session import SessionLocal

router = APIRouter(prefix="/metrics", tags=["metrics"])

# In-memory buffer — metrics are queued here, flushed to DB by background thread
# maxlen=2000 prevents unbounded growth; oldest entries are dropped under pressure
_buffer: deque = deque(maxlen=2000)
_buffer_lock = threading.Lock()
_flush_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="metrics")


def record_metric(metric_name: str, metric_value: float, dimensions: dict | None = None) -> None:
    """Non-blocking: append to in-memory buffer. Never opens a DB connection."""
    with _buffer_lock:
        _buffer.append({
            "metric_name": metric_name,
            "metric_value": metric_value,
            "dimensions": dimensions or {},
        })


def flush_metrics() -> None:
    """Drain the in-memory buffer to the DB. Called by background worker."""
    with _buffer_lock:
        if not _buffer:
            return
        batch = list(_buffer)
        _buffer.clear()

    if not batch:
        return

    try:
        db = SessionLocal()
        db.bulk_insert_mappings(MonitoringMetric, batch)
        db.commit()
        db.close()
    except Exception:
        pass  # Metrics are best-effort; never raise


def _aggregate(metric_name: str, minutes: int = 60):
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        avg = db.query(func.avg(MonitoringMetric.metric_value)).filter(
            MonitoringMetric.metric_name == metric_name,
            MonitoringMetric.created_at >= cutoff,
        ).scalar()
        count = db.query(func.count(MonitoringMetric.id)).filter(
            MonitoringMetric.metric_name == metric_name,
            MonitoringMetric.created_at >= cutoff,
        ).scalar()
        return {"average": float(avg or 0.0), "count": count or 0}
    finally:
        db.close()


@router.get("")
def metrics_overview():
    return {
        "requests_per_minute": _aggregate("request_duration_ms", minutes=1),
        "errors_per_minute": _aggregate("error_count", minutes=1),
        "average_response_time": _aggregate("request_duration_ms", minutes=60),
    }
