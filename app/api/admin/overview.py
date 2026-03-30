"""
Admin dashboard routes for platform-level visibility and tenant management.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.db.models import AIReplyQueue, Client, Complaint, Customer, Subscription
from app.db.session import get_db
from app.dependencies.auth import get_current_admin_user

router = APIRouter(prefix="/admin", tags=["admin"])

PLAN_LIMITS = {
    "starter": 50,
    "growth": 500,
    "enterprise": -1,
}


@router.get("/dashboard/overview")
async def get_admin_overview(
    db: Session = Depends(get_db),
    admin_user: dict = Depends(get_current_admin_user),
):
    """
    Return aggregate platform metrics across all tenants for administrators.
    """
    _ = admin_user

    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    total_tenants = db.query(func.count(Client.id)).scalar() or 0
    active_tenants = (
        db.query(func.count(func.distinct(Complaint.client_id)))
        .filter(Complaint.created_at >= thirty_days_ago)
        .scalar()
        or 0
    )
    total_tickets = db.query(func.count(Complaint.id)).scalar() or 0
    tickets_this_month = (
        db.query(func.count(Complaint.id))
        .filter(Complaint.created_at >= month_start)
        .scalar()
        or 0
    )
    total_customers = (
        db.query(func.count(Customer.id))
        .filter(Customer.is_master.is_(True))
        .scalar()
        or 0
    )

    total_auto_replies = db.query(func.count(AIReplyQueue.id)).scalar() or 0
    auto_approved = (
        db.query(func.count(AIReplyQueue.id))
        .filter(AIReplyQueue.status == "approved")
        .scalar()
        or 0
    )
    auto_approval_rate = (auto_approved / total_auto_replies * 100) if total_auto_replies else 0

    active_subscriptions = (
        db.query(func.count(Subscription.id))
        .filter(Subscription.status == "active")
        .scalar()
        or 0
    )

    tenants_by_plan = (
        db.query(Client.plan, func.count(Client.id).label("count"))
        .group_by(Client.plan)
        .all()
    )

    recent_signups = db.query(Client).order_by(desc(Client.created_at)).limit(10).all()

    top_tenants = (
        db.query(
            Client.name,
            Client.plan,
            func.count(Complaint.id).label("ticket_count"),
        )
        .join(Complaint, Client.id == Complaint.client_id)
        .group_by(Client.id, Client.name, Client.plan)
        .order_by(desc("ticket_count"))
        .limit(10)
        .all()
    )

    total_with_sla = (
        db.query(func.count(Complaint.id))
        .filter(Complaint.sla_due_at.isnot(None))
        .scalar()
        or 0
    )
    sla_compliant = (
        db.query(func.count(Complaint.id))
        .filter(Complaint.sla_due_at.isnot(None), Complaint.sla_status != "breached")
        .scalar()
        or 0
    )
    sla_compliance_rate = (sla_compliant / total_with_sla * 100) if total_with_sla else 0

    return {
        "overview": {
            "total_tenants": total_tenants,
            "active_tenants": active_tenants,
            "total_tickets": total_tickets,
            "tickets_this_month": tickets_this_month,
            "total_customers": total_customers,
            "active_subscriptions": active_subscriptions,
        },
        "auto_reply_metrics": {
            "total_generated": total_auto_replies,
            "auto_approved": auto_approved,
            "approval_rate": round(auto_approval_rate, 2),
        },
        "sla_metrics": {
            "compliance_rate": round(sla_compliance_rate, 2),
            "total_tracked": total_with_sla,
        },
        "tenants_by_plan": {plan or "unknown": count for plan, count in tenants_by_plan},
        "recent_signups": [
            {
                "id": str(client.id),
                "name": client.name,
                "plan": client.plan,
                "created_at": client.created_at.isoformat(),
            }
            for client in recent_signups
        ],
        "top_tenants": [
            {
                "name": name,
                "plan": plan,
                "ticket_count": count,
            }
            for name, plan, count in top_tenants
        ],
    }


@router.get("/tenants")
async def list_all_tenants(
    skip: int = 0,
    limit: int = 50,
    search: str | None = None,
    db: Session = Depends(get_db),
    admin_user: dict = Depends(get_current_admin_user),
):
    """List tenants for platform administration with optional search."""
    _ = admin_user

    query = db.query(Client)
    if search:
        query = query.filter(Client.name.ilike(f"%{search.strip()}%"))

    total = query.count()
    tenants = query.order_by(desc(Client.created_at)).offset(skip).limit(limit).all()

    return {
        "total": total,
        "tenants": [
            {
                "id": str(tenant.id),
                "name": tenant.name,
                "plan": tenant.plan,
                "created_at": tenant.created_at.isoformat(),
                "monthly_limit": tenant.monthly_ticket_limit,
            }
            for tenant in tenants
        ],
    }


@router.post("/tenants/{tenant_id}/upgrade-plan")
async def upgrade_tenant_plan(
    tenant_id: str,
    new_plan: str,
    db: Session = Depends(get_db),
    admin_user: dict = Depends(get_current_admin_user),
):
    """Update a tenant plan and the associated usage limit."""
    _ = admin_user

    normalized_plan = new_plan.strip().lower()
    if normalized_plan not in PLAN_LIMITS:
        raise HTTPException(status_code=400, detail="Invalid plan")

    tenant = db.query(Client).filter(Client.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    old_plan = tenant.plan
    tenant.plan = normalized_plan
    tenant.plan_id = normalized_plan
    tenant.monthly_ticket_limit = PLAN_LIMITS[normalized_plan]
    db.commit()

    return {
        "success": True,
        "tenant_id": str(tenant.id),
        "old_plan": old_plan,
        "new_plan": normalized_plan,
    }
