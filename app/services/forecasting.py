"""EWMA-based complaint surge forecasting.

Algorithm:
  1. Load hourly complaint counts for last N days
  2. Apply EWMA with α=0.3 (weighted toward recent history)
  3. Apply seasonality adjustment ONLY when sufficient history (≥14 days)
  4. Generate 24-hour forecast with confidence bands
  5. Trigger alert when forecast > 1.5x 7-day mean (critical at 2.0x)
  6. Persist forecasts to complaint_forecasts table (upsert)
  7. Back-fill actual_count for past hours + log to forecast_accuracy_log

EWMA recurrence:
  F[0] = X[0]
  F[t] = α * X[t] + (1 - α) * F[t-1]
"""
from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from statistics import mean, stdev
from typing import Any

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.db.models import Client, Complaint, ComplaintForecast, ForecastAccuracyLog
from app.intelligence.constants import (
    FORECAST_ALPHA,
    FORECAST_ALERT_MULTIPLIER,
    FORECAST_CRITICAL_MULTIPLIER,
    FORECAST_CONFIDENCE_LOWER,
    FORECAST_CONFIDENCE_UPPER,
    FORECAST_LOW_DATA_LOWER,
    FORECAST_LOW_DATA_UPPER,
    FORECAST_MIN_DATA_DAYS,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)


def _hourly_counts(db: Session, client_id: str, days: int = 30) -> dict[datetime, int]:
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


def _ewma_series(values: list[float], alpha: float = FORECAST_ALPHA) -> list[float]:
    if not values:
        return []
    smoothed = [values[0]]
    for x in values[1:]:
        smoothed.append(alpha * x + (1 - alpha) * smoothed[-1])
    return smoothed


def _seasonality_factors(
    hourly_counts: dict[datetime, int],
    min_days: int = FORECAST_MIN_DATA_DAYS,
) -> tuple[dict[int, float], dict[int, float], bool]:
    """Compute day-of-week and hour-of-day factors.

    Returns (dow_factors, hod_factors, has_sufficient_data).
    When data spans fewer than min_days, returns all-1.0 factors and
    has_sufficient_data=False so callers can widen confidence bands.
    """
    if not hourly_counts:
        return {}, {}, False

    # Check how many distinct days are in the dataset
    distinct_days = len({hr.date() for hr in hourly_counts})
    has_sufficient_data = distinct_days >= min_days

    if not has_sufficient_data:
        return {}, {}, False

    all_counts = list(hourly_counts.values())
    overall_avg = mean(all_counts) if all_counts else 1.0
    if overall_avg == 0:
        return {}, {}, False

    dow_totals: dict[int, list[int]] = defaultdict(list)
    hod_totals: dict[int, list[int]] = defaultdict(list)
    for hr, cnt in hourly_counts.items():
        dow_totals[hr.weekday()].append(cnt)
        hod_totals[hr.hour].append(cnt)

    dow_factors = {dow: (mean(counts) / overall_avg) for dow, counts in dow_totals.items()}
    hod_factors = {hod: (mean(counts) / overall_avg) for hod, counts in hod_totals.items()}
    return dow_factors, hod_factors, True


