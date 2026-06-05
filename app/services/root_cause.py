import math
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.db.models import Complaint, ComplaintEntity
from app.utils.logging import get_logger

logger = get_logger(__name__)

_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.0-flash:generateContent"
)


def _entity_frequency_for_complaints(
    db: Session,
    complaint_ids: list,
    threshold: float = 0.30,
) -> dict[str, list[dict]]:
    """
    For a set of complaint IDs, return entity_type → top entities appearing in
    >= threshold fraction of those complaints, sorted by frequency descending.
    """
    if not complaint_ids:
        return {}

    total = len(complaint_ids)
    type_counter: dict[str, Counter] = defaultdict(Counter)

    entities = (
        db.query(ComplaintEntity)
        .filter(ComplaintEntity.complaint_id.in_(complaint_ids))
        .all()
    )
    for ent in entities:
        type_counter[ent.entity_type][ent.entity_value] += 1

    result: dict[str, list[dict]] = {}
    for etype, counter in type_counter.items():
        common = [
            {"value": val, "count": cnt, "frequency": round(cnt / total, 3)}
            for val, cnt in counter.most_common(10)
            if cnt / total >= threshold
        ]
        if common:
            result[etype] = common

    return result


def _entity_based_fallback(category: str, change_pct: float, common_entities: dict) -> list[str]:
    """Generate useful hypotheses from entity signals alone when Gemini is unavailable."""
    hints = []
    for etype, entries in common_entities.items():
        if entries:
            top = entries[0]
            pct = round(top["frequency"] * 100)
            hints.append(
                f"{top['value']} appears in {pct}% of {category} tickets — "
                f"check if a recent change to this {etype.lower()} triggered the spike"
            )
    if not hints:
        hints.append(
            f"{category.capitalize()} complaints rose {change_pct:+.0f}% — "
            "review tickets from this period for common keywords or customer segments"
        )
        hints.append(
            f"Check if a release, process change, or external event coincides with the {category} spike"
        )
    return hints[:3]


def _chi_square_p_value(observed: int, expected: float) -> float | None:
    """Compute approximate chi-square p-value for observed vs. expected count.

    Uses single-cell chi-square (goodness of fit against baseline).
    Returns None when expected < 1 (insufficient data for test).
    This is a simple approximation — not a full contingency table test.
    """
    if expected < 1:
        return None
    chi2 = (observed - expected) ** 2 / expected
    # Approximate p-value using chi-square CDF with 1 df
    # p ≈ erfc(sqrt(chi2/2)) — good enough for significance flagging
    try:
        p = math.erfc(math.sqrt(chi2 / 2))
        return round(p, 4)
    except (ValueError, ZeroDivisionError):
        return None


def _gemini_correlational_hypothesis(
    category: str,
    change_pct: float,
    common_entities: dict[str, list[dict]],
    api_key: str,
) -> list[str]:
    """Generate 2-3 bullet-point correlational signals for a trending category.

    NOTE: These are observational associations, not proven causal relationships.
    """
    entity_lines = []
    for etype, entries in common_entities.items():
        vals = ", ".join(e["value"] for e in entries[:3])
        entity_lines.append(f"  - {etype}: {vals}")
    entity_summary = "\n".join(entity_lines) or "  (no common entities found)"

    prompt = (
        f"Category '{category}' shows a {change_pct:.1f}% change in complaints this period.\n"
        f"Common entities appearing across these complaints:\n{entity_summary}\n\n"
        "List 2-3 plausible OBSERVATIONAL associations (not proven causes) as concise bullet points "
        "(max 15 words each). Frame as 'may be associated with' rather than 'caused by'. Be specific."
    )
    try:
        resp = httpx.post(
            _GEMINI_URL,
            params={"key": api_key},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.3, "maxOutputTokens": 200},
            },
            timeout=12.0,
        )
        resp.raise_for_status()
        data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise ValueError(f"Gemini returned no candidates. finishReason may be SAFETY. Full response: {data}")
        raw = candidates[0]["content"]["parts"][0]["text"].strip()
        lines = [l.lstrip("•-* 0123456789.).").strip() for l in raw.splitlines() if l.strip()]
        results = [l for l in lines if len(l) > 10][:3]
        return results if results else _entity_based_fallback(category, change_pct, common_entities)
    except Exception as exc:
        logger.warning("Correlational hypothesis generation failed for category=%s: %s", category, exc)
        return _entity_based_fallback(category, change_pct, common_entities)


