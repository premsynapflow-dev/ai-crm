"""Revenue at Risk — three-tier system.

Tier 3 (HIGH confidence): actual_customer_value set via integration (Stripe, Razorpay, etc.)
Tier 2 (MEDIUM confidence): estimated_customer_value set manually or imported
Tier 1 (LOW confidence): no revenue data — returns Customer Risk Index (0–100 score), not ₹

Rules:
- NEVER compute LTV from ticket counts or SynapFlow plan pricing
- Always return 'confidence' and 'estimation_method' so callers know whether the number is real
- When confidence = 'low', revenue_at_risk = 0 and callers should show Risk Index instead
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from statistics import mean
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Customer, RevenueRiskSnapshot
from app.intelligence.calibration import calibrate_churn_probability
from app.intelligence.constants import RISK_HIGH_THRESHOLD
from app.utils.logging import get_logger

logger = get_logger(__name__)


def _get_ltv(customer: Customer) -> tuple[float, str]:
    """Return (ltv, source) for the customer.

    source is 'actual', 'estimated', or 'unknown'.
    Never falls back to ticket-count math — that produces fake precision.
    """
    if customer.actual_customer_value and customer.actual_customer_value > 0:
        return float(customer.actual_customer_value), "actual"
    if customer.estimated_customer_value and customer.estimated_customer_value > 0:
        return float(customer.estimated_customer_value), "estimated"
    return 0.0, "unknown"


def _overall_confidence(sources: list[str]) -> tuple[str, str]:
    """Determine aggregate confidence and estimation_method from per-customer sources."""
    if not sources:
        return "low", "behavioral_model_only"
    actual = sources.count("actual")
    estimated = sources.count("estimated")
    total = len(sources)
    if actual == total:
        return "high", "actual_revenue"
    if actual > 0 or estimated / total >= 0.5:
        return "medium", "mixed_revenue_and_estimates"
    if estimated > 0:
        return "medium", "estimated_value"
    return "low", "behavioral_model_only"


def compute_data_coverage(db: Session, client_id: str) -> dict[str, Any]:
    """Return revenue data coverage stats across all master customer records."""
    from datetime import timezone
    all_customers = (
        db.query(Customer)
        .filter(Customer.client_id == client_id, Customer.is_master.is_(True))
        .all()
    )
    total = len(all_customers)
    if total == 0:
        return {"actual": 0, "estimated": 0, "unknown": 0, "total": 0, "coverage_pct": 0.0,
                "risk_score_freshness": {"computed_today": 0, "computed_this_week": 0, "stale_over_7d": 0}}

    from datetime import datetime, timedelta
    actual = sum(1 for c in all_customers if (c.actual_customer_value or 0) > 0
                 or (c.customer_lifetime_revenue or 0) > 0)
    estimated = sum(1 for c in all_customers
                    if (c.actual_customer_value or 0) == 0
                    and (c.customer_lifetime_revenue or 0) == 0
                    and ((c.estimated_customer_value or 0) > 0
                         or (c.annual_contract_value or 0) > 0
                         or (c.monthly_recurring_value or 0) > 0))
    unknown = total - actual - estimated

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)
    computed_today = sum(1 for c in all_customers if c.risk_score_computed_at and c.risk_score_computed_at >= today_start)
    computed_week = sum(1 for c in all_customers if c.risk_score_computed_at and c.risk_score_computed_at >= week_ago)
    stale = sum(1 for c in all_customers if not c.risk_score_computed_at or c.risk_score_computed_at < week_ago)

    return {
        "actual": actual,
        "estimated": estimated,
        "unknown": unknown,
        "total": total,
        "coverage_pct": round((actual + estimated) / total * 100, 1),
        "risk_score_freshness": {
            "computed_today": computed_today,
            "computed_this_week": computed_week,
            "stale_over_7d": stale,
        },
    }


def compute_revenue_at_risk(db: Session, client_id: str) -> dict[str, Any]:
    """Compute current revenue-at-risk for all high-risk customers.

    Returns:
        revenue_at_risk          — ₹ total (0 when confidence is 'low')
        high_risk_customers      — count of customers with churn_risk_score >= 70
        avg_risk_score           — average risk score (0–100) across high-risk customers
        avg_churn_probability    — calibrated probability (NOT score/100)
        confidence               — 'high' | 'medium' | 'low'
        estimation_method        — textual description of the data tier used
        has_revenue_data         — True when at least one customer has actual/estimated value
        breakdown                — top-10 highest-risk customers with per-customer confidence
        data_coverage            — coverage stats across ALL customers (not just high-risk)
    """
    high_risk = (
        db.query(Customer)
        .filter(
            Customer.client_id == client_id,
            Customer.churn_risk_score >= RISK_HIGH_THRESHOLD,
            Customer.is_master.is_(True),
        )
        .order_by(Customer.churn_risk_score.desc())
        .all()
    )

    coverage = compute_data_coverage(db, client_id)

    if not high_risk:
        return {
            "revenue_at_risk": 0.0,
            "high_risk_customers": 0,
            "avg_risk_score": 0.0,
            "avg_churn_probability": 0.0,
            "confidence": "low",
            "estimation_method": "behavioral_model_only",
            "has_revenue_data": False,
            "breakdown": [],
            "data_coverage": coverage,
        }

    total_risk = 0.0
    total_customer_value = 0.0
    breakdown = []
    sources: list[str] = []

    for customer in high_risk:
        ltv, source = _get_ltv(customer)
        sources.append(source)
        churn_prob = calibrate_churn_probability(customer.churn_risk_score or 0)
        risk = round(ltv * churn_prob, 2) if ltv > 0 else 0.0
        total_risk += risk
        total_customer_value += ltv
        breakdown.append({
            "customer_id": str(customer.id),
            "email": customer.primary_email,
            "risk_score": customer.churn_risk_score,
            "churn_probability": churn_prob,
            "ltv": round(ltv, 2),
            "revenue_at_risk": risk,
            "value_source": source,
            "confidence": "high" if source == "actual" else ("medium" if source == "estimated" else "low"),
        })

    confidence, estimation_method = _overall_confidence(sources)
    risk_scores = [c.churn_risk_score for c in high_risk]
    avg_risk = round(mean(risk_scores), 1)
    avg_churn_prob = calibrate_churn_probability(avg_risk)

    return {
        "revenue_at_risk": round(total_risk, 2),
        "total_customer_value": round(total_customer_value, 2),
        "pct_at_risk": round((total_risk / total_customer_value * 100), 1) if total_customer_value > 0 else 0.0,
        "high_risk_customers": len(high_risk),
        "avg_risk_score": avg_risk,
        "avg_churn_probability": avg_churn_prob,
        "confidence": confidence,
        "estimation_method": estimation_method,
        "has_revenue_data": any(s != "unknown" for s in sources),
        "breakdown": breakdown[:10],
        "data_coverage": coverage,
    }


def compute_retention_probability(customer: Customer) -> float:
    """Simplified retention probability — kept for backward compat.

    Returns compute_retention_likelihood()['retention_likelihood'].
    """
    return compute_retention_likelihood(customer)["retention_likelihood"]


def compute_retention_likelihood(customer: Customer, db: Session | None = None) -> dict:
    """Standalone retention model using positive-signal scoring.

    Unlike compute_retention_probability (which was 1 - churn), this model
    has its own set of positive driving signals:

      +0.10  high resolution rate (>85% of past tickets resolved)
      +0.08  positive interactions in last 90d (> 2 tickets with positive sentiment)
      +0.08  high satisfaction average (avg CSAT >= 4.0)
      +0.05  no recent complaints (no tickets in last 60 days)
      +0.08  long-tenure customer (>365 days since first interaction)

    Detractors:
      -0.20  active escalation (churn_risk_score >= RISK_HIGH_THRESHOLD)
      -0.15  very high churn risk

    Returns dict with retention_likelihood, retention_drivers, confidence,
    and recommended_actions.
    """
    score = 0.50  # neutral base
    drivers: list[str] = []
    detractors: list[str] = []

    total = int(customer.total_tickets or 0)
    resolved = total - int(customer.open_tickets or 0)
    if total >= 5 and resolved / total > 0.85:
        score += 0.10
        drivers.append("high resolution rate")

    if (customer.avg_satisfaction_score or 0) >= 4.0:
        score += 0.08
        drivers.append("high satisfaction scores")

    tenure = int(customer.tenure_days or 0)
    if tenure > 365:
        score += 0.08
        drivers.append("long-term customer (>1 year)")

    if int(customer.total_interactions or 0) > 5:
        score += 0.05
        drivers.append("high engagement history")

    # Detractors
    from app.intelligence.constants import RISK_HIGH_THRESHOLD
    churn_score = float(customer.churn_risk_score or 0)
    if churn_score >= RISK_HIGH_THRESHOLD:
        score -= 0.20
        detractors.append("high behavioral risk score")
    elif churn_score >= 50:
        score -= 0.10
        detractors.append("elevated behavioral risk")

    if int(customer.open_tickets or 0) >= 3:
        score -= 0.08
        detractors.append("multiple unresolved tickets")

    retention_likelihood = round(min(0.95, max(0.05, score)), 3)

    # Confidence: "medium" always — "high" requires actual outcome data to validate
    confidence = "medium"

    # Simple recommended actions based on risk level
    recommended_actions: list[str] = []
    if retention_likelihood < 0.40:
        recommended_actions = [
            "Escalate to senior support agent",
            "Offer proactive resolution or goodwill credit",
            "Schedule executive callback",
        ]
    elif retention_likelihood < 0.65:
        recommended_actions = [
            "Send proactive check-in message",
            "Prioritise resolution of open tickets",
        ]
    else:
        recommended_actions = ["Maintain current service quality"]

    return {
        "retention_likelihood": retention_likelihood,
        "retention_drivers": drivers,
        "retention_detractors": detractors,
        "confidence": confidence,
        "recommended_actions": recommended_actions,
    }


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
