import hashlib
import hmac
import logging
from datetime import datetime, timezone

from app.config import get_settings
from app.billing.plans import PLANS
from app.db.models import Client, EventLog, Invoice, Subscription
from app.db.session import SessionLocal

settings = get_settings()
logger = logging.getLogger(__name__)


def _get_razorpay_client():
    try:
        import razorpay
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("razorpay package is not installed") from exc

    if not settings.razorpay_key_id or not settings.razorpay_key_secret:
        raise RuntimeError("Razorpay credentials are not configured")

    return razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))


def create_subscription(client_id, plan_id, billing_cycle="monthly"):
    plan_catalog = {
        "starter": {
            "monthly": {"period": "monthly", "interval": 1, "item": {"name": "Starter", "amount": 299900, "currency": "INR"}},
            "annual": {"period": "yearly", "interval": 1, "item": {"name": "Starter Annual", "amount": 2999000, "currency": "INR"}},
        },
        "pro": {
            "monthly": {"period": "monthly", "interval": 1, "item": {"name": "Pro", "amount": 499900, "currency": "INR"}},
            "annual": {"period": "yearly", "interval": 1, "item": {"name": "Pro Annual", "amount": 4999000, "currency": "INR"}},
        },
        "max": {
            "monthly": {"period": "monthly", "interval": 1, "item": {"name": "Max", "amount": 999900, "currency": "INR"}},
            "annual": {"period": "yearly", "interval": 1, "item": {"name": "Max Annual", "amount": 9999000, "currency": "INR"}},
        },
        "scale": {
            "monthly": {"period": "monthly", "interval": 1, "item": {"name": "Scale", "amount": 9999900, "currency": "INR"}},
            "annual": {"period": "yearly", "interval": 1, "item": {"name": "Scale Annual", "amount": 99999000, "currency": "INR"}},
        },
    }
    client = _get_razorpay_client()
    catalog_entry = plan_catalog.get(plan_id, plan_catalog["starter"])
    payload = catalog_entry.get(billing_cycle, catalog_entry["monthly"]).copy()
    payload["notes"] = {"client_id": str(client_id), "plan_id": plan_id, "billing_cycle": billing_cycle}
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


def create_payment_link(client_id, amount, *, plan_id=None, billing_cycle=None, description=None):
    client = _get_razorpay_client()
    notes = {"client_id": str(client_id)}
    if plan_id:
        notes["plan_id"] = str(plan_id)
    if billing_cycle:
        notes["billing_cycle"] = str(billing_cycle)

    payload = {
        "amount": amount,
        "currency": "INR",
        "description": description or f"SynapFlow plan payment for client {client_id}",
        "notes": notes,
    }
    return client.payment_link.create(payload)


def _extract_notes(payload: dict) -> dict:
    payment_notes = payload.get("payload", {}).get("payment", {}).get("entity", {}).get("notes") or {}
    payment_link_notes = payload.get("payload", {}).get("payment_link", {}).get("entity", {}).get("notes") or {}
    order_notes = payload.get("payload", {}).get("order", {}).get("entity", {}).get("notes") or {}
    subscription_notes = payload.get("payload", {}).get("subscription", {}).get("entity", {}).get("notes") or {}
    return {**payment_link_notes, **order_notes, **subscription_notes, **payment_notes}


def _apply_plan_after_payment(db, client_id, plan_id):
    if not client_id or plan_id not in PLANS:
        return

    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        return

    plan = PLANS[plan_id]
    client.plan_id = plan_id
    client.plan = plan_id
    client.monthly_ticket_limit = plan["tickets_per_month"]
    client.trial_ends_at = None


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
        notes = _extract_notes(payload)
        client_id = notes.get("client_id") or payload.get("client_id")
        plan_id = notes.get("plan_id")
        event = EventLog(
            client_id=client_id,
            event_type=f"razorpay:{payload.get('event', 'unknown')}",
            payload=payload,
        )
        db.add(event)

        if payload.get("event") in {"payment_link.paid", "payment.captured", "subscription.activated", "subscription.charged"}:
            _apply_plan_after_payment(db, client_id, plan_id)

        payment = payload.get("payload", {}).get("payment", {}).get("entity", {})
        if payment.get("id"):
            invoice = Invoice(
                client_id=client_id,
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
        logger.exception("Failed to process Razorpay webhook")
        raise
    finally:
        db.close()
