from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import get_current_client
from app.billing.plans import PLANS
from app.billing.razorpay_service import create_payment_link
from app.billing.usage import get_usage_summary
from app.config import get_settings
from app.db.models import Client
from app.db.session import get_db

router = APIRouter(prefix="/api", tags=["billing-api"])
settings = get_settings()


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
    if payload.plan_id not in PLANS:
        raise HTTPException(status_code=400, detail="Unknown plan")
    if payload.plan_id == "enterprise":
        raise HTTPException(status_code=400, detail="Enterprise requires sales contact")

    plan = PLANS[payload.plan_id]
    price = plan["annual_price"] if payload.billing_cycle == "annual" else plan["monthly_price"]
    payment_url = None
    plan_applied = False

    if price:
        if not settings.razorpay_key_id or not settings.razorpay_key_secret:
            raise HTTPException(status_code=503, detail="Razorpay is not configured")
        try:
            payment_link = create_payment_link(
                client.id,
                amount=int(price) * 100,
                plan_id=payload.plan_id,
                billing_cycle=payload.billing_cycle,
                description=f"SynapFlow {plan['name']} ({payload.billing_cycle}) plan payment",
            )
            payment_url = payment_link.get("short_url")
        except Exception as exc:
            raise HTTPException(status_code=502, detail="Unable to initiate Razorpay payment") from exc

        if not payment_url:
            raise HTTPException(status_code=502, detail="Razorpay payment link was not created")
    else:
        client.plan_id = payload.plan_id
        client.plan = payload.plan_id
        client.monthly_ticket_limit = plan["tickets_per_month"]
        if payload.plan_id == "starter" and plan.get("trial_days"):
            client.trial_ends_at = client.trial_ends_at or (
                datetime.now(timezone.utc) + timedelta(days=plan["trial_days"])
            )
        else:
            client.trial_ends_at = None
        db.commit()
        db.refresh(client)
        plan_applied = True

    return {
        "ok": True,
        "plan_id": payload.plan_id if payment_url else client.plan_id,
        "monthly_ticket_limit": plan["tickets_per_month"] if payment_url else client.monthly_ticket_limit,
        "billing_cycle": payload.billing_cycle,
        "razorpay_plan_id": plan.get("razorpay_plan_ids", {}).get(payload.billing_cycle),
        "payment_url": payment_url,
        "plan_applied": plan_applied,
    }
