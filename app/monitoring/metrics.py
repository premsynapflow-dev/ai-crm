from datetime import datetime, timedelta, timezone

from fastapi import APIRouter
from sqlalchemy import func

from app.db.models import MonitoringMetric
from app.db.session import SessionLocal

router = APIRouter(prefix="/metrics", tags=["metrics"])


def record_metric(metric_name: str, metric_value: float, dimensions: dict | None = None):
    db = SessionLocal()
    try:
        db.add(MonitoringMetric(metric_name=metric_name, metric_value=metric_value, dimensions=dimensions or {}))
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


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
