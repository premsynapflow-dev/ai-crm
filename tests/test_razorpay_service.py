import hashlib
import hmac
import unittest
import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.billing import razorpay_service
from app.billing.plans import PLANS
from app.db.models import Base, Client, EventLog, Invoice, Subscription


class RazorpayServiceTests(unittest.TestCase):
    def test_create_subscription_requires_configured_razorpay_plan_id(self):
        original_plan_ids = razorpay_service.PLANS["starter"]["razorpay_plan_ids"]
        razorpay_service.PLANS["starter"]["razorpay_plan_ids"] = {}
        try:
            with self.assertRaisesRegex(ValueError, "not configured"):
                razorpay_service.create_subscription("client_123", "starter", "monthly")
        finally:
            razorpay_service.PLANS["starter"]["razorpay_plan_ids"] = original_plan_ids

    def test_verify_payment_accepts_valid_signature(self):
        original_secret = razorpay_service.settings.razorpay_key_secret
        razorpay_service.settings.razorpay_key_secret = "super-secret"
        try:
            payment_id = "pay_test_123"
            signature = hmac.new(
                b"super-secret",
                payment_id.encode(),
                hashlib.sha256,
            ).hexdigest()
            self.assertTrue(razorpay_service.verify_payment(payment_id, signature))
            self.assertFalse(razorpay_service.verify_payment(payment_id, "bad-signature"))
        finally:
            razorpay_service.settings.razorpay_key_secret = original_secret

    def test_subscription_plan_maps_to_existing_plan_id_column(self):
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(bind=engine)
        session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = session_local()
        try:
            subscription = Subscription(
                client_id=uuid.uuid4(),
                plan="max",
                status="active",
                current_period_start=datetime.now(timezone.utc),
            )
            db.add(subscription)
            db.commit()

            stored_plan = db.execute(text("SELECT plan_id FROM subscriptions")).scalar_one()
            self.assertEqual(stored_plan, "max")
        finally:
            db.close()
            Base.metadata.drop_all(bind=engine)

    def test_paid_webhook_applies_plan_from_razorpay_notes(self):
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(bind=engine)
        session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        original_session_local = razorpay_service.SessionLocal
        razorpay_service.SessionLocal = session_local
        client_id = uuid.uuid4()
        db = session_local()
        try:
            db.add(
                Client(
                    id=client_id,
                    name="Neuronyx",
                    api_key="test-api-key",
                    plan="trial",
                    plan_id="trial",
                    monthly_ticket_limit=500,
                    trial_ends_at=datetime.now(timezone.utc),
                )
            )
            db.commit()

            result = razorpay_service.handle_webhook(
                {
                    "event": "payment_link.paid",
                    "payload": {
                        "payment_link": {
                            "entity": {
                                "notes": {
                                    "client_id": str(client_id),
                                    "plan_id": "max",
                                    "billing_cycle": "monthly",
                                }
                            }
                        },
                        "payment": {
                            "entity": {
                                "id": "pay_test_max",
                                "amount": 999900,
                                "method": "upi",
                            }
                        },
                    },
                }
            )
            db.expire_all()
            updated = db.query(Client).filter(Client.id == client_id).one()
            event = db.query(EventLog).filter(EventLog.client_id == client_id).one()
            invoice = db.query(Invoice).filter(Invoice.client_id == client_id).one()

            self.assertEqual(result, {"status": "ok"})
            self.assertEqual(updated.plan_id, "max")
            self.assertEqual(updated.plan, "max")
            self.assertEqual(updated.monthly_ticket_limit, PLANS["max"]["tickets_per_month"])
            self.assertIsNone(updated.trial_ends_at)
            self.assertEqual(event.event_type, "razorpay:payment_link.paid")
            self.assertEqual(invoice.invoice_number, "INV-pay_test_max")
        finally:
            db.close()
            razorpay_service.SessionLocal = original_session_local
            Base.metadata.drop_all(bind=engine)


if __name__ == "__main__":
    unittest.main()
