from datetime import datetime, timezone
from unittest.mock import patch

from app.services.unified_ingestion import IncomingMessage


def test_email_webhook_uses_body_aware_message_id_and_keeps_subject_header(client, test_client_record):
    captured: list[IncomingMessage] = []

    def fake_process(_db, message: IncomingMessage):
        captured.append(message)
        return {"status": "processed", "message_id": "stored-message"}

    with patch("app.services.unified_ingestion.process_incoming_message", side_effect=fake_process), patch(
        "app.intake.webhook.track_ticket_usage"
    ) as track_usage:
        first = client.post(
            "/webhook/email",
            headers={"x-api-key": test_client_record.api_key},
            json={
                "from": "customer@example.com",
                "subject": "Need help",
                "text": "First issue body",
                "timestamp": "2026-05-30T10:00:00Z",
            },
        )
        second = client.post(
            "/webhook/email",
            headers={"x-api-key": test_client_record.api_key},
            json={
                "from": "customer@example.com",
                "subject": "Need help",
                "text": "Different issue body",
                "timestamp": "2026-05-30T10:01:00Z",
            },
        )

    assert first.status_code == 200
    assert second.status_code == 200
    assert len(captured) == 2
    assert captured[0].external_message_id != captured[1].external_message_id
    assert captured[0].external_message_id.startswith("email-webhook:")
    assert captured[0].raw_payload["headers"]["Subject"] == "Need help"
    assert captured[0].message_text == "Need help\n\nFirst issue body"
    assert captured[0].timestamp == datetime(2026, 5, 30, 10, 0, tzinfo=timezone.utc)
    track_usage.assert_not_called()


def test_whatsapp_webhook_prefers_provider_ids_and_does_not_double_count(client, test_client_record):
    captured: list[IncomingMessage] = []

    def fake_process(_db, message: IncomingMessage):
        captured.append(message)
        return {"status": "processed", "message_id": "stored-message"}

    with patch("app.services.unified_ingestion.process_incoming_message", side_effect=fake_process), patch(
        "app.intake.webhook.track_ticket_usage"
    ) as track_usage:
        response = client.post(
            "/webhook/whatsapp",
            headers={"x-api-key": test_client_record.api_key},
            json={
                "From": "+15551234567",
                "Body": "My order has not arrived.",
                "message_id": "wamid.123",
                "thread_id": "thread-123",
            },
        )

    assert response.status_code == 200
    assert len(captured) == 1
    assert captured[0].external_message_id == "wamid.123"
    assert captured[0].external_thread_id == "thread-123"
    track_usage.assert_not_called()
