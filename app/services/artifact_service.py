"""ArtifactService — generate, review, and deliver Weekly Operational Digests."""
from __future__ import annotations

import textwrap
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Artifact, Client
from app.integrations.email import send_email
from app.utils.logging import get_logger

logger = get_logger(__name__)


def _settings():
    from app.config import get_settings
    return get_settings()


class ArtifactService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def generate_weekly_digest(
        self,
        client: Client,
        period_end: date | None = None,
        recipient: str | None = None,
        commit: bool = True,
    ) -> Artifact:
        """Generate (or regenerate) this week's digest for client.

        Idempotent: updates the existing row if one exists for this period_start,
        so n8n can safely call this endpoint more than once.
        """
        from app.api.v1.executive_summary import build_digest_payload

        period_end = period_end or date.today()
        period_start = period_end - timedelta(days=7)

        payload = build_digest_payload(self.db, client, days=7)

        narrative = payload.get("action", {}).get("narrative", "")
        title = (
            f"Weekly Operational Digest — "
            f"{period_start:%b %d}–{period_end:%b %d, %Y}"
        )
        summary = (narrative.split(". ")[0] + ".") if narrative else title

        artifact = self._upsert(
            client_id=client.id,
            artifact_type="weekly_operational_digest",
            period_start=period_start,
            period_end=period_end,
            title=title,
            summary=summary,
            sections_json=payload,
            model_used="gemini-2.5-flash-lite",
            recipient=recipient,
        )
        if commit:
            self.db.commit()
        return artifact

    def _upsert(
        self,
        *,
        client_id: Any,
        artifact_type: str,
        period_start: date,
        period_end: date,
        title: str,
        summary: str,
        sections_json: dict,
        model_used: str | None = None,
        recipient: str | None = None,
    ) -> Artifact:
        existing = (
            self.db.query(Artifact)
            .filter(
                Artifact.client_id == client_id,
                Artifact.artifact_type == artifact_type,
                Artifact.period_start == period_start,
            )
            .first()
        )
        if existing:
            existing.title = title
            existing.summary = summary
            existing.sections_json = sections_json
            existing.model_used = model_used
            if recipient:
                existing.recipient = recipient
            # Reset to draft so analyst reviews the refreshed content
            if existing.status in ("draft",):
                pass  # stay draft
            # Don't downgrade approved/delivered artifacts
            return existing

        artifact = Artifact(
            id=uuid.uuid4(),
            client_id=client_id,
            artifact_type=artifact_type,
            period_start=period_start,
            period_end=period_end,
            title=title,
            summary=summary,
            sections_json=sections_json,
            status="draft",
            model_used=model_used,
            recipient=recipient,
            generation_metadata={},
        )
        self.db.add(artifact)
        return artifact

    # ------------------------------------------------------------------
    # Review lifecycle
    # ------------------------------------------------------------------

    def approve(
        self,
        artifact_id: str,
        reviewer_email: str,
        edited_body: str | None = None,
        commit: bool = True,
    ) -> Artifact:
        artifact = self._get_or_404(artifact_id)
        artifact.status = "approved"
        artifact.reviewed_by = reviewer_email
        artifact.reviewed_at = datetime.now(timezone.utc)
        if edited_body is not None:
            artifact.edited_body = edited_body
        if commit:
            self.db.commit()
        return artifact

    def reject(
        self,
        artifact_id: str,
        reviewer_email: str,
        reason: str,
        commit: bool = True,
    ) -> Artifact:
        artifact = self._get_or_404(artifact_id)
        artifact.status = "rejected"
        artifact.reviewed_by = reviewer_email
        artifact.reviewed_at = datetime.now(timezone.utc)
        artifact.rejection_reason = reason
        if commit:
            self.db.commit()
        return artifact

    # ------------------------------------------------------------------
    # Rendering + Delivery
    # ------------------------------------------------------------------

    def render_email(self, artifact: Artifact) -> tuple[str, str]:
        """Return (subject, html_body) for delivery."""
        subject = artifact.title

        if artifact.edited_body:
            body_html = _markdown_to_simple_html(artifact.edited_body)
        else:
            body_html = _render_sections(artifact.sections_json)

        base_url = _settings().app_base_url.rstrip("/")
        acted_url = f"{base_url}/api/v1/artifacts/{artifact.id}/event?type=acted"

        html = f"""
<html><body style="font-family:sans-serif;max-width:640px;margin:0 auto;padding:24px;color:#111">
<h2 style="margin-bottom:4px">{artifact.title}</h2>
<p style="color:#666;font-size:13px;margin-top:0">{artifact.period_start} – {artifact.period_end}</p>
<hr style="border:none;border-top:1px solid #eee;margin:16px 0">
{body_html}
<hr style="border:none;border-top:1px solid #eee;margin:24px 0">
<p style="font-size:13px;color:#666">
  Did you act on a recommendation from this digest?
  <a href="{acted_url}" style="color:#4f46e5">Click here to let us know</a> — it takes one second
  and helps us improve future digests.
</p>
</body></html>
""".strip()
        return subject, html

    def deliver(
        self,
        artifact: Artifact,
        recipient: str | None = None,
        commit: bool = True,
    ) -> Artifact:
        to = recipient or artifact.recipient
        if not to:
            raise ValueError(f"No recipient set for artifact {artifact.id}")

        subject, body = self.render_email(artifact)
        send_email(to, subject, body, is_marketing=False)

        artifact.status = "delivered"
        artifact.delivered_at = datetime.now(timezone.utc)
        artifact.delivery_channel = "email"
        artifact.recipient = to
        if commit:
            self.db.commit()
        logger.info("Artifact %s delivered to %s", artifact.id, to)
        return artifact

    def record_event(
        self,
        artifact_id: str,
        event_type: str,
        commit: bool = True,
    ) -> Artifact:
        artifact = self._get_or_404(artifact_id)
        now = datetime.now(timezone.utc)
        if event_type == "opened" and artifact.opened_at is None:
            artifact.opened_at = now
        elif event_type == "acted" and artifact.acted_at is None:
            artifact.acted_at = now
            if artifact.opened_at is None:
                artifact.opened_at = now
        if commit:
            self.db.commit()
        return artifact

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_or_404(self, artifact_id: str) -> Artifact:
        from fastapi import HTTPException
        artifact = self.db.query(Artifact).filter(
            Artifact.id == uuid.UUID(artifact_id)
        ).first()
        if not artifact:
            raise HTTPException(status_code=404, detail="Artifact not found")
        return artifact


