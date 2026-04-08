import uuid
from datetime import datetime, timezone
from unittest.mock import patch

from app.db.models import Complaint, UnifiedMessage
from app.services.unified_ingestion import IncomingMessage, process_incoming_message


def test_process_incoming_message_reuses_existing_complaint_thread(test_db, test_client_record):
    first = IncomingMessage(
        client_id=test_client_record.id,
        channel="email",
        external_message_id="<customer-root@example.com>",
        external_thread_id="<customer-root@example.com>",
        sender_id="customer@example.com",
        sender_name="Customer",
        message_text="My order has not arrived yet.",
        attachments=[],
        timestamp=datetime.now(timezone.utc),
        direction="inbound",
        status="received",
        raw_payload={"headers": {"Message-ID": "<customer-root@example.com>"}},
    )

    with patch("app.services.unified_ingestion.can_process_ticket", return_value=True), patch(
        "app.services.unified_ingestion.track_ticket_usage",
        return_value=None,
    ):
        first_result = process_incoming_message(test_db, first)
        test_db.commit()

    complaint_id = uuid.UUID(first_result["complaint_id"])
    complaint = test_db.query(Complaint).filter(Complaint.id == complaint_id).one()
    assert complaint.thread_id == "<customer-root@example.com>"

    second = IncomingMessage(
        client_id=test_client_record.id,
        channel="email",
        external_message_id="<customer-followup@example.com>",
        external_thread_id="<customer-root@example.com>",
        sender_id="customer@example.com",
        sender_name="Customer",
        message_text="Sharing the order ID now: ORD-778899.",
        attachments=[{"filename": "order.txt"}],
        timestamp=datetime.now(timezone.utc),
        direction="inbound",
        status="received",
        raw_payload={"headers": {"References": "<customer-root@example.com>"}},
    )

    with patch("app.services.unified_ingestion.can_process_ticket", return_value=True), patch(
        "app.services.unified_ingestion.track_ticket_usage",
        return_value=None,
    ):
        second_result = process_incoming_message(test_db, second)
        test_db.commit()

    assert second_result["complaint_id"] == first_result["complaint_id"]
    assert test_db.query(Complaint).filter(Complaint.client_id == test_client_record.id).count() == 1

    stored_messages = (
        test_db.query(UnifiedMessage)
        .filter(UnifiedMessage.client_id == test_client_record.id, UnifiedMessage.channel == "email")
        .order_by(UnifiedMessage.timestamp.asc())
        .all()
    )
    assert len(stored_messages) == 2
    assert all(message.raw_payload.get("complaint_id") == first_result["complaint_id"] for message in stored_messages)
