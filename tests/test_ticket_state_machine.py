import uuid
from datetime import datetime, timedelta, timezone

from app.db.models import Complaint, Client, SLAPolicy, EscalationRule, TicketStateTransition
from app.services.ticket_state_machine import TicketStateMachine
from app.services.sla_manager import SLAManager


def _make_complaint(client_id):
    return Complaint(
        id=uuid.uuid4(),
        client_id=client_id,
        summary="Test",
        category="test",
        sentiment=0.0,
        priority=2,
        ticket_id="TKT-1",
        thread_id="TH-1",
        created_at=datetime.now(timezone.utc),
    )


def test_valid_transition_records_and_updates_state(test_db, test_client_record):
    complaint = _make_complaint(test_client_record.id)
    test_db.add(complaint)
    test_db.commit()

    machine = TicketStateMachine(test_db)
    success, error = machine.transition(complaint, "assigned", "user@example.com", "Assigning to agent")

    assert success is True
    assert error is None

    test_db.refresh(complaint)
    assert complaint.state == "assigned"
    assert complaint.state_changed_at is not None

    history = test_db.query(TicketStateTransition).filter(TicketStateTransition.complaint_id == complaint.id).first()
    assert history is not None
    assert history.to_state == "assigned"


def test_invalid_transition_fails(test_db, test_client_record):
    complaint = _make_complaint(test_client_record.id)
    test_db.add(complaint)
    test_db.commit()

    machine = TicketStateMachine(test_db)
    success, error = machine.transition(complaint, "closed", "user@example.com")

    assert success is False
    assert error is not None


def test_reopen_updates_counts(test_db, test_client_record):
    complaint = _make_complaint(test_client_record.id)
    complaint.state = "resolved"
    complaint.resolved_at = datetime.now(timezone.utc) - timedelta(hours=1)
    complaint.reopened_count = 0
    test_db.add(complaint)
    test_db.commit()

    machine = TicketStateMachine(test_db)
    success, _ = machine.transition(complaint, "reopened", "user@example.com")

    assert success
    test_db.refresh(complaint)
    assert complaint.state == "reopened"
    assert complaint.reopened_count == 1


def test_sla_due_date_24_7(test_db, test_client_record):
    sla_policy = SLAPolicy(
        id=uuid.uuid4(),
        client_id=test_client_record.id,
        name="Medium",
        priority_level="medium",
        first_response_minutes=60,
        resolution_minutes=240,
        business_hours_only=False,
        enabled=True,
    )
    test_db.add(sla_policy)
    test_db.commit()

    complaint = _make_complaint(test_client_record.id)
    complaint.priority = 2
    complaint.created_at = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    test_db.add(complaint)
    test_db.commit()

    manager = SLAManager(test_db)
    due = manager.calculate_sla_due_date(complaint)

    assert due == datetime(2026, 1, 1, 1, 0, tzinfo=timezone.utc)


def test_sla_breach_escalates(test_db, test_client_record):
    sla_policy = SLAPolicy(
        id=uuid.uuid4(),
        client_id=test_client_record.id,
        name="Critical",
        priority_level="critical",
        first_response_minutes=1,
        resolution_minutes=10,
        enabled=True,
    )
    escalation_rule = EscalationRule(
        id=uuid.uuid4(),
        client_id=test_client_record.id,
        rule_name="SLA breach",
        trigger_condition="sla_breach",
        escalation_level=1,
        escalate_to_email="esc@example.com",
        enabled=True,
    )
    test_db.add(sla_policy)
    test_db.add(escalation_rule)

    complaint = _make_complaint(test_client_record.id)
    complaint.priority = 5
    complaint.sla_due_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    test_db.add(complaint)
    test_db.commit()

    manager = SLAManager(test_db)
    status = manager.update_sla_status(complaint)

    assert status == "breached"
    test_db.refresh(complaint)
    assert complaint.sla_status == "breached"
    assert complaint.escalation_level == 1
    assert complaint.escalated_to == "esc@example.com"


def test_sync_from_legacy_keeps_state_in_step_with_existing_flows(test_db, test_client_record):
    complaint = _make_complaint(test_client_record.id)
    test_db.add(complaint)
    test_db.commit()

    complaint.status = "ESCALATE_HIGH"
    complaint.assigned_to = "support"
    machine = TicketStateMachine(test_db)
    changed, state = machine.sync_from_legacy(complaint, "system", "legacy escalation")

    assert changed is True
    assert state == "in_progress"
    test_db.refresh(complaint)
    assert complaint.state == "in_progress"
