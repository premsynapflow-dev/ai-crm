"""Executive Intelligence Dashboard — GET /api/v1/executive/summary."""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.models import Client, Complaint, Customer
from app.db.session import get_db
from app.dependencies.auth import require_api_key
from app.intelligence.calibration import calibrate_churn_probability
from app.intelligence.constants import RISK_HIGH_THRESHOLD
from app.services.root_cause import generate_root_cause_report
from app.utils.logging import get_logger

router = APIRouter(prefix="/api/v1/executive", tags=["executive"])
logger = get_logger(__name__)

_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.5-flash-lite:generateContent"
)

# In-memory 1h cache per client: {client_id: (cached_at, payload)}
_CACHE: dict[str, tuple[datetime, dict]] = {}
_CACHE_TTL_SECONDS = 3600


def _get_cached(client_id: str) -> dict | None:
    entry = _CACHE.get(str(client_id))
    if entry and (datetime.now(timezone.utc) - entry[0]).total_seconds() < _CACHE_TTL_SECONDS:
        return entry[1]
    return None


def _set_cache(client_id: str, payload: dict) -> None:
    _CACHE[str(client_id)] = (datetime.now(timezone.utc), payload)


def _compute_revenue_at_risk(db: Session, client_id: Any, days: int) -> dict:
    high_risk = (
        db.query(Customer)
        .filter(
            Customer.client_id == client_id,
            Customer.churn_risk_score >= RISK_HIGH_THRESHOLD,
        )
        .all()
    )
    total_risk = 0.0
    has_revenue_data = False
    for c in high_risk:
        ltv = float(c.lifetime_value) if c.lifetime_value else 0.0
        if ltv > 0:
            has_revenue_data = True
            prob = calibrate_churn_probability(c.churn_risk_score or 0)
            total_risk += ltv * prob

    return {
        "revenue_at_risk": round(total_risk, 2),
        "high_risk_customers": len(high_risk),
        "has_revenue_data": has_revenue_data,
    }


def _generate_narrative(metrics: dict, client_name: str, api_key: str) -> str:
    if not api_key:
        return _fallback_narrative(metrics)

    trending = metrics.get("trending_up", [])
    top_issue = trending[0]["category"] if trending else (
        metrics.get("top_issues", [{}])[0].get("category", "unknown") if metrics.get("top_issues") else "unknown"
    )
    change_pct = trending[0]["change_percentage"] if trending else metrics.get("overall_change_percentage", 0)
    total = metrics.get("total_complaints", 0)
    revenue_at_risk = metrics.get("revenue_at_risk", 0)
    insights = metrics.get("insights", [])

    prompt = f"""You are an executive intelligence assistant for {client_name}.
Based on the following complaint analytics data, write a concise 3-sentence executive briefing.

Data:
- Total complaints this period: {total}
- Period-over-period change: {change_pct:+.1f}%
- Top trending issue: {top_issue} (+{change_pct:.1f}%)
- Revenue at risk from high-churn customers: ₹{revenue_at_risk:,.0f}
- Current insights: {json.dumps(insights)}

Answer these three questions in three sentences:
1. What is the biggest operational problem?
2. What is the likely root cause?
3. What is the recommended action?

Be specific with numbers. Use business language. No bullet points."""

    try:
        resp = httpx.post(
            _GEMINI_URL,
            params={"key": api_key},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 300},
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as exc:
        logger.warning("Executive narrative generation failed: %s", exc)
        return _fallback_narrative(metrics)


def _fallback_narrative(metrics: dict) -> str:
    trending = metrics.get("trending_up", [])
    top = trending[0] if trending else {}
    issue = top.get("category", "general")
    pct = top.get("change_percentage", 0)
    total = metrics.get("total_complaints", 0)
    return (
        f"There are {total} complaints this period, with {issue} issues trending up {pct:.0f}%. "
        f"This suggests an underlying operational issue in the {issue} area. "
        f"Recommend immediate review of {issue}-related processes and team escalation."
    )


def build_digest_payload(db: Session, client: Client, days: int = 7) -> dict:
    """Compose root-cause + revenue + Gemini narrative into a digest dict.

    Reused by both the executive_summary endpoint and ArtifactService.
    Returns a plain dict (no cache, no HTTP concerns).
    """
    from app.services.revenue_risk import compute_data_coverage
    root_cause = generate_root_cause_report(db, str(client.id), period_days=days)
    revenue = _compute_revenue_at_risk(db, client.id, days)
    coverage = compute_data_coverage(db, str(client.id))

    metrics = {**root_cause, **revenue, "revenue_coverage_pct": coverage["coverage_pct"]}

    api_key = os.environ.get("GEMINI_API_KEY", "")
    narrative = _generate_narrative(metrics, client.name or "your company", api_key)

    trending = root_cause.get("trending_up", [])
    top_issue = trending[0] if trending else (root_cause.get("top_issues") or [{}])[0]

    return {
        "period_days": days,
        "what_broke": {
            "issue": top_issue.get("category", "No significant issues detected"),
            "count": top_issue.get("current_count", 0),
            "change_pct": top_issue.get("change_percentage", 0),
        },
        "why": {
            "root_cause_insights": root_cause.get("insights", []),
            "trending_categories": root_cause.get("trending_up", [])[:3],
        },
        "cost": {
            "revenue_at_risk": revenue["revenue_at_risk"],
            "high_risk_customers": revenue["high_risk_customers"],
            "has_revenue_data": revenue.get("has_revenue_data", False),
            "revenue_coverage_pct": coverage["coverage_pct"],
            "currency": "INR",
        },
        "action": {
            "narrative": narrative,
            "top_recommendations": root_cause.get("insights", [])[:2],
        },
        "full_analytics": {
            "total_complaints": root_cause.get("total_complaints", 0),
            "previous_period_total": root_cause.get("previous_period_total", 0),
            "overall_change_pct": root_cause.get("overall_change_percentage", 0),
            "top_issues": root_cause.get("top_issues", [])[:5],
            "resolution_rates": root_cause.get("resolution_rates", {}),
        },
        "correlational_signals": root_cause.get(
            "correlational_signals", root_cause.get("causal_analysis", [])
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/summary")
async def executive_summary(
    days: int = Query(7, ge=1, le=90, description="Analysis window in days"),
    force_refresh: bool = Query(False),
    client: Client = Depends(require_api_key),
    db: Session = Depends(get_db),
):
    cache_key = f"{client.id}:{days}"
    if not force_refresh:
        cached = _get_cached(cache_key)
        if cached:
            return {**cached, "cached": True}

    payload = build_digest_payload(db, client, days=days)
    _set_cache(cache_key, payload)
    return {**payload, "cached": False}
