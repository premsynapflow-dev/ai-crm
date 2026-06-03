"""Revenue at Risk API — Layer 4 completion."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.dependencies.auth import require_api_key
from app.db.models import Client
from app.db.session import get_db
from app.services.revenue_risk import compute_revenue_at_risk, get_30day_trend, save_daily_snapshot
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/revenue-risk")
def revenue_risk_summary(
    refresh: bool = Query(False, description="Force recalculate and save today's snapshot"),
    db: Session = Depends(get_db),
    current_client: Client = Depends(require_api_key),
):
    """
    Current revenue-at-risk for all high-risk customers (churn_risk_score >= 70).

    Returns the live calculation + last-30-days trend.
    """
    client_id = str(current_client.id)

    if refresh:
        try:
            save_daily_snapshot(db, client_id)
        except Exception as exc:
            logger.warning("Revenue risk snapshot failed: %s", exc)

    current = compute_revenue_at_risk(db, client_id)
    trend = get_30day_trend(db, client_id)

    return {
        "client_id": client_id,
        "current": current,
        "trend_30d": trend,
    }
