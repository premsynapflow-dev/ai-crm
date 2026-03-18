from fastapi import APIRouter

from app.billing.plans import PLANS

router = APIRouter(prefix="/api", tags=["plans"])


def _humanize_feature(value: str) -> str:
    return value.replace("_", " ").title()


@router.get("/plans")
def get_available_plans():
    return {
        plan_id: {
            "id": plan_id,
            "name": data["name"],
            "price": int(data["price"] / 100) if data["price"] >= 10000 else data["price"],
            "monthly_tickets": data["monthly_tickets"],
            "overage_rate": data.get("overage_price"),
            "features": [_humanize_feature(feature) for feature in data.get("features", [])],
        }
        for plan_id, data in PLANS.items()
    }
