import hashlib
import hmac
import logging
import uuid
from datetime import datetime, timezone

from app.config import get_settings
from app.billing.plan_application import apply_plan_to_client
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
    plan_config = PLANS.get(plan_id)
    if plan_config is None:
        logger.error("create_subscription failed: unknown plan_id=%s", plan_id)
        raise ValueError(f"Unknown plan_id: {plan_id}")

    plan_rate = plan_config.get("annual_price") if billing_cycle == "annual" else plan_config.get("monthly_price")
    razorpay_plan_id = plan_config.get("razorpay_plan_ids", {}).get(billing_cycle)

    logger.info(
        "create_subscription start client_id=%s plan_id=%s plan_rate=%s billing_cycle=%s razorpay_plan_id=%s",
        client_id,
        plan_id,
        plan_rate,
        billing_cycle,
        razorpay_plan_id,
    )

    if not razorpay_plan_id:
        logger.error("create_subscription failed: missing Razorpay plan_id for plan_id=%s billing_cycle=%s", plan_id, billing_cycle)
        raise ValueError("Razorpay subscription plan is not configured")

    if not plan_rate:
        logger.error("create_subscription failed: invalid price for plan_id=%s billing_cycle=%s", plan_id, billing_cycle)
        raise ValueError("invalid plan price")

    client = _get_razorpay_client()

    payload = {
        "plan_id": razorpay_plan_id,
        "total_count": 12 if billing_cycle == "annual" else None,
        "quantity": 1,
        "customer_notify": 1,
        "notes": {"client_id": str(client_id), "plan_id": plan_id, "billing_cycle": billing_cycle},
    }

    # Remove None values for API compatibility
    payload = {k: v for k, v in payload.items() if v is not None}

    logger.debug("create_subscription payload=%s", payload)

    # Validate remote Razorpay plan exists and is active
    try:
        razorpay_plan = client.plan.fetch(razorpay_plan_id)
        logger.debug("razorpay_plan details=%s", razorpay_plan)
        if razorpay_plan.get("status") != "active":
            logger.error("create_subscription failed: Razorpay plan %s is not active", razorpay_plan_id)
            raise ValueError("invalid Razorpay plan")
    except Exception as exc:
        logger.exception("create_subscription failed: unable to validate Razorpay plan %s", razorpay_plan_id)
        raise ValueError("invalid Razorpay plan") from exc

    subscription = client.subscription.create(payload)

    if not subscription or not subscription.get("id"):
        logger.error("create_subscription failed: Razorpay returned invalid response for client_id=%s plan_id=%s", client_id, plan_id)
        raise RuntimeError("invalid Razorpay subscription response")

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

    logger.info(
        "create_payment_link client_id=%s plan_id=%s billing_cycle=%s amount=%s",
        client_id,
        plan_id,
        billing_cycle,
        amount,
    )

    payload = {
        "amount": amount,
        "currency": "INR",
        "description": description or f"SynapFlow plan payment for client {client_id}",
        "notes": notes,
    }

    logger.debug("create_payment_link payload=%s", payload)
    result = client.payment_link.create(payload)

    if not result or not result.get("short_url"):
        logger.error("create_payment_link failed: invalid response for client_id=%s plan_id=%s", client_id, plan_id)
        raise RuntimeError("invalid Razorpay payment link response")

    return result


def _extract_notes(payload: dict) -> dict:
    payment_notes = payload.get("payload", {}).get("payment", {}).get("entity", {}).get("notes") or {}
    payment_link_notes = payload.get("payload", {}).get("payment_link", {}).get("entity", {}).get("notes") or {}
    order_notes = payload.get("payload", {}).get("order", {}).get("entity", {}).get("notes") or {}
    subscription_notes = payload.get("payload", {}).get("subscription", {}).get("entity", {}).get("notes") or {}
    return {**payment_link_notes, **order_notes, **subscription_notes, **payment_notes}


def _parse_client_id(value):
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        logger.warning("Ignoring invalid Razorpay client_id=%s", value)
        return None


def _apply_plan_after_payment(db, client_id, plan_id):
    if not client_id or plan_id not in PLANS:
        return

    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        return

    apply_plan_to_client(client, plan_id)


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
        client_id = _parse_client_id(notes.get("client_id") or payload.get("client_id"))
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
        if payment.get("id") and client_id:
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
        elif payment.get("id"):
            logger.warning("Skipping Razorpay invoice without a valid client_id payment_id=%s", payment.get("id"))
        db.commit()
        return {"status": "ok"}
    except Exception:
        db.rollback()
        logger.exception("Failed to process Razorpay webhook")
        raise
    finally:
        db.close()
