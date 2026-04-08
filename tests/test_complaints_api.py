import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.db.models import (
    AIReplyQueue,
    ClientUser,
    Complaint,
    Customer,
    CustomerInteraction,
    Escalation,
    RBIComplaint,
    RBIEscalationLog,
    ReplyFeedback,
    TicketAssignment,
    TicketComment,
    TicketStateTransition,
    UnifiedMessage,
)
from app.security.passwords import hash_password


def _auth_headers(client, test_db, tenant) -> dict[str, str]:
    password = "ComplaintPass123!"
    user = ClientUser(
        id=uuid.uuid4(),
        client_id=tenant.id,
        email=f"complaints-{tenant.id.hex[:8]}@example.com",
        password_hash=hash_password(password),
        created_at=datetime.now(timezone.utc),
    )
    test_db.add(user)
    test_db.commit()

    response = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": password},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_delete_complaint_removes_dependent_rows(test_db, client, test_client_record):
    headers = _auth_headers(client, test_db, test_client_record)
    complaint_id = uuid.uuid4()
    customer = Customer(
        id=uuid.uuid4(),
        client_id=test_client_record.id,
        primary_email="delete-me@example.com",
    )
    complaint = Complaint(
        id=complaint_id,
        client_id=test_client_record.id,
        customer_id=customer.id,
        summary="Delete this complaint safely",
        category="billing",
        sentiment=-0.2,
        priority=2,
        ticket_id="TKT-DELETE-1",
        ticket_number="TKT-DELETE-1",
        thread_id="TH-DELETE-1",
        created_at=datetime.now(timezone.utc),
    )
    queue_item = AIReplyQueue(
        id=uuid.uuid4(),
        complaint_id=complaint_id,
        client_id=test_client_record.id,
        generated_reply="We will check this.",
        confidence_score=0.8,
        generation_metadata={},
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    rbi_complaint = RBIComplaint(
        id=uuid.uuid4(),
        complaint_id=complaint_id,
        client_id=test_client_record.id,
        tat_due_date=datetime.now(timezone.utc) + timedelta(days=30),
    )
    customer_interaction = CustomerInteraction(
        id=uuid.uuid4(),
        customer_id=customer.id,
        client_id=test_client_record.id,
        interaction_type="ticket",
        interaction_channel="gmail",
        complaint_id=complaint_id,
    )
    test_db.add_all(
        [
            customer,
            complaint,
            queue_item,
            ReplyFeedback(
                id=uuid.uuid4(),
                complaint_id=complaint_id,
                reply_queue_id=queue_item.id,
            ),
            TicketStateTransition(
                id=uuid.uuid4(),
                complaint_id=complaint_id,
                to_state="new",
                transitioned_by="system",
            ),
            TicketComment(
                id=uuid.uuid4(),
                complaint_id=complaint_id,
                author_email="agent@example.com",
                content="Internal note",
            ),
            TicketAssignment(
                id=uuid.uuid4(),
                complaint_id=complaint_id,
                assigned_to="agent@example.com",
            ),
            Escalation(
                id=uuid.uuid4(),
                ticket_id=complaint_id,
                escalated_to="lead@example.com",
            ),
            rbi_complaint,
            RBIEscalationLog(
                id=uuid.uuid4(),
                rbi_complaint_id=rbi_complaint.id,
                from_level=0,
                to_level=1,
                escalation_reason="Test escalation",
                escalated_by="system",
            ),
            customer_interaction,
        ]
    )
    test_db.commit()
    rbi_complaint_id = rbi_complaint.id
    customer_interaction_id = customer_interaction.id

    response = client.delete(f"/api/v1/complaints/{complaint_id}", headers=headers)

    assert response.status_code == 200
    assert response.json() == {"ok": True, "id": str(complaint_id)}
    assert test_db.query(Complaint).filter(Complaint.id == complaint_id).count() == 0
    assert test_db.query(AIReplyQueue).filter(AIReplyQueue.complaint_id == complaint_id).count() == 0
    assert test_db.query(ReplyFeedback).filter(ReplyFeedback.complaint_id == complaint_id).count() == 0
    assert test_db.query(TicketStateTransition).filter(TicketStateTransition.complaint_id == complaint_id).count() == 0
    assert test_db.query(TicketComment).filter(TicketComment.complaint_id == complaint_id).count() == 0
    assert test_db.query(TicketAssignment).filter(TicketAssignment.complaint_id == complaint_id).count() == 0
    assert test_db.query(Escalation).filter(Escalation.ticket_id == complaint_id).count() == 0
    assert test_db.query(RBIComplaint).filter(RBIComplaint.complaint_id == complaint_id).count() == 0
    assert test_db.query(RBIEscalationLog).filter(RBIEscalationLog.rbi_complaint_id == rbi_complaint_id).count() == 0
    saved_interaction = test_db.query(CustomerInteraction).filter(CustomerInteraction.id == customer_interaction_id).one()
    assert saved_interaction.complaint_id is None


def test_reply_complaint_creates_manual_review_queue(test_db, client, test_client_record):
    headers = _auth_headers(client, test_db, test_client_record)
    complaint_id = uuid.uuid4()
    complaint = Complaint(
        id=complaint_id,
        client_id=test_client_record.id,
        summary="Customer asked for an OAuth Gmail reply",
        category="support",
        sentiment=0.0,
        priority=2,
        source="gmail",
        customer_email="customer@example.com",
        ticket_id="TKT-GMAIL-REPLY",
        ticket_number="TKT-GMAIL-REPLY",
        thread_id="gmail-thread-1",
        created_at=datetime.now(timezone.utc),
    )
    test_db.add(complaint)
    test_db.commit()

    with patch(
        "app.replies.send_reply.send_reply_via_original_channel",
        return_value={"sent": True, "channels": ["gmail"]},
    ):
        response = client.post(
            f"/api/v1/complaints/{complaint_id}/reply",
            headers=headers,
            json={"reply_text": "Thanks, we are checking this now."},
        )

    assert response.status_code == 200
    assert response.json()["sent"] is True
    assert response.json()["channels"] == ["gmail"]

    queue_item = test_db.query(AIReplyQueue).filter(AIReplyQueue.complaint_id == complaint_id).one()
    test_db.refresh(complaint)
    assert queue_item.status == "edited"
    assert queue_item.reviewed_by is not None
    assert queue_item.edited_reply == "Thanks, we are checking this now."
    assert complaint.ai_reply_status == "sent"
    assert complaint.ai_reply_sent_at is not None


def test_get_complaint_returns_thread_and_summary(test_db, client, test_client_record):
    headers = _auth_headers(client, test_db, test_client_record)
    complaint_id = uuid.uuid4()
    complaint = Complaint(
        id=complaint_id,
        client_id=test_client_record.id,
        summary="Re: Shipment delay for order ORD-445566",
        category="support",
        sentiment=0.0,
        priority=2,
        source="email",
        customer_email="customer@example.com",
        ticket_id="TKT-THREAD-1",
        ticket_number="TKT-THREAD-1",
        thread_id="<root-message@example.com>",
        created_at=datetime.now(timezone.utc),
    )
    inbound_message = UnifiedMessage(
        id=uuid.uuid4(),
        client_id=test_client_record.id,
        channel="email",
        external_message_id="<root-message@example.com>",
        external_thread_id="<root-message@example.com>",
        sender_id="customer@example.com",
        sender_name="Customer",
        message_text="Hi, my shipment is delayed.",
        attachments=[],
        timestamp=datetime.now(timezone.utc),
        direction="inbound",
        status="processed",
        raw_payload={
            "complaint_id": str(complaint_id),
            "conversation_id": str(uuid.uuid4()),
            "headers": {"Subject": "Shipment delay for order ORD-445566"},
        },
    )
    follow_up_message = UnifiedMessage(
        id=uuid.uuid4(),
        client_id=test_client_record.id,
        channel="email",
        external_message_id="<follow-up@example.com>",
        external_thread_id="<root-message@example.com>",
        sender_id="customer@example.com",
        sender_name="Customer",
        message_text="Here is the order ID you asked for: ORD-445566.",
        attachments=[{"filename": "order-details.pdf", "size": 1234}],
        timestamp=datetime.now(timezone.utc),
        direction="inbound",
        status="processed",
        raw_payload={
            "complaint_id": str(complaint_id),
            "conversation_id": str(uuid.uuid4()),
            "headers": {"Subject": "Re: Shipment delay for order ORD-445566"},
        },
    )
    test_db.add_all([complaint, inbound_message, follow_up_message])
    test_db.commit()

    response = client.get(f"/api/v1/complaints/{complaint_id}", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["thread_id"] == "<root-message@example.com>"
    assert payload["subject"] == "Shipment delay for order ORD-445566"
    assert len(payload["thread_messages"]) == 2
    assert payload["conversation_summary"]["message_count"] == 2
    assert payload["conversation_summary"]["attachments"] == ["order-details.pdf"]


def test_list_complaints_prefers_original_thread_subject(test_db, client, test_client_record):
    headers = _auth_headers(client, test_db, test_client_record)
    complaint_id = uuid.uuid4()
    complaint = Complaint(
        id=complaint_id,
        client_id=test_client_record.id,
        summary="Re: Order ID for delayed shipment",
        category="support",
        sentiment=0.0,
        priority=2,
        source="email",
        customer_email="customer@example.com",
        ticket_id="TKT-LIST-1",
        ticket_number="TKT-LIST-1",
        thread_id="<ticket-list-root@example.com>",
        created_at=datetime.now(timezone.utc),
    )
    first_message = UnifiedMessage(
        id=uuid.uuid4(),
        client_id=test_client_record.id,
        channel="email",
        external_message_id="<ticket-list-root@example.com>",
        external_thread_id="<ticket-list-root@example.com>",
        sender_id="customer@example.com",
        sender_name="Customer",
        message_text="Original order delay body",
        attachments=[],
        timestamp=datetime.now(timezone.utc),
        direction="inbound",
        status="processed",
        raw_payload={
            "complaint_id": str(complaint_id),
            "headers": {"Subject": "Original delayed shipment complaint"},
        },
    )
    follow_up_message = UnifiedMessage(
        id=uuid.uuid4(),
        client_id=test_client_record.id,
        channel="email",
        external_message_id="<ticket-list-followup@example.com>",
        external_thread_id="<ticket-list-root@example.com>",
        sender_id="customer@example.com",
        sender_name="Customer",
        message_text="Here is the order ID you requested.",
        attachments=[],
        timestamp=datetime.now(timezone.utc) + timedelta(minutes=5),
        direction="inbound",
        status="processed",
        raw_payload={
            "complaint_id": str(complaint_id),
            "headers": {"Subject": "Re: Original delayed shipment complaint"},
        },
    )
    test_db.add_all([complaint, first_message, follow_up_message])
    test_db.commit()

    response = client.get("/api/v1/complaints", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["ticket_id"] == "TKT-LIST-1"
    assert payload["items"][0]["subject"] == "Original delayed shipment complaint"
