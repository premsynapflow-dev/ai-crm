from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.db.models import Client, TenantUsageTracking
from app.db.session import SessionLocal
from app.middleware.feature_gate import get_plan_limits


class QuotaEnforcer:
    """Enforce DB-backed usage quotas without breaking existing billing logic."""

    @staticmethod
    def _effective_limit(client: Client, resource_type: str, limits: dict) -> int | None:
        if resource_type == "tickets":
            configured_limit = limits.get("tickets_per_month", -1)
            custom_limit = getattr(client, "monthly_ticket_limit", None)
            if custom_limit is not None and int(custom_limit) > 0:
                if configured_limit in {None, -1}:
                    return int(custom_limit)
                return min(int(configured_limit), int(custom_limit))
            return None if configured_limit in {None, -1} else int(configured_limit)

        if resource_type == "api_calls":
            configured_limit = limits.get("api_calls_per_day", -1)
            return None if configured_limit in {None, -1} else int(configured_limit)

        configured_limit = limits.get(resource_type, -1)
        return None if configured_limit in {None, -1} else int(configured_limit)

    @staticmethod
    def current_period_bounds(reference: datetime | None = None) -> tuple[datetime, datetime]:
        now = reference or datetime.now(timezone.utc)
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if period_start.month == 12:
            next_month = period_start.replace(year=period_start.year + 1, month=1)
        else:
            next_month = period_start.replace(month=period_start.month + 1)
        period_end = next_month - timedelta(seconds=1)
        return period_start, period_end

    @classmethod
    def check_ticket_quota(cls, client: Client, db: Session | None = None) -> bool:
        return cls.check_resource_quota(client, "tickets", db=db)

    @classmethod
    def check_resource_quota(cls, client: Client, resource_type: str, db: Session | None = None) -> bool:
        owns_session = db is None
        if owns_session:
            db = SessionLocal()

        try:
            limits = get_plan_limits(client, db=db)
            limit = cls._effective_limit(client, resource_type, limits)
            if limit is None:
                return True

            period_start, _ = cls.current_period_bounds()
            usage = (
                db.query(TenantUsageTracking)
                .filter(
                    TenantUsageTracking.client_id == client.id,
                    TenantUsageTracking.resource_type == resource_type,
                    TenantUsageTracking.period_start == period_start,
                )
                .first()
            )
            current_usage = usage.usage_count if usage else 0
            return int(current_usage) < limit
        finally:
            if owns_session:
                db.close()

    @classmethod
    def increment_usage(
        cls,
        client_id,
        resource_type: str,
        amount: int = 1,
        db: Session | None = None,
    ) -> TenantUsageTracking:
        owns_session = db is None
        if owns_session:
            db = SessionLocal()

        try:
            period_start, period_end = cls.current_period_bounds()
            usage = (
                db.query(TenantUsageTracking)
                .filter(
                    TenantUsageTracking.client_id == client_id,
                    TenantUsageTracking.resource_type == resource_type,
                    TenantUsageTracking.period_start == period_start,
                )
                .first()
            )
            if usage is None:
                usage = TenantUsageTracking(
                    client_id=client_id,
                    resource_type=resource_type,
                    usage_count=0,
                    period_start=period_start,
                    period_end=period_end,
                )
                db.add(usage)

            usage.usage_count += int(amount)
            if owns_session:
                db.commit()
                db.refresh(usage)
            else:
                db.flush()
            return usage
        finally:
            if owns_session:
                db.close()
