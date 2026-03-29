import uuid
from datetime import datetime, timedelta, timezone

from app.billing.plans import PLANS
from app.db.models import Client, PlanFeature, TenantUsageTracking
from app.middleware.quota_enforcer import QuotaEnforcer


def test_customer_360_feature_gate_blocks_starter_plan(test_db, client, test_client_record):
    test_client_record.plan_id = "starter"
    test_client_record.plan = "starter"
    test_db.commit()

    response = client.get(
        "/api/v1/customers",
        headers={"x-api-key": test_client_record.api_key},
    )

    assert response.status_code == 403
    body = response.json()
    assert body["detail"]["feature_flag"] == "customer_360"
    assert body["detail"]["current_plan"] == "Starter"
    assert body["detail"]["required_plan"] == "Pro"


def test_quota_enforcer_uses_plan_overrides_and_unlimited_enterprise(test_db):
    now = datetime.now(timezone.utc)
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    period_end = (period_start + timedelta(days=32)).replace(day=1) - timedelta(seconds=1)

    starter = Client(
        id=uuid.uuid4(),
        name="Starter Client",
        api_key="starter-key",
        plan="starter",
        plan_id="starter",
        monthly_ticket_limit=500,
        trial_ends_at=now + timedelta(days=30),
    )
    enterprise = Client(
        id=uuid.uuid4(),
        name="Enterprise Client",
        api_key="enterprise-key",
        plan="enterprise",
        plan_id="enterprise",
        monthly_ticket_limit=999999,
        trial_ends_at=now + timedelta(days=30),
    )
    test_db.add_all([starter, enterprise])
    test_db.add_all(
        [
            PlanFeature(
                plan_name="starter",
                features={"ticketing_state_machine": True, "customer_360": False},
                limits={"tickets_per_month": 1, "api_calls_per_day": 10, "users": 3},
            ),
            PlanFeature(
                plan_name="enterprise",
                features={"ticketing_state_machine": True, "customer_360": True, "auto_escalation": True},
                limits={"tickets_per_month": -1, "api_calls_per_day": -1, "users": -1},
            ),
        ]
    )
    test_db.flush()
    test_db.add(
        TenantUsageTracking(
            client_id=starter.id,
            resource_type="tickets",
            usage_count=1,
            period_start=period_start,
            period_end=period_end,
        )
    )
    test_db.add(
        TenantUsageTracking(
            client_id=enterprise.id,
            resource_type="tickets",
            usage_count=99999,
            period_start=period_start,
            period_end=period_end,
        )
    )
    test_db.commit()

    assert QuotaEnforcer.check_ticket_quota(starter, db=test_db) is False
    assert QuotaEnforcer.check_ticket_quota(enterprise, db=test_db) is True

    starter_limits = PLANS["starter"]["feature_flags"]
    assert starter_limits["customer_360"] is False
    assert PLANS["enterprise"]["feature_flags"]["auto_escalation"] is True
