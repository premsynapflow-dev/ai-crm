import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from app.billing import usage
from app.onboarding.flows import apply_signup_plan


class _FakeSession:
    def close(self):
        return None


class BillingUsageTests(unittest.TestCase):
    def test_trial_expiry_blocks_processing(self):
        client = SimpleNamespace(
            plan_id="starter",
            monthly_ticket_limit=500,
            trial_ends_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        record = SimpleNamespace(tickets_processed=5)

        with patch("app.billing.usage.SessionLocal", return_value=_FakeSession()), patch(
            "app.billing.usage._get_or_create_usage", return_value=(record, client)
        ):
            self.assertFalse(usage.can_process_ticket("client-1"))

    def test_paid_plan_allows_overage_processing(self):
        client = SimpleNamespace(
            plan_id="pro",
            monthly_ticket_limit=1000,
            trial_ends_at=None,
        )
        record = SimpleNamespace(tickets_processed=1500)

        with patch("app.billing.usage.SessionLocal", return_value=_FakeSession()), patch(
            "app.billing.usage._get_or_create_usage", return_value=(record, client)
        ):
            self.assertTrue(usage.can_process_ticket("client-1"))

    def test_calculate_overage_uses_plan_price(self):
        client = SimpleNamespace(
            plan_id="pro",
            monthly_ticket_limit=1000,
            trial_ends_at=None,
        )
        record = SimpleNamespace(tickets_processed=1100)

        with patch("app.billing.usage._get_or_create_usage", return_value=(record, client)):
            self.assertEqual(usage.calculate_overage("client-1", db=object()), 300)

    def test_apply_signup_plan_sets_free_plan(self):
        client = SimpleNamespace(plan_id="", plan="", monthly_ticket_limit=0, trial_ends_at=None)

        updated = apply_signup_plan(client)

        self.assertEqual(updated.plan_id, "free")
        self.assertEqual(updated.plan, "free")
        self.assertEqual(updated.monthly_ticket_limit, 50)
        self.assertIsNone(updated.trial_ends_at)


if __name__ == "__main__":
    unittest.main()
