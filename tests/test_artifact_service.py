"""Tests for ArtifactService — generate / approve / reject / render_email / deliver."""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.db.models import Artifact


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_digest_payload() -> dict:
    return {
        "period_days": 7,
        "what_broke": {
            "issue": "Payment failures",
            "count": 42,
            "change_pct": 35.0,
        },
        "why": {
            "root_cause_insights": ["Gateway timeouts spiked on Tuesday."],
            "trending_categories": [{"category": "Payment", "change_percentage": 35}],
        },
        "cost": {
            "revenue_at_risk": 1_500_000,
            "high_risk_customers": 8,
            "has_revenue_data": True,
            "revenue_coverage_pct": 60.0,
            "currency": "INR",
        },
        "action": {
            "narrative": "Escalate payment gateway team. Run incident retro. Reach out to 8 at-risk customers.",
            "top_recommendations": ["Review gateway SLA", "Proactive outreach to top 8 accounts"],
        },
        "correlational_signals": [],
        "generated_at": "2026-06-12T07:00:00+00:00",
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def svc(test_db):
    from app.services.artifact_service import ArtifactService
    return ArtifactService(test_db)


@pytest.fixture
def pilot_client(test_client_record):
    return test_client_record


# ---------------------------------------------------------------------------
# generate_weekly_digest
# ---------------------------------------------------------------------------

class TestGenerateWeeklyDigest:
    def test_creates_draft_artifact(self, svc, pilot_client, test_db):
        payload = _make_digest_payload()
        with patch("app.services.artifact_service.ArtifactService.generate_weekly_digest",
                   wraps=svc.generate_weekly_digest) as _wrapped, \
             patch("app.api.v1.executive_summary.build_digest_payload", return_value=payload):
            artifact = svc.generate_weekly_digest(pilot_client, recipient="ops@pilot.com")

        assert artifact.id is not None
        assert artifact.status == "draft"
        assert artifact.client_id == pilot_client.id
        assert artifact.artifact_type == "weekly_operational_digest"
        assert artifact.recipient == "ops@pilot.com"
        assert "what_broke" in artifact.sections_json
        assert artifact.period_start == date.today() - timedelta(days=7)

    def test_idempotent_on_same_period(self, svc, pilot_client, test_db):
        payload = _make_digest_payload()
        with patch("app.api.v1.executive_summary.build_digest_payload", return_value=payload):
            a1 = svc.generate_weekly_digest(pilot_client)
            a2 = svc.generate_weekly_digest(pilot_client)

        assert a1.id == a2.id
        rows = test_db.query(Artifact).filter(Artifact.client_id == pilot_client.id).all()
        assert len(rows) == 1

    def test_summary_is_first_sentence_of_narrative(self, svc, pilot_client):
        payload = _make_digest_payload()
        with patch("app.api.v1.executive_summary.build_digest_payload", return_value=payload):
            artifact = svc.generate_weekly_digest(pilot_client)

        assert artifact.summary.startswith("Escalate payment gateway team")
        assert artifact.summary.endswith(".")


# ---------------------------------------------------------------------------
# approve / reject
# ---------------------------------------------------------------------------

class TestReviewLifecycle:
    def _create_draft(self, svc, pilot_client, payload):
        with patch("app.api.v1.executive_summary.build_digest_payload", return_value=payload):
            return svc.generate_weekly_digest(pilot_client)

    def test_approve_sets_status_and_reviewer(self, svc, pilot_client):
        artifact = self._create_draft(svc, pilot_client, _make_digest_payload())
        updated = svc.approve(str(artifact.id), reviewer_email="analyst@co.com")
        assert updated.status == "approved"
        assert updated.reviewed_by == "analyst@co.com"
        assert updated.reviewed_at is not None

    def test_approve_stores_edited_body(self, svc, pilot_client):
        artifact = self._create_draft(svc, pilot_client, _make_digest_payload())
        updated = svc.approve(str(artifact.id), reviewer_email="a@co.com", edited_body="Custom memo text.")
        assert updated.edited_body == "Custom memo text."

    def test_reject_sets_status_and_reason(self, svc, pilot_client):
        artifact = self._create_draft(svc, pilot_client, _make_digest_payload())
        updated = svc.reject(str(artifact.id), reviewer_email="a@co.com", reason="Low data quality.")
        assert updated.status == "rejected"
        assert updated.rejection_reason == "Low data quality."

    def test_get_or_404_raises_on_missing(self, svc):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            svc._get_or_404(str(uuid.uuid4()))
        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# render_email
# ---------------------------------------------------------------------------

class TestRenderEmail:
    def _draft(self, svc, pilot_client):
        payload = _make_digest_payload()
        with patch("app.api.v1.executive_summary.build_digest_payload", return_value=payload):
            return svc.generate_weekly_digest(pilot_client)

    def test_subject_equals_title(self, svc, pilot_client):
        artifact = self._draft(svc, pilot_client)
        subject, _ = svc.render_email(artifact)
        assert subject == artifact.title

    def test_body_contains_sections(self, svc, pilot_client):
        artifact = self._draft(svc, pilot_client)
        _, body = svc.render_email(artifact)
        assert "Payment failures" in body
        assert "Gateway timeouts" in body
        assert "₹15.0L" in body or "₹1" in body  # INR formatting
        assert "acted" in body  # engagement link

    def test_edited_body_used_when_present(self, svc, pilot_client):
        artifact = self._draft(svc, pilot_client)
        svc.approve(str(artifact.id), reviewer_email="a@co.com", edited_body="## Custom\nHello pilot.")
        _, body = svc.render_email(artifact)
        assert "Custom" in body
        assert "Hello pilot" in body


# ---------------------------------------------------------------------------
# deliver
# ---------------------------------------------------------------------------

class TestDeliver:
    def _approved_artifact(self, svc, pilot_client):
        payload = _make_digest_payload()
        with patch("app.api.v1.executive_summary.build_digest_payload", return_value=payload):
            artifact = svc.generate_weekly_digest(pilot_client, recipient="ops@pilot.com")
        svc.approve(str(artifact.id), reviewer_email="a@co.com")
        return artifact

    def test_deliver_calls_send_email(self, svc, pilot_client):
        artifact = self._approved_artifact(svc, pilot_client)
        with patch("app.services.artifact_service.send_email", return_value=True) as mock_send:
            svc.deliver(artifact)
        mock_send.assert_called_once()
        call_args = mock_send.call_args
        assert call_args[0][0] == "ops@pilot.com"

    def test_deliver_sets_delivered_status(self, svc, pilot_client):
        artifact = self._approved_artifact(svc, pilot_client)
        with patch("app.services.artifact_service.send_email", return_value=True):
            updated = svc.deliver(artifact)
        assert updated.status == "delivered"
        assert updated.delivered_at is not None
        assert updated.delivery_channel == "email"

    def test_deliver_without_recipient_raises(self, svc, pilot_client):
        payload = _make_digest_payload()
        with patch("app.api.v1.executive_summary.build_digest_payload", return_value=payload):
            artifact = svc.generate_weekly_digest(pilot_client, recipient=None)
        svc.approve(str(artifact.id), reviewer_email="a@co.com")
        artifact.recipient = None
        with pytest.raises(ValueError, match="No recipient"):
            svc.deliver(artifact)


# ---------------------------------------------------------------------------
# record_event
# ---------------------------------------------------------------------------

class TestRecordEvent:
    def test_stamps_opened_at(self, svc, pilot_client):
        payload = _make_digest_payload()
        with patch("app.api.v1.executive_summary.build_digest_payload", return_value=payload):
            artifact = svc.generate_weekly_digest(pilot_client)
        svc.record_event(str(artifact.id), "opened")
        assert artifact.opened_at is not None

    def test_stamps_acted_at_and_opened_at(self, svc, pilot_client):
        payload = _make_digest_payload()
        with patch("app.api.v1.executive_summary.build_digest_payload", return_value=payload):
            artifact = svc.generate_weekly_digest(pilot_client)
        svc.record_event(str(artifact.id), "acted")
        assert artifact.acted_at is not None
        assert artifact.opened_at is not None  # acted implies opened

    def test_idempotent_opened(self, svc, pilot_client):
        payload = _make_digest_payload()
        with patch("app.api.v1.executive_summary.build_digest_payload", return_value=payload):
            artifact = svc.generate_weekly_digest(pilot_client)
        svc.record_event(str(artifact.id), "opened")
        first_ts = artifact.opened_at
        svc.record_event(str(artifact.id), "opened")
        assert artifact.opened_at == first_ts  # not overwritten
