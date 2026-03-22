from fastapi import Depends, HTTPException

from app.auth import get_current_client
from app.billing.plans import PLAN_ORDER, PLANS
from app.db.models import Client


def _feature_enabled(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() not in {"", "false", "none", "basic"}
    if isinstance(value, (int, float)):
        return value > 0
    return bool(value)


def get_required_plan(feature_flag: str) -> str:
    for plan_id in PLAN_ORDER:
        plan = PLANS.get(plan_id, {})
        feature_flags = plan.get("feature_flags", {})
        if _feature_enabled(feature_flags.get(feature_flag)):
            return plan.get("name", plan_id.title())
    return "Enterprise"


def ensure_feature_access(client: Client, feature_flag: str) -> dict:
    plan = PLANS.get(client.plan_id)
    if not plan:
        raise HTTPException(status_code=403, detail="Invalid plan")

    feature_flags = plan.get("feature_flags", {})
    if _feature_enabled(feature_flags.get(feature_flag)):
        return plan

    required_plan_name = get_required_plan(feature_flag)
    raise HTTPException(
        status_code=403,
        detail={
            "message": f"This feature requires {required_plan_name} plan or higher",
            "feature_flag": feature_flag,
            "required_plan": required_plan_name,
            "current_plan": plan.get("name", client.plan_id),
        },
    )


def require_feature(feature_flag: str):
    def dependency(client: Client = Depends(get_current_client)) -> dict:
        return ensure_feature_access(client, feature_flag)

    return dependency
