from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import get_current_client
from app.billing.plans import PLANS
from app.billing.usage import get_usage_summary
from app.db.models import Client
from app.db.session import get_db

router = APIRouter(prefix="/api", tags=["billing-api"])


class UpgradePlanRequest(BaseModel):
    plan_id: str


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

    plan = PLANS[payload.plan_id]
    client.plan_id = payload.plan_id
    client.plan = payload.plan_id
    client.monthly_ticket_limit = plan["monthly_tickets"]
    db.commit()
    db.refresh(client)

    return {
        "ok": True,
        "plan_id": client.plan_id,
        "monthly_ticket_limit": client.monthly_ticket_limit,
    }
