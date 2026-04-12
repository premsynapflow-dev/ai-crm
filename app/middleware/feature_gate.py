import uuid

from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.auth import get_current_client
from app.billing.plans import PLAN_ORDER, PLANS
from app.db.models import Client, PlanFeature
from app.db.session import SessionLocal
from app.middleware.rls_context import resolve_client_id_from_request


FEATURES = {
    "ticketing_state_machine": ["starter", "pro", "max", "scale", "enterprise"],
    "sla_management": ["pro", "max", "scale", "enterprise"],
    "customer_360": ["pro", "max", "scale", "enterprise"],
    "auto_reply_approval_queue": ["starter", "pro", "max", "scale", "enterprise"],
    "rbi_compliance": ["scale", "enterprise"],
    "auto_escalation": ["enterprise"],
}


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


def _default_limits_for_plan(plan_id: str) -> dict:
    plan = PLANS.get(plan_id, {})
    return {
        "tickets_per_month": plan.get("tickets_per_month", 0),
        "api_calls_per_day": plan.get("api_calls_per_day", -1),
        "users": plan.get("team_seats", 0),
    }


def get_plan_configuration(plan_id: str, db=None) -> tuple[dict, dict]:
    static_plan = PLANS.get(plan_id, {})
    features = dict(static_plan.get("feature_flags", {}))
    limits = _default_limits_for_plan(plan_id)

    if db is not None:
        try:
            plan_record = db.query(PlanFeature).filter(PlanFeature.plan_name == plan_id).first()
        except Exception:
            plan_record = None
        if plan_record:
            features.update(plan_record.features or {})
            limits.update(plan_record.limits or {})

    return features, limits


def has_feature_access(client: Client, feature_flag: str, db=None) -> bool:
    if feature_flag in FEATURES and client.plan_id in FEATURES[feature_flag]:
        return True

    feature_flags, _ = get_plan_configuration(client.plan_id, db=db)
    return _feature_enabled(feature_flags.get(feature_flag))


def get_required_plan(feature_flag: str, db=None) -> str:
    for plan_id in PLAN_ORDER:
        if feature_flag in FEATURES and plan_id in FEATURES[feature_flag]:
            return PLANS.get(plan_id, {}).get("name", plan_id.title())
        feature_flags, _ = get_plan_configuration(plan_id, db=db)
        if _feature_enabled(feature_flags.get(feature_flag)):
            plan = PLANS.get(plan_id, {})
            return plan.get("name", plan_id.title())
    return "Enterprise"


def get_plan_limits(client: Client, db=None) -> dict:
    _, limits = get_plan_configuration(client.plan_id, db=db)
    return limits


def ensure_feature_access(client: Client, feature_flag: str, db=None) -> dict:
    plan = PLANS.get(client.plan_id)
    if not plan:
        raise HTTPException(status_code=403, detail="Invalid plan")

    if has_feature_access(client, feature_flag, db=db):
        return plan

    required_plan_name = get_required_plan(feature_flag, db=db)
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


class FeatureGateMiddleware(BaseHTTPMiddleware):
    FEATURE_MAP = {
        "/api/v1/reply-queue": "auto_reply_approval_queue",
        "/api/v1/rbi-compliance": "rbi_compliance",
    }

    async def dispatch(self, request: Request, call_next):
        required_feature = self._get_required_feature(request.url.path)
        if not required_feature:
            return await call_next(request)

        client = self._resolve_client(request)
        if client:
            db = SessionLocal()
            try:
                if not has_feature_access(client, required_feature, db=db):
                    required_plan_name = get_required_plan(required_feature, db=db)
                    return JSONResponse(
                        status_code=403,
                        content={
                            "detail": {
                                "message": f"This feature requires {required_plan_name} plan or higher",
                                "feature_flag": required_feature,
                                "required_plan": required_plan_name,
                                "current_plan": PLANS.get(client.plan_id, {}).get("name", client.plan_id),
                            }
                        },
                    )
            finally:
                db.close()

        return await call_next(request)

    def _get_required_feature(self, path: str) -> str | None:
        for route_prefix, feature_flag in self.FEATURE_MAP.items():
            if path.startswith(route_prefix):
                return feature_flag
        return None

    def _resolve_client(self, request: Request) -> Client | None:
        client_id = resolve_client_id_from_request(request)
        if not client_id:
            return None

        db = SessionLocal()
        try:
            return db.query(Client).filter(Client.id == self._as_uuid(client_id)).first()
        finally:
            db.close()

    @staticmethod
    def _as_uuid(value):
        if isinstance(value, uuid.UUID):
            return value
        try:
            return uuid.UUID(str(value))
        except (TypeError, ValueError):
            return value
