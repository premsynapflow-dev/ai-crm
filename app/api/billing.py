from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import get_current_client
from app.billing.plan_application import apply_plan_to_client
from app.billing.plans import PLANS, ALLOWED_UPGRADES, is_upgrade_allowed
from app.billing.razorpay_service import create_payment_link, create_subscription
from app.billing.usage import get_usage_summary
from app.config import get_settings
from app.db.models import Client
from app.db.session import get_db
from app.utils.logging import get_logger

router = APIRouter(prefix="/api", tags=["billing-api"])
settings = get_settings()
logger = get_logger(__name__)


class UpgradePlanRequest(BaseModel):
    plan_id: str
    billing_cycle: str = Field(default="monthly", pattern="^(monthly|annual)$")


@router.get("/usage")
def get_usage(client: Client = Depends(get_current_client)):
    return get_usage_summary(client.id)


@router.post("/upgrade")
def upgrade_plan(
    payload: UpgradePlanRequest,
    db: Session = Depends(get_db),
    client: Client = Depends(get_current_client),
):
    if not payload.plan_id:
        logger.warning("upgrade_plan called without plan_id for client %s", client.id)
        raise HTTPException(status_code=400, detail="plan_id is required")

    plan = PLANS.get(payload.plan_id)
    if not plan:
        logger.warning("upgrade_plan unknown plan_id=%s for client %s", payload.plan_id, client.id)
        raise HTTPException(status_code=400, detail="Unknown plan")

    if payload.plan_id == "enterprise":
        raise HTTPException(status_code=400, detail="Enterprise requires sales contact")

    current_plan = client.plan_id or "free"
    if not is_upgrade_allowed(current_plan, payload.plan_id):
        logger.warning(
            "upgrade not allowed current_plan=%s target_plan=%s allowed=%s",
            current_plan,
            payload.plan_id,
            ALLOWED_UPGRADES.get(current_plan),
        )
        raise HTTPException(status_code=400, detail="Upgrade not allowed")

    price = plan.get("annual_price") if payload.billing_cycle == "annual" else plan.get("monthly_price")
    if price is None:
        logger.warning("upgrade_plan plan_id=%s has no price for cycle=%s", payload.plan_id, payload.billing_cycle)
        raise HTTPException(status_code=400, detail="Selected plan does not have a fixed price; please contact sales")

    logger.info(
        "upgrade_plan request client=%s current_plan=%s target_plan=%s billing_cycle=%s price=%s",
        client.id,
        client.plan_id,
        payload.plan_id,
        payload.billing_cycle,
        price,
    )
    logger.debug("target plan metadata: %s", plan)

    payment_url = None
    razorpay_subscription_id = None
    plan_applied = False

    # Primary Razorpay workflow: create a subscription for paid plans
    if price > 0:
        if not settings.razorpay_key_id or not settings.razorpay_key_secret:
            logger.error("Razorpay is not configured for upgrade_plan, client=%s", client.id)
            raise HTTPException(status_code=503, detail="Razorpay is not configured")

        try:
            subscription = create_subscription(client.id, payload.plan_id, payload.billing_cycle)
        except Exception:
            logger.exception(
                "Razorpay subscription creation failed for client=%s target_plan=%s, attempting payment link fallback",
                client.id,
                payload.plan_id,
            )

            try:
                payment_link = create_payment_link(
                    client.id,
                    amount=int(price) * 100,
                    plan_id=payload.plan_id,
                    billing_cycle=payload.billing_cycle,
                    description=f"SynapFlow {plan['name']} ({payload.billing_cycle}) plan payment",
                )
                payment_url = payment_link.get("short_url")
                if not payment_url:
                    raise ValueError("Razorpay payment link response missing short_url")
                logger.info(
                    "Razorpay payment link created for upgrade client=%s plan=%s url=%s",
                    client.id,
                    payload.plan_id,
                    payment_url,
                )
            except Exception as exc:
                logger.exception("Unable to initiate Razorpay payment link for client=%s", client.id)
                raise HTTPException(status_code=502, detail="Unable to initiate Razorpay payment") from exc
        else:
            razorpay_subscription_id = subscription.get("id")
            logger.info(
                "Razorpay subscription created client=%s plan=%s subscription_id=%s",
                client.id,
                payload.plan_id,
                razorpay_subscription_id,
            )

            apply_plan_to_client(client, payload.plan_id)
            db.commit()
            db.refresh(client)
            plan_applied = True
    else:
        # Free or zero-cost plan: apply directly
        apply_plan_to_client(client, payload.plan_id)
        db.commit()
        db.refresh(client)
        plan_applied = True

    return {
        "ok": True,
        "status": "payment_pending" if payment_url else "upgraded",
        "plan_id": payload.plan_id,
        "monthly_ticket_limit": plan.get("tickets_per_month", client.monthly_ticket_limit),
        "billing_cycle": payload.billing_cycle,
        "razorpay_plan_id": plan.get("razorpay_plan_ids", {}).get(payload.billing_cycle),
        "razorpay_subscription_id": razorpay_subscription_id,
        "payment_url": payment_url,
        "plan_applied": plan_applied,
    }
