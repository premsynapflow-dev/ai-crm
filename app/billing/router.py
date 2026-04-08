from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.billing.plan_application import apply_plan_to_client
from app.billing.plans import PLANS, ALLOWED_UPGRADES, is_upgrade_allowed
from app.billing.razorpay_service import create_payment_link, create_subscription, handle_webhook
from app.billing.usage import get_usage_summary
from app.config import get_settings
from app.db.models import Client, Subscription
from app.db.session import SessionLocal, get_db
from app.utils.logging import get_logger
from app.utils.webhook_security import verify_razorpay_signature

router = APIRouter(prefix="/billing", tags=["billing"])
settings = get_settings()
logger = get_logger(__name__)


class CheckoutRequest(BaseModel):
    plan_id: str = Field(..., pattern="^(starter|pro|max|scale|enterprise)$")
    billing_cycle: str = Field(default="monthly", pattern="^(monthly|annual)$")


class UpgradeRequest(BaseModel):
    plan_id: str = Field(..., pattern="^(starter|pro|max|scale|enterprise)$")
    billing_cycle: str = Field(default="monthly", pattern="^(monthly|annual)$")


def _get_client_by_api_key(x_api_key: str) -> Client:
    db = SessionLocal()
    try:
        client = db.query(Client).filter(Client.api_key == x_api_key).first()
        if not client:
            raise HTTPException(status_code=401, detail="Invalid API key")
        db.expunge(client)
        return client
    finally:
        db.close()


@router.post("/checkout")
def billing_checkout(payload: CheckoutRequest, x_api_key: str = Header(default="", alias="x-api-key")):
    client = _get_client_by_api_key(x_api_key)
    plan = PLANS.get(payload.plan_id)
    if not plan:
        raise HTTPException(status_code=400, detail="Unknown plan")

    price = plan.get("annual_price") if payload.billing_cycle == "annual" else plan.get("monthly_price")
    if price is None:
        raise HTTPException(status_code=400, detail="Selected plan does not have a fixed price; contact support")

    try:
        subscription = create_subscription(client.id, payload.plan_id, payload.billing_cycle)
    except Exception:
        logger.exception("Razorpay subscription checkout failed; falling back to payment link; client=%s", client.id)
        payment_link = create_payment_link(
            client.id,
            int(price) * 100,
            plan_id=payload.plan_id,
            billing_cycle=payload.billing_cycle,
            description=f"SynapFlow {plan['name']} ({payload.billing_cycle}) plan payment",
        )
        payment_url = payment_link.get("short_url")
        if not payment_url:
            raise HTTPException(status_code=502, detail="Unable to initiate Razorpay payment")
        return {
            "status": "payment_pending",
            "plan_id": payload.plan_id,
            "billing_cycle": payload.billing_cycle,
            "payment_url": payment_url,
            "plan_applied": False,
        }

    db = SessionLocal()
    try:
        db_client = db.query(Client).filter(Client.id == client.id).first()
        if not db_client:
            raise HTTPException(status_code=404, detail="Client not found")
        apply_plan_to_client(db_client, payload.plan_id)
        db.commit()
    finally:
        db.close()
    return {
        "status": "upgraded",
        "plan_id": payload.plan_id,
        "billing_cycle": payload.billing_cycle,
        "razorpay_plan_id": plan.get("razorpay_plan_ids", {}).get(payload.billing_cycle),
        "razorpay_subscription_id": subscription.get("id"),
        "payment_url": None,
        "plan_applied": True,
    }


@router.post("/webhook/razorpay")
async def razorpay_webhook(request: Request, db: Session = Depends(get_db)):
    settings = get_settings()
    
    # Verify signature
    if settings.razorpay_webhook_secret:
        is_valid = await verify_razorpay_signature(
            request, 
            settings.razorpay_webhook_secret
        )
        if not is_valid:
            raise HTTPException(401, "Invalid webhook signature")
    
    payload = await request.json()
    return handle_webhook(payload)


@router.get("/usage")
def billing_usage(x_api_key: str = Header(default="", alias="x-api-key")):
    client = _get_client_by_api_key(x_api_key)
    return get_usage_summary(client.id)


