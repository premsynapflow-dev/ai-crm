"""AI Executive Copilot — RAG-based natural language Q&A over complaint data.

Pipeline:
  1. Structured context: SQL analytics (complaint counts, category trends, top entities)
  2. Semantic context: fetch complaint cluster summaries + recent complaint snippets
  3. Gemini generation: answer question grounded in retrieved context
  4. Persist query + response to copilot_queries table
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.analytics.customer_pulse import detect_complaint_spikes, generate_customer_pulse
from app.db.models import Complaint, ComplaintCluster, CopilotQuery
from app.utils.logging import get_logger

logger = get_logger(__name__)

_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.0-flash:generateContent"
)

_SYSTEM_PROMPT = (
    "You are an executive intelligence assistant for a customer operations platform. "
    "Your job is to help executives understand: what is broken, why it is broken, "
    "how much it costs, and what to do about it. "
    "Answer the question factually using ONLY the analytics data provided below. "
    "Be concise (max 5 sentences). Cite specific numbers when available. "
    "When recommending actions, be specific about teams, priorities, and timelines. "
    "If the data is insufficient to answer, say so explicitly."
)


def _get_structured_context(db: Session, client_id: str, days: int = 30) -> dict[str, Any]:
    """Pull structured complaint analytics for the context window."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    total = db.query(func.count(Complaint.id)).filter(
        Complaint.client_id == client_id,
        Complaint.created_at >= cutoff,
    ).scalar() or 0

    resolved = db.query(func.count(Complaint.id)).filter(
        Complaint.client_id == client_id,
        Complaint.created_at >= cutoff,
        Complaint.resolution_status == "resolved",
    ).scalar() or 0

    # Category breakdown
    category_rows = (
        db.query(Complaint.category, func.count(Complaint.id).label("cnt"))
        .filter(Complaint.client_id == client_id, Complaint.created_at >= cutoff)
        .group_by(Complaint.category)
        .order_by(func.count(Complaint.id).desc())
        .limit(5)
        .all()
    )

    # Average urgency
    avg_urgency = db.query(func.avg(Complaint.urgency_score)).filter(
        Complaint.client_id == client_id,
        Complaint.created_at >= cutoff,
    ).scalar()

    # SLA breach count
    sla_breached = db.query(func.count(Complaint.id)).filter(
        Complaint.client_id == client_id,
        Complaint.created_at >= cutoff,
        Complaint.sla_status == "breached",
    ).scalar() or 0

    return {
        "period_days": days,
        "total_complaints": total,
        "resolved_complaints": resolved,
        "resolution_rate": round(resolved / total * 100, 1) if total else 0.0,
        "sla_breached": sla_breached,
        "avg_urgency_score": round(float(avg_urgency or 0), 2),
        "top_categories": [
            {"category": row.category or "unknown", "count": row.cnt}
            for row in category_rows
        ],
    }


