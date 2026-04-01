from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.billing.plans import PLANS
from app.billing.razorpay_service import create_payment_link, create_subscription, handle_webhook
from app.billing.usage import get_usage_summary
from app.config import get_settings
from app.db.models import Client, Subscription
from app.db.session import SessionLocal, get_db
from app.utils.webhook_security import verify_razorpay_signature

router = APIRouter(prefix="/billing", tags=["billing"])
settings = get_settings()


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
    return create_subscription(client.id, payload.plan_id, payload.billing_cycle)


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
    client = _get_client_by_api_key(x_api_key)
    db = SessionLocal()
    try:
        db_client = db.query(Client).filter(Client.id == client.id).first()
        if not db_client:
            raise HTTPException(status_code=404, detail="Client not found")
        plan = PLANS[payload.plan_id]
        if payload.plan_id == "enterprise":
            raise HTTPException(status_code=400, detail="Enterprise requires sales contact")
        price = plan["annual_price"] if payload.billing_cycle == "annual" else plan["monthly_price"]
        payment_url = None
        plan_applied = False

        if price:
            if not settings.razorpay_key_id or not settings.razorpay_key_secret:
                raise HTTPException(status_code=503, detail="Razorpay is not configured")
            try:
                payment_link = create_payment_link(
                    client.id,
                    int(price) * 100,
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
            db_client.plan_id = payload.plan_id
            db_client.plan = payload.plan_id
            db_client.monthly_ticket_limit = plan["tickets_per_month"]
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
