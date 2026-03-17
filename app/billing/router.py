from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.billing.plans import PLANS
from app.billing.razorpay_service import create_payment_link, create_subscription, handle_webhook
from app.billing.usage import get_usage_summary
from app.config import get_settings
from app.db.models import Client, Subscription
from app.db.session import SessionLocal

router = APIRouter(prefix="/billing", tags=["billing"])
settings = get_settings()


class CheckoutRequest(BaseModel):
    plan_id: str = Field(..., pattern="^(trial|pro|business)$")


class UpgradeRequest(BaseModel):
    plan_id: str = Field(..., pattern="^(trial|pro|business)$")


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
    return create_subscription(client.id, payload.plan_id)


@router.post("/webhook/razorpay")
def razorpay_webhook(payload: dict):
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
        db_client.plan_id = payload.plan_id
        db_client.plan = payload.plan_id
        db_client.monthly_ticket_limit = plan["monthly_tickets"]
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
        return {"status": "upgraded", "plan_id": payload.plan_id}
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
