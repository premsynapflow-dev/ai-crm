import uuid
from datetime import datetime, timezone

from app.db.models import AIReplyQueue, AutomationSetting, Complaint, Customer, ReplyDraft, UnifiedMessage
from app.services.auto_reply_hardened import HardenedAutoReplyService


def _create_customer(test_db, client_id, *, churn_risk_score: float = 10.0) -> Customer:
    customer = Customer(
        id=uuid.uuid4(),
        client_id=client_id,
        primary_email="customer@example.com",
        full_name="Taylor Customer",
        emails=["customer@example.com"],
        churn_risk_score=churn_risk_score,
        total_tickets=2,
    )
    test_db.add(customer)
    test_db.commit()
    return customer


def _create_complaint(test_db, client_id, customer_id, *, priority: int = 2) -> Complaint:
    complaint = Complaint(
        id=uuid.uuid4(),
        client_id=client_id,
        customer_id=customer_id,
        summary="Customer needs help with a billing refund request.",
        category="billing",
        sentiment=-0.4,
        priority=priority,
        source="email",
        customer_email="customer@example.com",
        ticket_id="TKT-DRAFT-1",
        ticket_number="TKT-DRAFT-1",
        thread_id="<draft-thread@example.com>",
        created_at=datetime.now(timezone.utc),
        state="new",
        status="AUTO_REPLY",
    )
    test_db.add(complaint)
    test_db.commit()
    return complaint


def _enable_auto_reply(test_db, client_id):
    setting = AutomationSetting(
        id=uuid.uuid4(),
        client_id=client_id,
        channel="email",
        auto_reply_enabled=True,
        confidence_threshold=0.8,
    )
    test_db.add(setting)
    test_db.commit()
    return setting


def _add_thread_messages(test_db, client_id, thread_id: str):
    messages = [
        UnifiedMessage(
            id=uuid.uuid4(),
            client_id=client_id,
            channel="email",
            external_message_id="<draft-inbound@example.com>",
            external_thread_id=thread_id,
            sender_id="customer@example.com",
            sender_name="Taylor Customer",
            message_text="I was charged twice and need help with the billing issue.",
            attachments=[],
            timestamp=datetime.now(timezone.utc),
            direction="inbound",
            status="processed",
            raw_payload={
                "headers": {"Subject": "Billing help needed"},
            },
        ),
        UnifiedMessage(
            id=uuid.uuid4(),
            client_id=client_id,
            channel="email",
            external_message_id="<draft-outbound@example.com>",
            external_thread_id=thread_id,
            sender_id="support@example.com",
            sender_name="Support",
            message_text="We are checking your earlier message.",
            attachments=[],
            timestamp=datetime.now(timezone.utc),
            direction="outbound",
            status="sent",
            raw_payload={},
        ),
    ]
    test_db.add_all(messages)
    test_db.commit()


def test_generate_and_queue_reply_creates_reply_draft(test_db, test_client_record):
    customer = _create_customer(test_db, test_client_record.id)
    complaint = _create_complaint(test_db, test_client_record.id, customer.id)
    _enable_auto_reply(test_db, test_client_record.id)
    _add_thread_messages(test_db, test_client_record.id, complaint.thread_id)

    queue_item = HardenedAutoReplyService(test_db).generate_and_queue_reply(complaint, commit=True)

    assert queue_item is not None

    draft = test_db.query(ReplyDraft).filter(ReplyDraft.complaint_id == complaint.id).one()
    test_db.refresh(complaint)
    test_db.refresh(queue_item)

    assert draft.client_id == complaint.client_id
    assert draft.ticket_id == complaint.ticket_id
    assert draft.status == "pending"
    assert draft.subject.startswith("Re:")
    assert "billing" in draft.body.lower()
    assert queue_item.reply_draft_id == draft.id
    assert queue_item.status == "pending"
    assert complaint.ai_reply_status == "pending"
    assert complaint.ai_reply == draft.body


def test_generate_and_queue_reply_skips_high_priority_tickets(test_db, test_client_record):
    customer = _create_customer(test_db, test_client_record.id)
    complaint = _create_complaint(test_db, test_client_record.id, customer.id, priority=5)
    _enable_auto_reply(test_db, test_client_record.id)
    _add_thread_messages(test_db, test_client_record.id, complaint.thread_id)

    queue_item = HardenedAutoReplyService(test_db).generate_and_queue_reply(complaint, commit=True)

    assert queue_item is None
    assert test_db.query(ReplyDraft).filter(ReplyDraft.complaint_id == complaint.id).count() == 0
    assert test_db.query(AIReplyQueue).filter(AIReplyQueue.complaint_id == complaint.id).count() == 0
    test_db.refresh(complaint)
    assert complaint.ai_reply_status == "agent_review"