@router.post("/upgrade")
def billing_upgrade(payload: UpgradeRequest, x_api_key: str = Header(default="", alias="x-api-key")):
    if not payload.plan_id:
        logger.warning("billing_upgrade called without plan_id")
        raise HTTPException(status_code=400, detail="plan_id is required")

    client = _get_client_by_api_key(x_api_key)
    plan = PLANS.get(payload.plan_id)
    if not plan:
        logger.warning("billing_upgrade unknown plan_id=%s", payload.plan_id)
        raise HTTPException(status_code=400, detail="Unknown plan")

    if payload.plan_id == "enterprise":
        raise HTTPException(status_code=400, detail="Enterprise requires sales contact")

    current_plan = client.plan_id or "free"
    allowed = is_upgrade_allowed(current_plan, payload.plan_id)
    logger.debug("billing_upgrade path check current_plan=%s target_plan=%s allowed=%s", current_plan, payload.plan_id, allowed)
    if not allowed:
        logger.warning("billing_upgrade not allowed current_plan=%s target_plan=%s", current_plan, payload.plan_id)
        raise HTTPException(status_code=400, detail="Upgrade not allowed")

    price = plan.get("annual_price") if payload.billing_cycle == "annual" else plan.get("monthly_price")
    if price is None:
        logger.warning("billing_upgrade plan_id=%s has null price for cycle=%s", payload.plan_id, payload.billing_cycle)
        raise HTTPException(status_code=400, detail="Selected plan does not have a fixed price; contact support")

    logger.info(
        "billing_upgrade request client=%s target_plan=%s billing_cycle=%s price=%s",
        client.id,
        payload.plan_id,
        payload.billing_cycle,
        price,
    )
    logger.debug("billing_upgrade target plan details=%s", plan)

    db = SessionLocal()
    try:
        db_client = db.query(Client).filter(Client.id == client.id).first()
        if not db_client:
            raise HTTPException(status_code=404, detail="Client not found")

        payment_url = None
        plan_applied = False

        if price > 0:
            if not settings.razorpay_key_id or not settings.razorpay_key_secret:
                logger.error("Razorpay not configured for billing_upgrade client=%s", client.id)
                raise HTTPException(status_code=503, detail="Razorpay is not configured")

            # Prefer subscription creation for plan upgrades
            try:
                subscription = create_subscription(client.id, payload.plan_id, payload.billing_cycle)
            except Exception:
                logger.exception("Razorpay subscription creation failed; falling back to payment link; client=%s", client.id)
                try:
                    payment_link = create_payment_link(
                        client.id,
                        int(price) * 100,
                        plan_id=payload.plan_id,
                        billing_cycle=payload.billing_cycle,
                        description=f"SynapFlow {plan['name']} ({payload.billing_cycle}) plan payment",
                    )
                    payment_url = payment_link.get("short_url")
                    if not payment_url:
                        raise ValueError("no short_url returned by Razorpay payment link")
                    logger.info("Razorpay payment link for upgrade client=%s plan=%s url=%s", client.id, payload.plan_id, payment_url)
                except Exception as exc:
                    logger.exception("Unable to initiate Razorpay payment link for client=%s", client.id)
                    raise HTTPException(status_code=502, detail="Unable to initiate Razorpay payment") from exc
            else:
                logger.info(
                    "Razorpay subscription created client=%s plan=%s subscription_id=%s",
                    client.id,
                    payload.plan_id,
                    subscription.get("id"),
                )

                apply_plan_to_client(db_client, payload.plan_id)
                db.commit()
                plan_applied = True
        else:
            apply_plan_to_client(db_client, payload.plan_id)
            subscription = (
                db.query(Subscription)
                .filter(Subscription.client_id == client.id)
                .order_by(Subscription.created_at.desc())
                .first()
            )
            if subscription:
                subscription.plan = payload.plan_id
                subscription.status = "active"
            db.commit()
            plan_applied = True

        return {
            "status": "payment_pending" if payment_url else "upgraded",
            "plan_id": payload.plan_id,
            "billing_cycle": payload.billing_cycle,
            "payment_url": payment_url,
            "plan_applied": plan_applied,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/cancel")
def billing_cancel(x_api_key: str = Header(default="", alias="x-api-key")):
    client = _get_client_by_api_key(x_api_key)
    db = SessionLocal()
    try:
        subscription = (
            db.query(Subscription)
            .filter(Subscription.client_id == client.id)
            .order_by(Subscription.created_at.desc())
            .first()
        )
        if subscription:
            subscription.status = "cancelled"
        db.commit()
        return {"status": "cancelled"}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
