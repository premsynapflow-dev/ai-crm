import uuid
from datetime import datetime, timezone

from app.db.models import Complaint


def test_ticket_state_transition_endpoint(test_db, client, test_client_record):
    complaint = Complaint(
        id=uuid.uuid4(),
        client_id=test_client_record.id,
        summary="Transition test",
        category="test",
        sentiment=0.0,
        priority=2,
        ticket_id="TKT-999",
        ticket_number="TKT-999",
        thread_id="TH-999",
        created_at=datetime.now(timezone.utc),
        state="new",
    )
    test_db.add(complaint)
    test_db.commit()

    response = client.post(
        f"/api/v1/tickets/{complaint.id}/transition",
        json={"to_state": "assigned", "reason": "unit test"},
        headers={"x-api-key": test_client_record.api_key},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["ticket"]["state"] == "assigned"


def test_ticket_comment_endpoint(test_db, client, test_client_record):
    complaint = Complaint(
        id=uuid.uuid4(),
        client_id=test_client_record.id,
        summary="Comment test",
        category="test",
        sentiment=0.0,
        priority=2,
        ticket_id="TKT-1000",
        ticket_number="TKT-1000",
        thread_id="TH-1000",
        created_at=datetime.now(timezone.utc),
        state="new",
    )
    test_db.add(complaint)
    test_db.commit()

    response = client.post(
        f"/api/v1/tickets/{complaint.id}/comments",
        json={"content": "Internal note", "is_internal": True},
        headers={"x-api-key": test_client_record.api_key},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["comment"]["content"] == "Internal note"
    assert body["comment"]["is_internal"] is True


def test_ticket_assignment_endpoint(test_db, client, test_client_record):
    complaint = Complaint(
        id=uuid.uuid4(),
        client_id=test_client_record.id,
        summary="Assignment test",
        category="test",
        sentiment=0.0,
        priority=2,
        ticket_id="TKT-1001",
        ticket_number="TKT-1001",
        thread_id="TH-1001",
        created_at=datetime.now(timezone.utc),
        state="new",
    )
    test_db.add(complaint)
    test_db.commit()

    response = client.post(
        f"/api/v1/tickets/{complaint.id}/assign",
        json={"assigned_to": "support-agent@example.com", "assignment_reason": "work queue"},
        headers={"x-api-key": test_client_record.api_key},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["ticket"]["assigned_to"] == "support-agent@example.com"
    assert body["ticket"]["state"] == "assigned"
