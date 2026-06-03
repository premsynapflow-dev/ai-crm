"""Surge Forecasting API — Layer 8: EWMA-based complaint volume predictions."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.orm import Session

from app.db.models import Client
from app.db.session import get_db
from app.dependencies.auth import require_api_key
from app.services.forecasting import get_forecast_summary, run_forecast
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/forecast")
def get_forecast(
    hours: int = Query(24, ge=1, le=72, description="Forecast horizon in hours"),
    refresh: bool = Query(False, description="Recompute forecast before returning"),
    db: Session = Depends(get_db),
    current_client: Client = Depends(require_api_key),
):
    """
    Return surge forecast for the next N hours.

    Uses EWMA (α=0.3) with day-of-week and hour-of-day seasonality adjustment.
    alert_triggered=true when forecast > 1.5× 7-day average.
    """
    client_id = str(current_client.id)

    if refresh:
        try:
            run_forecast(db, client_id, horizon_hours=hours)
        except Exception as exc:
            logger.warning("Forecast refresh failed for client=%s: %s", client_id, exc)

    forecasts = get_forecast_summary(db, client_id, hours=hours)

    if not forecasts and refresh:
        # get_forecast_summary returned empty because run_forecast committed;
        # re-query after commit
        forecasts = get_forecast_summary(db, client_id, hours=hours)

    alerts = [f for f in forecasts if f.get("alert_triggered")]

    return {
        "client_id": client_id,
        "horizon_hours": hours,
        "forecasts": forecasts,
        "alert_count": len(alerts),
        "next_alert": alerts[0] if alerts else None,
    }


@router.post("/forecast/run")
def trigger_forecast(
    background_tasks: BackgroundTasks,
    hours: int = Query(24, ge=1, le=72),
    db: Session = Depends(get_db),
    current_client: Client = Depends(require_api_key),
):
    """Trigger EWMA forecast computation as a background task."""
    client_id = str(current_client.id)

    def _run():
        from app.db.session import SessionLocal
        _db = SessionLocal()
        try:
            result = run_forecast(_db, client_id, horizon_hours=hours)
            alerts = sum(1 for r in result if r.get("alert_triggered"))
            logger.info("Forecast complete client=%s hours=%s alerts=%s", client_id, hours, alerts)
        except Exception as exc:
            logger.exception("Forecast run failed client=%s: %s", client_id, exc)
        finally:
            _db.close()

    background_tasks.add_task(_run)
    return {"status": "started", "message": f"Forecast job queued for {hours}-hour horizon."}
