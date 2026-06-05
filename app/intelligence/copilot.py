"""AI Executive Copilot — RAG-based natural language Q&A over complaint data.

Context pipeline (in order of richness):
  1. Structured analytics  — ticket counts, resolution rate, SLA metrics
  2. SLA & resolution data — breach rate, avg resolution time, overdue count
  3. Team workload         — per-team ticket volume and backlog
  4. Assignment queue      — unassigned tickets, reply queue depth
  5. Revenue intelligence  — at-risk count, avg risk score, confidence tier
  6. Cluster summaries     — AI-grouped complaint themes
  7. Customer pulse        — sentiment trend, churn signals, spikes
  8. Recent complaint snip — PII-anonymised verbatim samples for grounding

Legal compliance (Legal_Requirements_Document.md §2.5 / §2.7):
  All complaint content sent to the Gemini API is passed through `anonymise_pii_for_ai`
  before the API call. No raw email addresses, phone numbers, PAN/Aadhaar, or
  bank account numbers are transmitted to Google's servers.
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
from app.db.models import (
    AIReplyQueue,
    Complaint,
    ComplaintCluster,
    CopilotQuery,
    Customer,
    Team,
    TeamMember,
)
from app.utils.logging import get_logger
from app.utils.prompt_safety import (
    UNTRUSTED_CONTENT_NOTE,
    anonymise_pii_for_ai,
    sanitize_copilot_query,
)

logger = get_logger(__name__)

_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.5-flash-lite:generateContent"
)

_SYSTEM_PROMPT = """You are an executive intelligence assistant for a B2B customer operations platform.

Your role is to help executives and support leaders understand:
- What issues are breaking, why, how widespread, and what to prioritise
- Financial and churn risk exposure
- SLA and compliance health
- Team performance and capacity
- What specific actions to take and in what order

Guidelines:
- Answer the question factually using ONLY the analytics data provided below.
- Be specific: cite numbers, percentages, team names, categories, and time periods.
- When recommending actions, name the team or person responsible and give a timeline.
- If a question asks about a specific customer by name/email, explain that individual
  customer PII is not shown here for privacy compliance; redirect to the Customer
  Intelligence module.
- If the data is insufficient to fully answer, say so and explain what additional
  data would help (e.g. "connect a Stripe integration to see revenue impact").