def _get_cluster_context(db: Session, client_id: str, days: int = 30) -> list[dict]:
    """Fetch recent cluster summaries for semantic context."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    clusters = (
        db.query(ComplaintCluster)
        .filter(
            ComplaintCluster.client_id == client_id,
            ComplaintCluster.period_end >= cutoff.date(),
        )
        .order_by(ComplaintCluster.cluster_size.desc())
        .limit(5)
        .all()
    )
    return [
        {
            "cluster_label": c.cluster_label,
            "size": c.cluster_size,
            "summary": c.summary,
            "top_category": c.top_category,
        }
        for c in clusters
    ]


def _get_pulse_context(db: Session, client_id: str) -> dict[str, Any]:
    """Get live pulse snapshot: sentiment trend, top issues, churn risk, spikes."""
    try:
        pulse = generate_customer_pulse(db, client_id)
        spikes = detect_complaint_spikes(db, client_id, send_alert=False)
        return {
            "sentiment_trend": pulse.get("sentiment_trend", {}),
            "top_issues": pulse.get("top_issues", [])[:5],
            "churn_risk_customer_count": len(pulse.get("churn_risk_customers", [])),
            "suggested_actions": pulse.get("suggested_actions", []),
            "active_spikes": [
                {"type": s.get("type"), "severity": s.get("severity")}
                for s in spikes[:3]
            ],
        }
    except Exception:
        return {}


def _get_recent_complaints(db: Session, client_id: str, limit: int = 8) -> list[str]:
    """Fetch recent complaint summaries for direct grounding."""
    complaints = (
        db.query(Complaint.summary, Complaint.category, Complaint.urgency_score)
        .filter(Complaint.client_id == client_id, Complaint.summary.isnot(None))
        .order_by(Complaint.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        f"[{c.category or 'unknown'}] {c.summary} (urgency={c.urgency_score:.1f})"
        for c in complaints
    ]


def _call_gemini(prompt: str, api_key: str) -> str:
    resp = httpx.post(
        _GEMINI_URL,
        params={"key": api_key},
        json={
            "systemInstruction": {"parts": [{"text": _SYSTEM_PROMPT}]},
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 400},
        },
        timeout=15.0,
    )
    resp.raise_for_status()
    return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()


def answer_query(
    db: Session,
    client_id: str,
    question: str,
    user_id: str | None = None,
    days: int = 30,
) -> dict[str, Any]:
    """
    Main entry point. Returns {answer, sources, latency_ms}.
    Persists the query to copilot_queries table.
    """
    api_key = os.environ.get("GEMINI_API_KEY", "")

    t0 = time.perf_counter()

    structured = _get_structured_context(db, client_id, days)
    clusters = _get_cluster_context(db, client_id, days)
    recent = _get_recent_complaints(db, client_id)
    pulse = _get_pulse_context(db, client_id)

    context_used = {
        "structured_analytics": structured,
        "cluster_summaries": clusters,
        "recent_complaints_sample": recent[:3],
        "live_pulse": pulse,
    }

    if not api_key:
        answer = (
            f"Unable to generate AI answer (GEMINI_API_KEY not set). "
            f"Analytics: {structured['total_complaints']} complaints in last {days} days, "
            f"resolution rate {structured['resolution_rate']}%."
        )
        latency_ms = int((time.perf_counter() - t0) * 1000)
    else:
        cluster_lines = "\n".join(
            f"  - Cluster '{c['cluster_label']}' ({c['size']} complaints, top: {c['top_category']}): {c['summary']}"
            for c in clusters
        ) or "  No clusters computed yet."

        complaint_lines = "\n".join(f"  - {s}" for s in recent) or "  No recent complaints."

        # Pulse context block
        pulse_lines = ""
        if pulse:
            trend = pulse.get("sentiment_trend", {})
            pulse_lines = (
                f"\nLive pulse (last 7 days):\n"
                f"  - Sentiment: {trend.get('direction', 'unknown')} "
                f"({trend.get('previous_avg', 0):.2f} → {trend.get('current_avg', 0):.2f})\n"
                f"  - Customers at churn risk: {pulse.get('churn_risk_customer_count', 0)}\n"
            )
            if pulse.get("active_spikes"):
                pulse_lines += f"  - Active spikes: {json.dumps(pulse['active_spikes'])}\n"
            if pulse.get("top_issues"):
                top = pulse["top_issues"][:3]
                issue_summary = ", ".join(
                    "{} ({}x)".format(i["category"], i["count"]) for i in top
                )
                pulse_lines += f"  - Top issues: {issue_summary}\n"

        prompt = (
            f"Analytics (last {days} days):\n"
            f"{json.dumps(structured, indent=2)}\n"
            f"{pulse_lines}\n"
            f"Complaint cluster summaries:\n{cluster_lines}\n\n"
            f"Recent complaint samples:\n{complaint_lines}\n\n"
            f"Question: {question}"
        )

        try:
            answer = _call_gemini(prompt, api_key)
        except Exception as exc:
            logger.exception("Copilot Gemini call failed: %s", exc)
            answer = "Unable to generate answer due to an AI service error."

        latency_ms = int((time.perf_counter() - t0) * 1000)

    # Persist query
    record = CopilotQuery(
        client_id=client_id,
        user_id=user_id,
        query=question,
        response=answer,
        context_used=context_used,
        latency_ms=latency_ms,
    )
    db.add(record)
    try:
        db.commit()
        db.refresh(record)
    except Exception:
        db.rollback()

    return {
        "id": str(record.id),
        "answer": answer,
        "sources": context_used,
        "latency_ms": latency_ms,
    }
