import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from app.db.models import ClientUser, Complaint, RoutingRule, SLAPolicy, Team, TeamMember, UnifiedMessage
from app.services.unified_ingestion import IncomingMessage, process_incoming_message


def _incoming_message(client_id, external_message_id: str, text: str) -> IncomingMessage:
    return IncomingMessage(
        client_id=client_id,
        channel="email",
        external_message_id=external_message_id,
        external_thread_id=external_message_id,
        sender_id="customer@example.com",
        sender_name="Customer",
        message_text=text,
        attachments=[],
        timestamp=datetime.now(timezone.utc),
        direction="inbound",
        status="received",
        raw_payload={"headers": {"Message-ID": external_message_id}},
    )


def test_incoming_message_creates_complaint_links_assignment_and_sla(test_db, test_client_record):
    user = ClientUser(
        id=uuid.uuid4(),
        client_id=test_client_record.id,
        email="owner@example.com",
        password_hash="hash",
    )
    finance_team = Team(
        id=uuid.uuid4(),
        client_id=test_client_record.id,
        name="finance",
    )
    finance_member = TeamMember(
        id=uuid.uuid4(),
        client_id=test_client_record.id,
        team_id=finance_team.id,
        user_id=user.id,
        role="agent",
        capacity=10,
        active_tasks=0,
        is_active=True,
    )
    billing_rule = RoutingRule(
        id=uuid.uuid4(),
        client_id=test_client_record.id,
        category="billing",
        team_id=finance_team.id,
    )
    policy = SLAPolicy(
        id=uuid.uuid4(),
        client_id=test_client_record.id,
        name="Medium",
        priority_level="medium",
        first_response_minutes=60,
        resolution_minutes=240,
        enabled=True,
    )
    test_db.add(user)
    test_db.add(finance_team)
    test_db.add(finance_member)
    test_db.add(billing_rule)
    test_db.add(policy)
    test_db.commit()

    message = _incoming_message(
        test_client_record.id,
        "<ticket-create@example.com>",
        "I need help with a billing issue on my account.",
    )

    classification = {
        "intent": "complaint",
        "category": "billing",
        "sentiment": -0.3,
        "urgency_score": 0.5,
        "priority": 2,
        "recommended_action": "support_ticket",
        "confidence": 0.91,
        "summary": "Billing issue on customer account",
    }

    with patch("app.services.unified_ingestion.can_process_ticket", return_value=True), patch(
        "app.services.unified_ingestion.track_ticket_usage",
        return_value=None,
    ), patch(
        "app.intelligence.classifier.classify_message",
        return_value=classification,
    ), patch(
        "app.services.auto_reply_hardened.HardenedAutoReplyService.generate_and_queue_reply",
        return_value=SimpleNamespace(status="pending"),
    ), patch(
        "app.workflow.dispatcher.dispatch_action",
        return_value=None,
    ), patch(
        "app.services.rules_engine.get_matching_rules",
        return_value=[],
    ):
        result = process_incoming_message(test_db, message)
        test_db.commit()

    complaint = test_db.query(Complaint).filter(Complaint.id == uuid.UUID(result["complaint_id"])).one()
    stored_message = test_db.query(UnifiedMessage).filter(UnifiedMessage.id == uuid.UUID(result["message_id"])).one()
    test_db.refresh(finance_member)

    assert result["status"] == "processed"
    assert complaint.team_id == finance_team.id
    assert complaint.assigned_team == "finance"
    assert complaint.assigned_user_id == user.id
    assert complaint.assigned_to == "owner@example.com"
    assert complaint.sla_due_at is not None
    assert stored_message.raw_payload["complaint_id"] == str(complaint.id)
    assert stored_message.raw_payload["message_id"] == str(stored_message.id)
    assert stored_message.raw_payload["team_id"] == str(finance_team.id)
    assert stored_message.raw_payload["assigned_team"] == "finance"
    assert stored_message.raw_payload["assigned_user"] == "owner@example.com"
    assert stored_message.raw_payload["assigned_user_id"] == str(user.id)
    assert stored_message.status == "processed"
    assert finance_member.active_tasks == 1


def test_incoming_spam_message_does_not_create_complaint(test_db, test_client_record):
    message = _incoming_message(
        test_client_record.id,
        "<spam-message@example.com>",
        "Win a free prize now by clicking this suspicious link!",
    )

    classification = {
        "intent": "complaint",
        "category": "spam",
        "sentiment": -0.1,
        "urgency_score": 0.1,
        "priority": 1,
        "recommended_action": "auto_reply",
        "confidence": 0.98,
        "summary": "Promotional spam message",
    }

    with patch("app.services.unified_ingestion.can_process_ticket", return_value=True), patch(
        "app.services.unified_ingestion.track_ticket_usage",
        return_value=None,
    ), patch(
        "app.intelligence.classifier.classify_message",
        return_value=classification,
    ), patch(
        "app.workflow.dispatcher.dispatch_action",
        return_value=None,
    ):
        result = process_incoming_message(test_db, message)
        test_db.commit()

    stored_message = test_db.query(UnifiedMessage).filter(UnifiedMessage.id == uuid.UUID(result["message_id"])).one()

    assert result["status"] == "spam_filtered"
    assert test_db.query(Complaint).filter(Complaint.client_id == test_client_record.id).count() == 0
    assert stored_message.status == "spam_filtered"
    assert "complaint_id" not in stored_message.raw_payload
    assert stored_message.raw_payload["classification_category"] == "spam"