def compute_rolling_mape(db: Session, client_id: str, days: int = 30) -> float | None:
    """Mean Absolute Percentage Error over completed forecast rows (last N days).

    Returns None if fewer than 5 completed forecasts exist.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        db.query(ForecastAccuracyLog)
        .filter(
            ForecastAccuracyLog.client_id == client_id,
            ForecastAccuracyLog.target_date >= cutoff,
            ForecastAccuracyLog.actual_count.isnot(None),
            ForecastAccuracyLog.pct_error.isnot(None),
        )
        .all()
    )
    if len(rows) < 5:
        return None
    return round(mean(abs(r.pct_error) for r in rows), 1)


def run_forecast(db: Session, client_id: str, horizon_hours: int = 24) -> list[dict[str, Any]]:
    """Compute EWMA forecast for the next horizon_hours hours for one client.

    Returns list of dicts with confidence bands and data sufficiency flag.
    """
    hourly = _hourly_counts(db, client_id, days=30)

    if not hourly:
        return []

    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    start = now - timedelta(days=30)
    all_hours = []
    current = start
    while current <= now:
        all_hours.append((current, hourly.get(current, 0)))
        current += timedelta(hours=1)

    counts = [float(c) for _, c in all_hours]
    smoothed = _ewma_series(counts, FORECAST_ALPHA)
    last_ewma = smoothed[-1] if smoothed else 0.0

    seven_day_cutoff = now - timedelta(days=7)
    recent_counts = [cnt for hr, cnt in hourly.items() if hr >= seven_day_cutoff]
    seven_day_avg = mean(recent_counts) if recent_counts else max(1.0, last_ewma)

    dow_factors, hod_factors, has_sufficient_data = _seasonality_factors(hourly)
    historical_mape = compute_rolling_mape(db, client_id)
    data_days = len({hr.date() for hr in hourly})

    # Confidence band multipliers — wider when not enough history
    conf_lower = FORECAST_CONFIDENCE_LOWER if has_sufficient_data else FORECAST_LOW_DATA_LOWER
    conf_upper = FORECAST_CONFIDENCE_UPPER if has_sufficient_data else FORECAST_LOW_DATA_UPPER

    results = []
    for h in range(1, horizon_hours + 1):
        target = now + timedelta(hours=h)
        dow = target.weekday()
        hod = target.hour
        dow_adj = dow_factors.get(dow, 1.0) if has_sufficient_data else 1.0
        hod_adj = hod_factors.get(hod, 1.0) if has_sufficient_data else 1.0
        predicted = max(0.0, last_ewma * dow_adj * hod_adj)
        alert = predicted > seven_day_avg * FORECAST_ALERT_MULTIPLIER
        critical = predicted > seven_day_avg * FORECAST_CRITICAL_MULTIPLIER

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

        # Log to accuracy tracking table
        _upsert_accuracy_log(db, client_id, now, target, round(predicted, 2), {
            "alpha": FORECAST_ALPHA,
            "dow_adj": round(dow_adj, 3),
            "hod_adj": round(hod_adj, 3),
            "has_sufficient_data": has_sufficient_data,
        })

        results.append({
            "forecast_hour": target.isoformat(),
            "predicted_count": round(predicted, 2),
            "confidence_lower": round(predicted * conf_lower, 2),
            "confidence_upper": round(predicted * conf_upper, 2),
            "alert_triggered": alert,
            "critical_alert": critical,
            "seven_day_avg": round(seven_day_avg, 2),
            "has_sufficient_data": has_sufficient_data,
            "data_days_available": data_days,
            "historical_mape": historical_mape,
        })

    _backfill_actuals(db, client_id, hourly)
    db.commit()
    return results


def _upsert_accuracy_log(
    db: Session,
    client_id: str,
    forecast_date: datetime,
    target_date: datetime,
    predicted_count: float,
    params: dict,
) -> None:
    """Insert a forecast accuracy record (skipped if already exists)."""
    try:
        existing = (
            db.query(ForecastAccuracyLog)
            .filter(
                ForecastAccuracyLog.client_id == client_id,
                ForecastAccuracyLog.forecast_date == forecast_date,
                ForecastAccuracyLog.target_date == target_date,
            )
            .first()
        )
        if not existing:
            db.add(ForecastAccuracyLog(
                id=uuid.uuid4(),
                client_id=client_id,
                forecast_date=forecast_date,
                target_date=target_date,
                predicted_count=predicted_count,
                forecast_params=params,
            ))
    except Exception as exc:
        logger.debug("Could not log forecast accuracy: %s", exc)


def _backfill_actuals(db: Session, client_id: str, hourly: dict[datetime, int]) -> None:
    """Fill actual_count for past forecast rows and accuracy log rows."""
    # Backfill ComplaintForecast table
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

    # Backfill ForecastAccuracyLog table
    try:
        accuracy_rows = (
            db.query(ForecastAccuracyLog)
            .filter(
                ForecastAccuracyLog.client_id == client_id,
                ForecastAccuracyLog.actual_count.is_(None),
                ForecastAccuracyLog.target_date <= datetime.now(timezone.utc),
            )
            .all()
        )
        for row in accuracy_rows:
            hr = row.target_date
            if hr.tzinfo is None:
                hr = hr.replace(tzinfo=timezone.utc)
            actual = hourly.get(hr)
            if actual is not None:
                row.actual_count = actual
                err = abs(actual - row.predicted_count)
                row.absolute_error = round(err, 2)
                row.pct_error = round((err / actual) * 100, 1) if actual > 0 else None
    except Exception as exc:
        logger.debug("Could not backfill accuracy log: %s", exc)


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