# ------------------------------------------------------------------
# Rendering helpers
# ------------------------------------------------------------------

def _render_sections(sections: dict) -> str:
    what = sections.get("what_broke", {})
    why = sections.get("why", {})
    cost = sections.get("cost", {})
    action = sections.get("action", {})

    issue = what.get("issue", "—")
    change = what.get("change_pct", 0)
    count = what.get("count", 0)

    insights = why.get("root_cause_insights", [])
    insights_html = "".join(f"<li>{i}</li>" for i in insights[:4]) or "<li>No significant patterns detected.</li>"

    rev = cost.get("revenue_at_risk", 0)
    high_risk = cost.get("high_risk_customers", 0)
    has_rev = cost.get("has_revenue_data", False)
    cost_line = (
        f"₹{rev:,.0f} revenue at risk across {high_risk} high-churn customers."
        if has_rev else
        f"{high_risk} customers at high churn risk. Revenue data not yet connected."
    )

    narrative = action.get("narrative", "")
    recs = action.get("top_recommendations", [])
    recs_html = "".join(f"<li>{r}</li>" for r in recs) or ""

    trending = why.get("trending_categories", [])
    trend_html = ""
    if trending:
        rows = "".join(
            f"<tr><td style='padding:4px 8px'>{t.get('category','—')}</td>"
            f"<td style='padding:4px 8px;color:#dc2626'>+{t.get('change_percentage',0):.0f}%</td></tr>"
            for t in trending[:3]
        )
        trend_html = f"""
<h3 style="margin-top:24px">Trending Up</h3>
<table style="border-collapse:collapse;font-size:14px"><tbody>{rows}</tbody></table>"""

    return f"""
<h3>What Broke</h3>
<p><strong>{issue}</strong> — {count} complaints ({change:+.0f}% vs last week)</p>

<h3>Why</h3>
<ul>{insights_html}</ul>
{trend_html}

<h3>Cost</h3>
<p>{cost_line}</p>

<h3>Recommended Actions</h3>
<p>{narrative}</p>
{"<ul>" + recs_html + "</ul>" if recs_html else ""}
""".strip()


def _markdown_to_simple_html(text: str) -> str:
    """Minimal markdown → HTML: paragraphs and line breaks only."""
    paragraphs = text.split("\n\n")
    parts = []
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        lines = p.split("\n")
        parts.append("<p>" + "<br>".join(lines) + "</p>")
    return "\n".join(parts)
