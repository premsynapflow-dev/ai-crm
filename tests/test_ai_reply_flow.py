import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

from app.db.models import AIReplyQueue, Complaint
from app.intelligence.reply_decision import decide_reply_action
from app.replies.send_reply import send_complaint_reply


class _FakeDB:
    def add(self, obj):
        return obj

    def flush(self):
        return None

    def refresh(self, complaint):
        return complaint


class AIReplyFlowTests(unittest.TestCase):
    def _attach_approved_reply(self, complaint):
        complaint.id = complaint.id or uuid.uuid4()
        complaint.client_id = complaint.client_id or uuid.uuid4()
        complaint.reply_queue = AIReplyQueue(
            complaint_id=complaint.id,
            client_id=complaint.client_id,
            generated_reply=complaint.ai_reply or "Approved reply",
            confidence_score=0.9,
            status="approved",
        )

    def test_reply_decision_threshold(self):
        self.assertEqual(decide_reply_action(0.9), "auto_send_reply")
        self.assertEqual(decide_reply_action(0.85), "mark_for_agent_review")

    def test_send_reply_marks_complaint_sent(self):
        complaint = Complaint(
            summary="Customer needs billing help",
            category="billing",
            ticket_id="TKT-12345678",
            thread_id="TH-1234567890",
            source="email",
            customer_email="customer@example.com",
            ai_reply="Here is the next step for your billing question.",
        )
        complaint.created_at = datetime.now(timezone.utc)
        self._attach_approved_reply(complaint)

        with patch(
            "app.replies.send_reply.send_reply_via_original_channel",
            return_value={"sent": True, "channels": ["email"]},
        ):
            result = send_complaint_reply(_FakeDB(), complaint)

        self.assertTrue(result["sent"])
        self.assertEqual(complaint.ai_reply_status, "sent")
        self.assertIsNotNone(complaint.ai_reply_sent_at)
        self.assertIsNotNone(complaint.first_response_at)

    def test_send_reply_falls_back_to_agent_review_when_no_channel(self):
        complaint = Complaint(
            summary="Customer wrote from API without contact info",
            category="general",
            ticket_id="TKT-87654321",
            thread_id="TH-0987654321",
            source="api",
            ai_reply="We have received your issue.",
        )
        complaint.created_at = datetime.now(timezone.utc)
        self._attach_approved_reply(complaint)

        with patch(
            "app.replies.send_reply.send_reply_via_original_channel",
            return_value={"sent": False, "channels": []},
        ), patch("app.replies.send_reply.settings.slack_webhook_url", ""), patch(
            "app.replies.send_reply.send_slack_alert", return_value=False
        ):
            result = send_complaint_reply(_FakeDB(), complaint, client=None)

        self.assertFalse(result["sent"])
        self.assertEqual(complaint.ai_reply_status, "agent_review")
        self.assertIsNone(complaint.ai_reply_sent_at)


if __name__ == "__main__":
    unittest.main()
