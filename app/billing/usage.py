from datetime import datetime, timedelta, timezone

from app.billing.plans import PLANS
from app.db.models import Client, UsageRecord
from app.db.session import SessionLocal


def _current_period_bounds():
    now = datetime.now(timezone.utc)
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if period_start.month == 12:
        next_month = period_start.replace(year=period_start.year + 1, month=1)
    else:
        next_month = period_start.replace(month=period_start.month + 1)
    period_end = next_month - timedelta(seconds=1)
    return period_start, period_end


def _get_or_create_usage(db, client_id):
    period_start, period_end = _current_period_bounds()
    record = (
        db.query(UsageRecord)
        .filter(
            UsageRecord.client_id == client_id,
            UsageRecord.period_start == period_start,
            UsageRecord.period_end == period_end,
        )
        .first()
    )
    client = db.query(Client).filter(Client.id == client_id).first()
    if record is None:
        record = UsageRecord(
            client_id=client_id,
            period_start=period_start,
            period_end=period_end,
            included_in_plan=client.monthly_ticket_limit if client else 0,
        )
        db.add(record)
        db.flush()
    return record, client


def track_ticket_usage(client_id):
    db = SessionLocal()
    try:
        record, client = _get_or_create_usage(db, client_id)
        record.tickets_processed += 1
        limit = client.monthly_ticket_limit if client else 0
        record.included_in_plan = limit
        record.overage = max(record.tickets_processed - limit, 0)
        record.overage_cost = calculate_overage(client_id, db=db)
        db.commit()
        db.refresh(record)
        return record
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def can_process_ticket(client_id):
    db = SessionLocal()
    try:
        record, client = _get_or_create_usage(db, client_id)
        if client and client.plan_id == "trial":
            if client.trial_ends_at and client.trial_ends_at <= datetime.now(timezone.utc):
                return False
            limit = client.monthly_ticket_limit if client else 0
            if limit <= 0:
                return True
            return record.tickets_processed < limit

        limit = client.monthly_ticket_limit if client else 0
        if limit <= 0:
            return True
        return True
    finally:
        db.close()


def calculate_overage(client_id, db=None):
    owns_session = db is None
    if owns_session:
        db = SessionLocal()

    try:
        record, client = _get_or_create_usage(db, client_id)
        overage = max(record.tickets_processed - (client.monthly_ticket_limit if client else 0), 0)
        plan = PLANS.get(client.plan_id if client else "trial", PLANS["trial"])
        overage_price = plan.get("overage_price", 0)
        return overage * overage_price
    finally:
        if owns_session:
            db.close()


def get_usage_summary(client_id):
    db = SessionLocal()
    try:
        record, client = _get_or_create_usage(db, client_id)
        trial_active = True
        if client and client.plan_id == "trial" and client.trial_ends_at:
            trial_active = client.trial_ends_at > datetime.now(timezone.utc)
        return {
            "client_id": str(client_id),
            "plan_id": client.plan_id if client else "trial",
            "monthly_limit": client.monthly_ticket_limit if client else 0,
            "tickets_processed": record.tickets_processed,
            "overage": record.overage,
            "overage_cost": record.overage_cost,
            "trial_ends_at": client.trial_ends_at.isoformat() if client and client.trial_ends_at else None,
            "trial_active": trial_active,
            "period_start": record.period_start.isoformat(),
            "period_end": record.period_end.isoformat(),
        }
    finally:
        db.close()