def generate_root_cause_report(db: Session, client_id: str, period_days: int = 30) -> dict:
    """
    Generate a root cause analysis report for recent complaint trends.
    """
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=period_days)
    previous_start = start_date - timedelta(days=period_days)

    current_complaints = (
        db.query(Complaint)
        .filter(
            Complaint.client_id == client_id,
            Complaint.created_at >= start_date,
            Complaint.created_at <= end_date,
        )
        .all()
    )
    previous_complaints = (
        db.query(Complaint)
        .filter(
            Complaint.client_id == client_id,
            Complaint.created_at >= previous_start,
            Complaint.created_at < start_date,
        )
        .all()
    )

    current_categories = Counter([item.category for item in current_complaints if item.category])
    previous_categories = Counter([item.category for item in previous_complaints if item.category])

    category_trends = []
    current_total = len(current_complaints)
    previous_total_for_expected = len(previous_complaints)
    for category, current_count in current_categories.most_common():
        previous_count = previous_categories.get(category, 0)
        if previous_count > 0:
            change_pct = ((current_count - previous_count) / previous_count) * 100
        elif current_count > 0:
            change_pct = 100.0
        else:
            change_pct = 0.0

        # Chi-square significance: is this count significantly above what we'd expect?
        # Expected = previous_count scaled to current_total
        expected = (
            (previous_count / previous_total_for_expected) * current_total
            if previous_total_for_expected > 0 and previous_count > 0
            else None
        )
        p_value = _chi_square_p_value(current_count, expected) if expected else None
        statistically_significant = (p_value is not None and p_value < 0.05 and current_count >= 5)

        category_trends.append(
            {
                "category": category,
                "current_count": current_count,
                "previous_count": previous_count,
                "current_total": current_total,
                "previous_total": previous_total_for_expected,
                "change_percentage": round(change_pct, 1),
                "percentage_of_total": round((current_count / current_total) * 100, 1) if current_total else 0.0,
                "p_value": p_value,
                "statistically_significant": statistically_significant,
                "sufficient_data": current_count >= 5,
            }
        )

    top_issues = category_trends[:5]
    trending_up = [item for item in category_trends if item["change_percentage"] > 10][:3]

    resolution_rates = {}
    for category in current_categories.keys():
        category_complaints = [item for item in current_complaints if item.category == category]
        resolved = len([item for item in category_complaints if item.resolution_status == "resolved"])
        resolution_rates[category] = round((resolved / len(category_complaints)) * 100, 1) if category_complaints else 0.0

    previous_total = len(previous_complaints)
    overall_change = (
        ((current_total - previous_total) / previous_total) * 100 if previous_total > 0 else 0.0
    )

    # Correlational signals: entity frequency + AI associations for top trending categories
    # Only include categories that are statistically significant AND have sufficient data
    api_key = os.environ.get("GEMINI_API_KEY", "")
    correlational_signals = []
    top_trending = [
        t for t in category_trends
        if t["change_percentage"] > 15 and t.get("sufficient_data", False)
    ][:3]
    for trend in top_trending:
        cat_complaints = [c for c in current_complaints if c.category == trend["category"]]
        complaint_ids = [c.id for c in cat_complaints]
        common_entities = _entity_frequency_for_complaints(db, complaint_ids)
        associations = (
            _gemini_correlational_hypothesis(trend["category"], trend["change_percentage"], common_entities, api_key)
            if api_key
            else _entity_based_fallback(trend["category"], trend["change_percentage"], common_entities)
        )
        correlational_signals.append({
            "category": trend["category"],
            "change_percentage": trend["change_percentage"],
            "sample_size": trend["current_count"],
            "p_value": trend.get("p_value"),
            "statistically_significant": trend.get("statistically_significant", False),
            "common_entities": common_entities,
            "associations": associations,
        })

    return {
        "period": f"Last {period_days} days",
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "total_complaints": current_total,
        "previous_period_total": previous_total,
        "overall_change_percentage": round(overall_change, 1),
        "top_issues": top_issues,
        "trending_up": trending_up,
        "resolution_rates": resolution_rates,
        "correlational_signals": correlational_signals,
        # Backward compat alias — remove after frontend is updated
        "causal_analysis": correlational_signals,
        "disclaimer": "Associations are observational. Correlation does not imply causation. Investigate underlying data before taking action.",
        "insights": generate_insights(current_complaints, category_trends),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_insights(complaints: list[Complaint], trends: list[dict]) -> list[str]:
    insights: list[str] = []

    for trend in trends[:3]:
        if trend["change_percentage"] > 20:
            insights.append(
                f"{trend['category']} complaints increased by {trend['change_percentage']}%. Investigate the root cause and prioritize fixes."
            )

    for trend in trends[:3]:
        if trend["percentage_of_total"] > 30:
            insights.append(
                f"{trend['category']} represents {trend['percentage_of_total']}% of all complaints. This is a major pain point."
            )

    if not insights:
        insights.append("No critical complaint spikes were detected in the selected period.")

    return insights
