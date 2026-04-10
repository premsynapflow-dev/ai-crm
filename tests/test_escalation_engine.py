import logging
import uuid
from datetime import datetime, timedelta, timezone

from app.db.models import Complaint, Escalation
from app.services.escalation_engine import EscalationEngine


def _make_rbi_ticket(client_id, *, created_at: datetime) -> Complaint:
    suffix = uuid.uuid4().hex[:8].upper()
    return Complaint(
        id=uuid.uuid4(),
        client_id=client_id,
        summary="Escalation test",
        category="banking",
        sentiment=-0.4,
        priority=4,
        ticket_id=f"TKT-{suffix}",
        thread_id=f"TH-{suffix}",
        created_at=created_at,
        status="PENDING",
        resolution_status="open",
        state="new",
        rbi_category_code="BANKING",
    )


def test_old_ticket_triggers_threshold_escalation(test_db, test_client_record, caplog):
    complaint = _make_rbi_ticket(
        test_client_record.id,
        created_at=datetime.now(timezone.utc) - timedelta(hours=25),
    )
    test_db.add(complaint)
    test_db.commit()

    engine = EscalationEngine(test_db)
    hours_open = engine.calculate_hours_since_creation(complaint)
    assert hours_open >= 25

    with caplog.at_level(logging.INFO, logger="app.services.escalation_engine"):
        stats = engine.process_pending_escalations(test_client_record.id)

    test_db.refresh(complaint)
    escalation = test_db.query(Escalation).filter(Escalation.ticket_id == complaint.id).one_or_none()

    assert stats["checked"] == 1
    assert stats["escalated"] == 1
    assert stats["errors"] == 0
    assert complaint.escalation_level == 1
    assert complaint.escalated_to == "regional_manager@rbi"
    assert escalation is not None
    assert escalation.level == 1
    assert "Escalation trigger matched for ticket" in caplog.text


def test_new_ticket_does_not_trigger_threshold_escalation(test_db, test_client_record):
    complaint = _make_rbi_ticket(
        test_client_record.id,
        created_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    test_db.add(complaint)
    test_db.commit()

    engine = EscalationEngine(test_db)
    hours_open = engine.calculate_hours_since_creation(complaint)

    assert 0 <= hours_open < 24

    stats = engine.process_pending_escalations(test_client_record.id)

    test_db.refresh(complaint)

    assert stats["checked"] == 1
    assert stats["escalated"] == 0
    assert stats["errors"] == 0
    assert complaint.escalation_level == 0
    assert complaint.escalated_at is None
    assert test_db.query(Escalation).filter(Escalation.ticket_id == complaint.id).count() == 0
