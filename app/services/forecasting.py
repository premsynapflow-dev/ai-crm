"""EWMA-based complaint surge forecasting — Layer 8.

Algorithm:
  1. Load hourly complaint counts for last 14 days
  2. Apply EWMA with α=0.3 (weighted toward recent history)
  3. Apply seasonality adjustment (day-of-week + hour-of-day factors)
  4. Generate 24-hour forecast
  5. Trigger alert when forecast > 1.5x 7-day mean (critical at 2.0x)
  6. Persist forecasts to complaint_forecasts table (upsert)
  7. Back-fill actual_count for past hours

EWMA recurrence:
  F[0] = X[0]
  F[t] = α * X[t] + (1 - α) * F[t-1]
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from statistics import mean, stdev
from typing import Any

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.db.models import Client, Complaint, ComplaintForecast
from app.utils.logging import get_logger

logger = get_logger(__name__)

ALPHA = 0.3          # EWMA smoothing factor
SURGE_THRESHOLD = 1.5   # alert when forecast > 1.5× 7-day avg
CRITICAL_THRESHOLD = 2.0


def _hourly_counts(db: Session, client_id: str, days: int = 14) -> dict[datetime, int]:
    """Return {truncated_hour_utc: complaint_count} for the past N days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        db.query(
            func.date_trunc("hour", Complaint.created_at).label("hr"),
            func.count(Complaint.id).label("cnt"),
        )
        .filter(
            Complaint.client_id == client_id,
            Complaint.created_at >= cutoff,
        )
        .group_by(text("hr"))
        .all()
    )
    result: dict[datetime, int] = {}
    for hr, cnt in rows:
        if hr is None:
            continue
        if hr.tzinfo is None:
            hr = hr.replace(tzinfo=timezone.utc)
        result[hr] = int(cnt)
    return result


def _ewma_series(values: list[float], alpha: float = ALPHA) -> list[float]:
    if not values:
        return []
    smoothed = [values[0]]
    for x in values[1:]:
        smoothed.append(alpha * x + (1 - alpha) * smoothed[-1])
    return smoothed


def _seasonality_factors(hourly_counts: dict[datetime, int]) -> tuple[dict[int, float], dict[int, float]]:
    """Compute day-of-week and hour-of-day adjustment factors relative to overall mean."""
    if not hourly_counts:
        return {}, {}

    all_counts = list(hourly_counts.values())
    overall_avg = mean(all_counts) if all_counts else 1.0
    if overall_avg == 0:
        return {}, {}

    dow_totals: dict[int, list[int]] = defaultdict(list)
    hod_totals: dict[int, list[int]] = defaultdict(list)
    for hr, cnt in hourly_counts.items():
        dow_totals[hr.weekday()].append(cnt)
        hod_totals[hr.hour].append(cnt)

    dow_factors = {
        dow: (mean(counts) / overall_avg) for dow, counts in dow_totals.items()
    }
    hod_factors = {
        hod: (mean(counts) / overall_avg) for hod, counts in hod_totals.items()
    }
    return dow_factors, hod_factors


def run_forecast(db: Session, client_id: str, horizon_hours: int = 24) -> list[dict[str, Any]]:
    """
    Compute EWMA forecast for the next `horizon_hours` hours for one client.
    Upserts into complaint_forecasts table.
    Returns list of {forecast_hour, predicted_count, alert_triggered}.
    """
    hourly = _hourly_counts(db, client_id, days=14)

    if not hourly:
        return []

    # Build time-ordered list of (hour, count) for the last 14 days
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    start = now - timedelta(days=14)
    all_hours = []
    current = start
    while current <= now:
        all_hours.append((current, hourly.get(current, 0)))
        current += timedelta(hours=1)

    counts = [c for _, c in all_hours]
    smoothed = _ewma_series([float(c) for c in counts], ALPHA)
    last_ewma = smoothed[-1] if smoothed else 0.0

    # 7-day mean for alert threshold
    seven_day_cutoff = now - timedelta(days=7)
    recent_counts = [cnt for hr, cnt in hourly.items() if hr >= seven_day_cutoff]
    seven_day_avg = mean(recent_counts) if recent_counts else max(1.0, last_ewma)

    dow_factors, hod_factors = _seasonality_factors(hourly)

    results = []
    for h in range(1, horizon_hours + 1):
        target = now + timedelta(hours=h)
        dow = target.weekday()
        hod = target.hour
        dow_adj = dow_factors.get(dow, 1.0)
        hod_adj = hod_factors.get(hod, 1.0)
        predicted = max(0.0, last_ewma * dow_adj * hod_adj)
        alert = predicted > seven_day_avg * SURGE_THRESHOLD
        critical = predicted > seven_day_avg * CRITICAL_THRESHOLD

        # Upsert into DB
        existing = (
            db.query(ComplaintForecast)
            .filter(
                ComplaintForecast.client_id == client_id,
                ComplaintForecast.forecast_hour == target,
            )
            .first()
        )
        if existing:
            existing.predicted_count = round(predicted, 2)
            existing.alert_triggered = alert or critical
        else:
            db.add(ComplaintForecast(
                client_id=client_id,
                forecast_hour=target,
                predicted_count=round(predicted, 2),
                alert_triggered=alert or critical,
            ))

        results.append({
            "forecast_hour": target.isoformat(),
            "predicted_count": round(predicted, 2),
            "alert_triggered": alert,
            "critical_alert": critical,
            "seven_day_avg": round(seven_day_avg, 2),
        })

    # Back-fill actual counts for past hours
    _backfill_actuals(db, client_id, hourly)

    db.commit()
    return results


def _backfill_actuals(db: Session, client_id: str, hourly: dict[datetime, int]) -> None:
    """Fill actual_count for past forecast rows where it's still NULL."""
    past_rows = (
        db.query(ComplaintForecast)
        .filter(
            ComplaintForecast.client_id == client_id,
            ComplaintForecast.actual_count.is_(None),
            ComplaintForecast.forecast_hour <= datetime.now(timezone.utc),
        )
        .all()
    )
    for row in past_rows:
        hr = row.forecast_hour
        if hr.tzinfo is None:
            hr = hr.replace(tzinfo=timezone.utc)
        row.actual_count = hourly.get(hr, 0)


def get_forecast_summary(db: Session, client_id: str, hours: int = 24) -> list[dict]:
    """Load persisted forecasts without recomputing."""
    now = datetime.now(timezone.utc)
    rows = (
        db.query(ComplaintForecast)
        .filter(
            ComplaintForecast.client_id == client_id,
            ComplaintForecast.forecast_hour >= now,
            ComplaintForecast.forecast_hour <= now + timedelta(hours=hours),
        )
        .order_by(ComplaintForecast.forecast_hour.asc())
        .all()
    )
    return [
        {
            "forecast_hour": r.forecast_hour.isoformat(),
            "predicted_count": r.predicted_count,
            "actual_count": r.actual_count,
            "alert_triggered": r.alert_triggered,
        }
        for r in rows
    ]