- Max 6 sentences. Use numbered bullet points only when listing multiple actions.
- Tone: direct, executive-level, no fluff.
"""


# ── context builders ──────────────────────────────────────────────────────────


def _get_structured_context(db: Session, client_id: str, days: int = 30) -> dict[str, Any]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    prev_cutoff = cutoff - timedelta(days=days)

    total = db.query(func.count(Complaint.id)).filter(
        Complaint.client_id == client_id,
        Complaint.created_at >= cutoff,
    ).scalar() or 0

    prev_total = db.query(func.count(Complaint.id)).filter(
        Complaint.client_id == client_id,
        Complaint.created_at >= prev_cutoff,
        Complaint.created_at < cutoff,
    ).scalar() or 0

    resolved = db.query(func.count(Complaint.id)).filter(
        Complaint.client_id == client_id,
        Complaint.created_at >= cutoff,
        Complaint.resolution_status == "resolved",
    ).scalar() or 0

    category_rows = (
        db.query(Complaint.category, func.count(Complaint.id).label("cnt"))
        .filter(Complaint.client_id == client_id, Complaint.created_at >= cutoff)
        .group_by(Complaint.category)
        .order_by(func.count(Complaint.id).desc())
        .limit(8)
        .all()
    )

    avg_urgency = db.query(func.avg(Complaint.urgency_score)).filter(
        Complaint.client_id == client_id,
        Complaint.created_at >= cutoff,
    ).scalar()

    sla_breached = db.query(func.count(Complaint.id)).filter(
        Complaint.client_id == client_id,
        Complaint.created_at >= cutoff,
        Complaint.sla_status == "breached",
    ).scalar() or 0

    open_tickets = db.query(func.count(Complaint.id)).filter(
        Complaint.client_id == client_id,
        Complaint.resolution_status != "resolved",
    ).scalar() or 0

    unassigned = db.query(func.count(Complaint.id)).filter(
        Complaint.client_id == client_id,
        Complaint.resolution_status != "resolved",
        Complaint.assigned_user_id.is_(None),
    ).scalar() or 0

    week_on_week_pct = round((total - prev_total) / max(prev_total, 1) * 100, 1)

    return {
        "period_days": days,
        "total_tickets": total,
        "prev_period_tickets": prev_total,
        "week_on_week_change_pct": week_on_week_pct,
        "resolved_tickets": resolved,
        "resolution_rate_pct": round(resolved / total * 100, 1) if total else 0.0,
        "open_tickets": open_tickets,
        "unassigned_open_tickets": unassigned,
        "sla_breached": sla_breached,
        "sla_breach_rate_pct": round(sla_breached / total * 100, 1) if total else 0.0,
        "avg_urgency_score": round(float(avg_urgency or 0), 2),
        "top_categories": [
            {"category": row.category or "unknown", "count": row.cnt,
             "pct": round(row.cnt / total * 100, 1) if total else 0}
            for row in category_rows
        ],
    }


def _get_sla_context(db: Session, client_id: str, days: int = 30) -> dict[str, Any]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    resolved_with_time = (
        db.query(Complaint.created_at, Complaint.resolved_at)
        .filter(
            Complaint.client_id == client_id,
            Complaint.created_at >= cutoff,
            Complaint.resolved_at.isnot(None),
        )
        .limit(500)
        .all()
    )

    resolution_times_hours: list[float] = []
    for row in resolved_with_time:
        if row.created_at and row.resolved_at:
            created = row.created_at.replace(tzinfo=timezone.utc) if row.created_at.tzinfo is None else row.created_at
            resolved = row.resolved_at.replace(tzinfo=timezone.utc) if row.resolved_at.tzinfo is None else row.resolved_at
            hours = (resolved - created).total_seconds() / 3600
            if 0 < hours < 720:  # ignore outliers > 30 days
                resolution_times_hours.append(hours)

    avg_resolution_h = round(sum(resolution_times_hours) / len(resolution_times_hours), 1) if resolution_times_hours else None

    overdue = db.query(func.count(Complaint.id)).filter(
        Complaint.client_id == client_id,
        Complaint.sla_status == "breached",
        Complaint.resolution_status != "resolved",
    ).scalar() or 0

    return {
        "avg_resolution_hours": avg_resolution_h,
        "currently_overdue_tickets": overdue,
    }


def _get_team_context(db: Session, client_id: str) -> list[dict]:
    teams = db.query(Team).filter(Team.client_id == client_id).all()
    result = []
    for team in teams:
        member_ids = [
            str(m.user_id)
            for m in db.query(TeamMember).filter(TeamMember.team_id == team.id).all()
        ]
        if not member_ids:
            continue
        open_count = db.query(func.count(Complaint.id)).filter(
            Complaint.client_id == client_id,
            Complaint.team_id == team.id,
            Complaint.resolution_status != "resolved",
        ).scalar() or 0
        result.append({
            "team": team.name,
            "members": len(member_ids),
            "open_tickets": open_count,
        })
    return sorted(result, key=lambda x: x["open_tickets"], reverse=True)


def _get_revenue_context(db: Session, client_id: str) -> dict[str, Any]:
    try:
        from app.services.revenue_risk import compute_revenue_at_risk
        risk = compute_revenue_at_risk(db, client_id)
        return {
            "high_risk_customer_count": risk["high_risk_customers"],
            "avg_risk_score": risk["avg_risk_score"],
            "revenue_at_risk": risk["revenue_at_risk"],
            "confidence": risk["confidence"],
            "has_revenue_data": risk["has_revenue_data"],
        }
    except Exception:
        return {}


def _get_reply_queue_context(db: Session, client_id: str) -> dict[str, Any]:
    pending = db.query(func.count(AIReplyQueue.id)).filter(
        AIReplyQueue.client_id == client_id,
        AIReplyQueue.status == "pending",
    ).scalar() or 0

    cutoff_week = datetime.now(timezone.utc) - timedelta(days=7)
    approved_this_week = db.query(func.count(AIReplyQueue.id)).filter(
        AIReplyQueue.client_id == client_id,
        AIReplyQueue.status == "approved",
        AIReplyQueue.created_at >= cutoff_week,
    ).scalar() or 0

    return {
        "pending_ai_reply_reviews": pending,
        "ai_replies_approved_this_week": approved_this_week,
    }


def _get_cluster_context(db: Session, client_id: str, days: int = 30) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    clusters = (
        db.query(ComplaintCluster)
        .filter(
            ComplaintCluster.client_id == client_id,
            ComplaintCluster.period_end >= cutoff.date(),
        )
        .order_by(ComplaintCluster.cluster_size.desc())
        .limit(6)
        .all()
    )
    return [
        {
            "theme": c.cluster_label,
            "count": c.cluster_size,
            "top_category": c.top_category,
            "summary": anonymise_pii_for_ai(c.summary or ""),
        }
        for c in clusters
    ]


def _get_pulse_context(db: Session, client_id: str) -> dict[str, Any]:
    try:
        pulse = generate_customer_pulse(db, client_id)
        spikes = detect_complaint_spikes(db, client_id, send_alert=False)
        return {
            "sentiment_trend": pulse.get("sentiment_trend", {}),
            "top_issues": pulse.get("top_issues", [])[:5],
            "churn_risk_customer_count": len(pulse.get("churn_risk_customers", [])),
            "suggested_actions": pulse.get("suggested_actions", []),
            "active_spikes": [
                {"type": s.get("type"), "severity": s.get("severity"), "category": s.get("category")}
                for s in spikes[:3]
            ],
        }
    except Exception:
        return {}


def _get_recent_complaints(db: Session, client_id: str, limit: int = 10) -> list[str]:
    """Return PII-anonymised complaint snippets for grounding."""
    complaints = (
        db.query(Complaint.summary, Complaint.category, Complaint.urgency_score, Complaint.sentiment)
        .filter(Complaint.client_id == client_id, Complaint.summary.isnot(None))
        .order_by(Complaint.created_at.desc())
        .limit(limit)
        .all()
    )
    snippets = []
    for c in complaints:
        safe_summary = anonymise_pii_for_ai(c.summary or "")
        sentiment_label = (
            "positive" if (c.sentiment or 0) > 0.2
            else "negative" if (c.sentiment or 0) < -0.2
            else "neutral"
        )
        snippets.append(
            f"[{c.category or 'unknown'}] urgency={(c.urgency_score or 0):.1f} "
            f"sentiment={sentiment_label}: {safe_summary}"
        )
    return snippets


# ── Gemini call ───────────────────────────────────────────────────────────────


def _call_gemini(prompt: str, api_key: str) -> str:
    resp = httpx.post(
        _GEMINI_URL,
        params={"key": api_key},
        json={
            "systemInstruction": {"parts": [{"text": _SYSTEM_PROMPT}]},
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 800},
        },
        timeout=25.0,
    )
    resp.raise_for_status()
    data = resp.json()
    candidates = data.get("candidates") or []
    if not candidates:
        raise ValueError(f"Gemini returned no candidates (promptFeedback={data.get('promptFeedback')})")
    candidate = candidates[0]
    content = candidate.get("content")
    if not content:
        raise ValueError(f"Gemini candidate has no content (finishReason={candidate.get('finishReason', 'UNKNOWN')})")
    return content["parts"][0]["text"].strip()


# ── main entry point ──────────────────────────────────────────────────────────


def answer_query(
    db: Session,
    client_id: str,
    question: str,
    user_id: str | None = None,
    days: int = 30,
) -> dict[str, Any]:
    """Answer an executive question. Returns {answer, sources, latency_ms}."""
    api_key = os.environ.get("GEMINI_API_KEY", "")
    t0 = time.perf_counter()

    # Gather all context in parallel-ish (sequential is fine; each is fast)
    structured = _get_structured_context(db, client_id, days)
    sla = _get_sla_context(db, client_id, days)
    teams = _get_team_context(db, client_id)
    revenue = _get_revenue_context(db, client_id)
    reply_q = _get_reply_queue_context(db, client_id)
    clusters = _get_cluster_context(db, client_id, days)
    pulse = _get_pulse_context(db, client_id)
    recent = _get_recent_complaints(db, client_id, limit=10)

    context_used = {
        "structured_analytics": structured,
        "sla_context": sla,
        "team_workload": teams,
        "revenue_intelligence": revenue,
        "reply_queue": reply_q,
        "cluster_themes": clusters,
        "live_pulse": pulse,
        "recent_tickets_sample": recent[:4],  # store fewer in DB for space
    }

    if not api_key:
        answer = (
            f"Unable to generate AI answer (GEMINI_API_KEY not set). "
            f"Analytics: {structured['total_tickets']} tickets in last {days} days, "
            f"resolution rate {structured['resolution_rate_pct']}%, "
            f"{structured['unassigned_open_tickets']} unassigned."
        )
        latency_ms = int((time.perf_counter() - t0) * 1000)
    else:
        safe_question = sanitize_copilot_query(question)

        # Build the context block sent to Gemini
        cluster_lines = "\n".join(
            f"  - '{c['theme']}' ({c['count']} tickets, cat={c['top_category']}): {c['summary']}"
            for c in clusters
        ) or "  No cluster data yet — run clustering on the Intelligence Hub."

        team_lines = "\n".join(
            f"  - {t['team']}: {t['open_tickets']} open tickets ({t['members']} agents)"
            for t in teams
        ) or "  No teams configured."

        ticket_lines = "\n".join(f"  - {s}" for s in recent) or "  No recent tickets."

        pulse_block = ""
        if pulse:
            trend = pulse.get("sentiment_trend", {})
            pulse_block = (
                f"\nCustomer pulse (last 7 days):\n"
                f"  - Sentiment direction: {trend.get('direction', 'unknown')} "
                f"({trend.get('previous_avg', 0):.2f} → {trend.get('current_avg', 0):.2f})\n"
                f"  - High churn risk customers: {pulse.get('churn_risk_customer_count', 0)}\n"
            )
            if pulse.get("active_spikes"):
                for spike in pulse["active_spikes"]:
                    pulse_block += (
                        f"  - SPIKE: {spike.get('category', 'unknown')} "
                        f"(severity={spike.get('severity', '?')})\n"
                    )
            if pulse.get("top_issues"):
                issue_lines = ", ".join(
                    f"{i['category']} ({i['count']}x)"
                    for i in pulse["top_issues"][:4]
                )
                pulse_block += f"  - Top issues: {issue_lines}\n"

        revenue_block = ""
        if revenue:
            if revenue.get("has_revenue_data"):
                revenue_block = (
                    f"\nRevenue intelligence (confidence={revenue.get('confidence', '?')}):\n"
                    f"  - High-churn customers: {revenue.get('high_risk_customer_count', 0)}\n"
                    f"  - Estimated revenue at risk: ₹{revenue.get('revenue_at_risk', 0):,.0f}\n"
                    f"  - Avg churn risk score: {revenue.get('avg_risk_score', 0):.0f}/100\n"
                )
            else:
                revenue_block = (
                    f"\nRevenue intelligence:\n"
                    f"  - {revenue.get('high_risk_customer_count', 0)} customers at high churn risk "
                    f"(avg score {revenue.get('avg_risk_score', 0):.0f}/100)\n"
                    f"  - No revenue integration connected — financial impact unknown\n"
                )

        reply_block = (
            f"\nAI Reply Queue:\n"
            f"  - {reply_q.get('pending_ai_reply_reviews', 0)} drafts awaiting human review\n"
            f"  - {reply_q.get('ai_replies_approved_this_week', 0)} AI replies approved this week\n"
        ) if reply_q else ""

        prompt = (
            f"{UNTRUSTED_CONTENT_NOTE}"
            f"=== ANALYTICS (last {days} days) ===\n"
            f"{json.dumps(structured, indent=2)}\n\n"
            f"=== SLA & RESOLUTION ===\n"
            f"  - Avg resolution time: {sla.get('avg_resolution_hours', 'unknown')} hours\n"
            f"  - Currently overdue (breached SLA, not resolved): {sla.get('currently_overdue_tickets', 0)}\n"
            f"{pulse_block}"
            f"{revenue_block}"
            f"{reply_block}"
            f"\n=== TEAM WORKLOAD ===\n{team_lines}\n\n"
            f"=== COMPLAINT CLUSTERS (top themes) ===\n{cluster_lines}\n\n"
            f"=== RECENT TICKET SAMPLES (PII-anonymised) ===\n{ticket_lines}\n\n"
            f"=== QUESTION ===\n{safe_question}"
        )

        try:
            answer = _call_gemini(prompt, api_key)
        except Exception as exc:
            logger.warning("Copilot Gemini call failed: %s", exc)
            top_cat = (structured["top_categories"][0]["category"] if structured["top_categories"] else "none")
            answer = (
                f"I couldn't reach the AI model right now ({type(exc).__name__}). "
                f"Based on raw data: {structured['total_tickets']} tickets in {days} days "
                f"(resolution {structured['resolution_rate_pct']}%), "
                f"{structured['sla_breached']} SLA breaches, "
                f"{structured['unassigned_open_tickets']} unassigned. "
                f"Top issue: {top_cat}."
            )

        latency_ms = int((time.perf_counter() - t0) * 1000)

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
