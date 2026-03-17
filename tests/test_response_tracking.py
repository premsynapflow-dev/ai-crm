import unittest
from datetime import datetime, timedelta, timezone

from app.db.models import Complaint
from app.services.response_tracking import mark_first_response


class _FakeDB:
    def refresh(self, complaint):
        return complaint

    def flush(self):
        return None


class ResponseTrackingTests(unittest.TestCase):
    def test_marks_first_response_once(self):
        created_at = datetime.now(timezone.utc)
        complaint = Complaint(
            summary="Checkout failed",
            category="technical",
            ticket_id="TKT-12345678",
            thread_id="TH-1234567890",
        )
        complaint.created_at = created_at

        responded_at = created_at + timedelta(seconds=120)
        changed = mark_first_response(_FakeDB(), complaint, responded_at=responded_at)

        self.assertTrue(changed)
        self.assertEqual(complaint.first_response_at, responded_at)
        self.assertEqual(complaint.response_time_seconds, 120)

        second_change = mark_first_response(
            _FakeDB(),
            complaint,
            responded_at=responded_at + timedelta(seconds=30),
        )
        self.assertFalse(second_change)
        self.assertEqual(complaint.response_time_seconds, 120)


if __name__ == "__main__":
    unittest.main()
