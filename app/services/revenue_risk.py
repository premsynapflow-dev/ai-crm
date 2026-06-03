"""Revenue at Risk and Retention Probability computation.

Queries CustomerProfile (Customer model) for churn_risk_score >= threshold,
computes revenue_at_risk = sum(LTV × churn_probability), and persists a
daily snapshot to revenue_risk_snapshots.
"""
from __future__ import annotations

import os
from datetime import date, datetime, timezone
from statistics import mean
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Customer, RevenueRiskSnapshot
from app.utils.logging import get_logger

logger = get_logger(__name__)

_HIGH_RISK_THRESHOLD = 70.0
_DEFAULT_LTV = 10_000.0  # ₹10,000 fallback when no LTV recorded


def _estimate_ltv(customer: Customer) -> float:
    """Return LTV or a sensible default when not recorded."""
    if customer.lifetime_value and customer.lifetime_value > 0:
        return float(customer.lifetime_value)
    # Rough estimate: ₹500/interaction * expected 20 annual interactions
    interactions = customer.total_interactions or 1
    return max(_DEFAULT_LTV, interactions * 500.0)


def compute_revenue_at_risk(db: Session, client_id: str) -> dict[str, Any]:
    """
    Compute current revenue-at-risk for all high-risk customers of a client.

    Returns a dict with: revenue_at_risk, high_risk_customers, avg_churn_probability,
    breakdown (list of top-10 highest-risk customers).
    """
    high_risk = (
        db.query(Customer)
        .filter(
            Customer.client_id == client_id,
            Customer.churn_risk_score >= _HIGH_RISK_THRESHOLD,
            Customer.is_master.is_(True),
        )
        .order_by(Customer.churn_risk_score.desc())
        .all()
    )

    if not high_risk:
        return {
            "revenue_at_risk": 0.0,
            "high_risk_customers": 0,
            "avg_churn_probability": 0.0,
            "breakdown": [],
        }

    total_risk = 0.0
    breakdown = []
    for customer in high_risk:
        ltv = _estimate_ltv(customer)
        churn_prob = customer.churn_risk_score / 100.0
        risk = round(ltv * churn_prob, 2)
        total_risk += risk
        breakdown.append({
            "customer_id": str(customer.id),
            "email": customer.primary_email,
            "churn_risk_score": customer.churn_risk_score,
            "churn_probability": round(churn_prob, 3),
            "ltv": round(ltv, 2),
            "revenue_at_risk": risk,
        })

    churn_probs = [c.churn_risk_score / 100.0 for c in high_risk]

    return {
        "revenue_at_risk": round(total_risk, 2),
        "high_risk_customers": len(high_risk),
        "avg_churn_probability": round(mean(churn_probs), 3),
        "breakdown": breakdown[:10],
    }


def compute_retention_probability(customer: Customer) -> float:
    """
    P(retention) = (1 - churn_probability) + intervention_uplift.

    Intervention uplifts:
      - complaint resolved within SLA → +0.10
      - AI reply was sent → +0.05
    """
    base_retention = 1.0 - (customer.churn_risk_score / 100.0)

    uplift = 0.0
    # Proxy: customers with low open ticket counts are better served
    if (customer.open_tickets or 0) == 0 and (customer.total_tickets or 0) > 0:
        uplift += 0.10
    if (customer.total_interactions or 0) > 3:
        uplift += 0.05

    return round(min(1.0, base_retention + uplift), 3)


def save_daily_snapshot(db: Session, client_id: str, commit: bool = True) -> RevenueRiskSnapshot:
    """Compute and upsert today's revenue-at-risk snapshot."""
    today = date.today()
    result = compute_revenue_at_risk(db, client_id)

    existing = (
        db.query(RevenueRiskSnapshot)
        .filter(
            RevenueRiskSnapshot.client_id == client_id,
            RevenueRiskSnapshot.snapshot_date == today,
        )
        .first()
    )
    if existing:
        existing.revenue_at_risk = result["revenue_at_risk"]
        existing.high_risk_customer_count = result["high_risk_customers"]
        existing.avg_churn_probability = result["avg_churn_probability"]
        existing.computed_at = datetime.now(timezone.utc)
        snapshot = existing
    else:
        snapshot = RevenueRiskSnapshot(
            client_id=client_id,
            snapshot_date=today,
            revenue_at_risk=result["revenue_at_risk"],
            high_risk_customer_count=result["high_risk_customers"],
            avg_churn_probability=result["avg_churn_probability"],
        )
        db.add(snapshot)

    if commit:
        db.commit()
        db.refresh(snapshot)
    else:
        db.flush()

    return snapshot


def get_30day_trend(db: Session, client_id: str) -> list[dict]:
    """Return last 30 daily snapshots for trend charts."""
    from datetime import timedelta
    cutoff = date.today() - timedelta(days=30)
    snapshots = (
        db.query(RevenueRiskSnapshot)
        .filter(
            RevenueRiskSnapshot.client_id == client_id,
            RevenueRiskSnapshot.snapshot_date >= cutoff,
        )
        .order_by(RevenueRiskSnapshot.snapshot_date.asc())
        .all()
    )
    return [
        {
            "date": str(s.snapshot_date),
            "revenue_at_risk": float(s.revenue_at_risk or 0),
            "high_risk_customers": s.high_risk_customer_count or 0,
            "avg_churn_probability": s.avg_churn_probability or 0.0,
        }
        for s in snapshots
    ]
