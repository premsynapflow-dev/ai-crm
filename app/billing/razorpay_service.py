import hashlib
import hmac
from datetime import datetime, timezone

from app.config import get_settings
from app.db.models import EventLog, Invoice, Subscription
from app.db.session import SessionLocal

settings = get_settings()


def _get_razorpay_client():
    try:
        import razorpay
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("razorpay package is not installed") from exc

    if not settings.razorpay_key_id or not settings.razorpay_key_secret:
        raise RuntimeError("Razorpay credentials are not configured")

    return razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))


def create_subscription(client_id, plan_id):
    plan_catalog = {
        "trial": {"period": "weekly", "interval": 1, "item": {"name": "Trial", "amount": 0, "currency": "INR"}},
        "pro": {"period": "monthly", "interval": 1, "item": {"name": "Pro", "amount": 499900, "currency": "INR"}},
        "business": {"period": "monthly", "interval": 1, "item": {"name": "Business", "amount": 1499900, "currency": "INR"}},
    }
    client = _get_razorpay_client()
    payload = plan_catalog.get(plan_id, plan_catalog["trial"]).copy()
    payload["notes"] = {"client_id": str(client_id), "plan_id": plan_id}
    subscription = client.subscription.create(payload)

    db = SessionLocal()
    try:
        record = Subscription(
            client_id=client_id,
            plan=plan_id,
            status=subscription.get("status", "created"),
            razorpay_subscription_id=subscription.get("id"),
            current_period_start=datetime.now(timezone.utc),
        )
        db.add(record)
        db.commit()
    finally:
        db.close()

    return subscription


def create_payment_link(client_id, amount):
    client = _get_razorpay_client()
    payload = {
        "amount": amount,
        "currency": "INR",
        "description": f"SynapFlow usage payment for client {client_id}",
        "notes": {"client_id": str(client_id)},
    }
    return client.payment_link.create(payload)


def verify_payment(payment_id, signature):
    expected_signature = hmac.new(
        settings.razorpay_key_secret.encode(),
        payment_id.encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected_signature, signature)


def handle_webhook(payload):
    db = SessionLocal()
    try:
        event = EventLog(
            client_id=payload.get("payload", {}).get("subscription", {}).get("entity", {}).get("notes", {}).get("client_id") or payload.get("client_id"),
            event_type=f"razorpay:{payload.get('event', 'unknown')}",
            payload=payload,
        )
        db.add(event)
        payment = payload.get("payload", {}).get("payment", {}).get("entity", {})
        if payment.get("id"):
            invoice = Invoice(
                client_id=payload.get("payload", {}).get("subscription", {}).get("entity", {}).get("notes", {}).get("client_id"),
                invoice_number=f"INV-{payment['id']}",
                status="paid",
                subtotal=payment.get("amount", 0),
                tax=0,
                total=payment.get("amount", 0),
                payment_method=payment.get("method"),
                payment_id=payment.get("id"),
                paid_at=datetime.now(timezone.utc),
            )
            db.add(invoice)
        db.commit()
        return {"status": "ok"}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
