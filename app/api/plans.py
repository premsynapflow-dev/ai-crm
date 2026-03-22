from fastapi import APIRouter

from app.billing.plans import PLANS

router = APIRouter(prefix="/api", tags=["plans"])


@router.get("/plans")
def get_available_plans():
    """Get all available subscription plans with the SynapFlow pricing catalog."""
    return PLANS
