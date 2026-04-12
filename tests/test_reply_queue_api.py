import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.db.models import AIReplyQueue, Complaint, ReplyDraft


def _create_complaint(test_db, client_id, *, summary: str, ticket_id: str) -> Complaint:
    complaint = Complaint(
        id=uuid.uuid4(),
        client_id=client_id,
        summary=summary,
        category="billing",
        sentiment=-0.3,
        priority=2,
        ticket_id=ticket_id,
        ticket_number=ticket_id,
        thread_id=f"TH-{ticket_id}",
        created_at=datetime.now(timezone.utc),
        state="new",
    )
    test_db.add(complaint)
    test_db.commit()
    return complaint


def _create_queue_item(test_db, complaint, *, status: str = "pending", expires_in_hours: int = 24) -> AIReplyQueue:
    queue_item = AIReplyQueue(
        id=uuid.uuid4(),
        complaint_id=complaint.id,
        client_id=complaint.client_id,
        generated_reply=f"Reply for {complaint.ticket_id}",
        confidence_score=0.91,
        generation_strategy="gpt4",
        generation_metadata={"model_confidence": 0.91},
        status=status,
        reviewed_by=None,
        reviewed_at=None,
        hallucination_check_passed=True,
        toxicity_score=0.0,
        factual_consistency_score=0.9,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=expires_in_hours),
    )
    test_db.add(queue_item)
    test_db.commit()
    return queue_item


def _create_reply_draft(test_db, complaint, *, status: str = "pending") -> ReplyDraft:
    draft = ReplyDraft(
        id=uuid.uuid4(),
        complaint_id=complaint.id,
        client_id=complaint.client_id,
        ticket_id=complaint.ticket_id,
        customer_id=complaint.customer_id,
        subject=f"Re: {complaint.ticket_id}",
        body=f"Draft body for {complaint.ticket_id}",
        status=status,
        confidence_score=0.87,
        generation_metadata={"strategy": "test"},
    )
    test_db.add(draft)
    test_db.commit()
    return draft


def test_reply_queue_listing_returns_only_pending_items(test_db, client, test_client_record):
    complaint_pending = _create_complaint(
        test_db,
        test_client_record.id,
        summary="Pending reply queue item",
        ticket_id="TKT-RQ-1",
    )
    complaint_approved = _create_complaint(
        test_db,
        test_client_record.id,
        summary="Already processed reply queue item",
        ticket_id="TKT-RQ-2",
    )
    pending_item = _create_queue_item(test_db, complaint_pending, status="pending", expires_in_hours=24)
    _create_queue_item(test_db, complaint_approved, status="approved", expires_in_hours=24)

    response = client.get(
        "/api/v1/reply-queue",
        headers={"x-api-key": test_client_record.api_key},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == str(pending_item.id)
    assert body["items"][0]["ticket_number"] == complaint_pending.ticket_number
    assert body["items"][0]["status"] == "pending"
    assert body["items"][0]["draft_body"] == pending_item.generated_reply


def test_reply_queue_approve_updates_queue_and_complaint(test_db, client, test_client_record):
    complaint = _create_complaint(
        test_db,
        test_client_record.id,
        summary="Approve this AI reply",
        ticket_id="TKT-RQ-3",
    )
    draft = _create_reply_draft(test_db, complaint)
    queue_item = _create_queue_item(test_db, complaint)
    queue_item.reply_draft_id = draft.id
    test_db.commit()

    def fake_send_reply(db, complaint, client=None, reply_text=None, status_on_success="sent", reply_subject=None):
        complaint.ai_reply = reply_text
        complaint.ai_reply_status = status_on_success
        complaint.ai_reply_sent_at = datetime.now(timezone.utc)
        complaint.last_replied_at = complaint.ai_reply_sent_at
        complaint.status = "RESPONDED"
        return {"sent": True, "channels": ["email"]}

    with patch("app.services.auto_reply_hardened.send_complaint_reply", side_effect=fake_send_reply):
        response = client.post(
            f"/api/v1/reply-queue/{queue_item.id}/approve",
            headers={"x-api-key": test_client_record.api_key},
            json={},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["item"]["status"] == "approved"
    assert body["item"]["reviewed_by"] == f"client-{str(test_client_record.id)[:8]}@system.local"

    test_db.refresh(queue_item)
    test_db.refresh(draft)
    test_db.refresh(complaint)
    assert queue_item.status == "approved"
    assert draft.status == "approved"
    assert complaint.ai_reply_status == "sent"
    assert complaint.ai_reply_sent_at is not None
    assert complaint.last_replied_at is not None
    assert complaint.status == "RESPONDED"


def test_reply_queue_approve_reports_delivery_failure(test_db, client, test_client_record):
    complaint = _create_complaint(
        test_db,
        test_client_record.id,
        summary="Approve but fail delivery",
        ticket_id="TKT-RQ-FAIL",
    )
    queue_item = _create_queue_item(test_db, complaint)

    def fake_send_reply(db, complaint, client=None, reply_text=None, status_on_success="sent", reply_subject=None):
        complaint.ai_reply = reply_text
        complaint.ai_reply_status = "agent_review"
        return {"sent": False, "channels": []}

    with patch("app.services.auto_reply_hardened.send_complaint_reply", side_effect=fake_send_reply):
        response = client.post(
            f"/api/v1/reply-queue/{queue_item.id}/approve",
            headers={"x-api-key": test_client_record.api_key},
            json={},
        )

    assert response.status_code == 502
    assert response.json()["detail"] == "Queue item was reviewed, but the reply could not be delivered"

    test_db.refresh(queue_item)
    test_db.refresh(complaint)
    assert queue_item.status == "pending"
    assert queue_item.reviewed_by is None
    assert queue_item.reviewed_at is None
    assert complaint.ai_reply_status == "agent_review"


def test_reply_queue_reject_updates_queue_state(test_db, client, test_client_record):
    complaint = _create_complaint(
        test_db,
        test_client_record.id,
        summary="Reject this AI reply",
        ticket_id="TKT-RQ-4",
    )
    draft = _create_reply_draft(test_db, complaint)
    queue_item = _create_queue_item(test_db, complaint)
    queue_item.reply_draft_id = draft.id
    test_db.commit()

    response = client.post(
        f"/api/v1/reply-queue/{queue_item.id}/reject",
        headers={"x-api-key": test_client_record.api_key},
        json={"reason": "Needs human review"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["item"]["status"] == "rejected"
    assert body["item"]["rejection_reason"] == "Needs human review"

    test_db.refresh(queue_item)
    test_db.refresh(draft)
    test_db.refresh(complaint)
    assert queue_item.status == "rejected"
    assert draft.status == "rejected"
    assert complaint.ai_reply_status == "agent_review"
