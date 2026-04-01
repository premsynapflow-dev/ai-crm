from datetime import datetime, timedelta, timezone

from sqlalchemy import func

from app.billing.plans import PLANS
from app.db.models import Client, Complaint, UsageRecord
from app.db.session import SessionLocal
from app.middleware.quota_enforcer import QuotaEnforcer


def _as_utc(value):
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


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


def _format_day_label(day) -> str:
    return day.strftime("%b %d").replace(" 0", " ")


def track_ticket_usage(client_id):
    db = SessionLocal()
    try:
        record, client = _get_or_create_usage(db, client_id)
        record.tickets_processed += 1
        limit = client.monthly_ticket_limit if client else 0
        record.included_in_plan = limit
        record.overage = max(record.tickets_processed - limit, 0)
        record.overage_cost = calculate_overage(client_id, db=db)
        QuotaEnforcer.increment_usage(client_id, "tickets", db=db)
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
        if client and client.plan_id == "starter":
            trial_ends_at = _as_utc(client.trial_ends_at)
            if trial_ends_at and trial_ends_at <= datetime.now(timezone.utc):
                return False
            limit = client.monthly_ticket_limit if client else 0
            if limit <= 0:
                return _check_db_quota_if_supported(db, client)
            if record.tickets_processed >= limit:
                return False
        if client is None:
            return True
        return _check_db_quota_if_supported(db, client)
    finally:
        db.close()


def calculate_overage(client_id, db=None):
    owns_session = db is None
    if owns_session:
        db = SessionLocal()

    try:
        record, client = _get_or_create_usage(db, client_id)
        overage = max(record.tickets_processed - (client.monthly_ticket_limit if client else 0), 0)
        plan = PLANS.get(client.plan_id if client else "free", PLANS["free"])
        overage_price = plan.get("overage_rate", plan.get("overage_price", 0))
        return overage * overage_price
    finally:
        if owns_session:
            db.close()


def _check_db_quota_if_supported(db, client) -> bool:
    if not hasattr(db, "query"):
        return True
    return QuotaEnforcer.check_ticket_quota(client, db=db)


def get_usage_summary(client_id):
    db = SessionLocal()
    try:
        record, client = _get_or_create_usage(db, client_id)
        trial_active = False
        if client and client.trial_ends_at:
            trial_active = _as_utc(client.trial_ends_at) > datetime.now(timezone.utc)
        now = datetime.now(timezone.utc)
        current_usage = int(record.tickets_processed or 0)
        monthly_limit = int(client.monthly_ticket_limit if client else 0)
        remaining_tickets = max(monthly_limit - current_usage, 0)
        usage_percentage = round((current_usage / monthly_limit) * 100, 2) if monthly_limit else 0.0
        total_days = max((record.period_end.date() - record.period_start.date()).days + 1, 1)
        elapsed_days = max((min(now, record.period_end).date() - record.period_start.date()).days + 1, 1)
        days_remaining = max((record.period_end.date() - now.date()).days, 0)
        daily_average = round(current_usage / elapsed_days, 2) if elapsed_days else 0.0
        projected_usage = int(round(daily_average * total_days))

        history_rows = (
            db.query(
                func.date(Complaint.created_at).label("day"),
                func.count(Complaint.id).label("count"),
            )
            .filter(
                Complaint.client_id == client_id,
                Complaint.created_at >= record.period_start,
                Complaint.created_at <= record.period_end,
            )
            .group_by(func.date(Complaint.created_at))
            .order_by(func.date(Complaint.created_at))
            .all()
        )
        counts_by_day = {row.day: int(row.count) for row in history_rows}
        history = []
        peak_day = None
        peak_day_count = 0
        for offset in range(total_days):
            day = record.period_start.date() + timedelta(days=offset)
            count = counts_by_day.get(day, 0)
            label = _format_day_label(day)
            history.append({"date": label, "tickets": count})
            if count > peak_day_count:
                peak_day = label
                peak_day_count = count

        category_rows = (
            db.query(Complaint.category, func.count(Complaint.id).label("count"))
            .filter(
                Complaint.client_id == client_id,
                Complaint.created_at >= record.period_start,
                Complaint.created_at <= record.period_end,
            )
            .group_by(Complaint.category)
            .order_by(func.count(Complaint.id).desc())
            .all()
        )
        category_breakdown = [
            {
                "category": str(row.category or "unknown"),
                "tickets": int(row.count),
            }
            for row in category_rows
        ]
        plan = PLANS.get(client.plan_id if client else "free", PLANS["free"])
        return {
            "client_id": str(client_id),
            "plan_id": client.plan_id if client else "free",
            "monthly_limit": monthly_limit,
            "tickets_processed": record.tickets_processed,
            "overage": record.overage,
            "overage_cost": record.overage_cost,
            "trial_ends_at": _as_utc(client.trial_ends_at).isoformat() if client and client.trial_ends_at else None,
            "trial_active": trial_active,
            "period_start": record.period_start.isoformat(),
            "period_end": record.period_end.isoformat(),
            "current_usage": current_usage,
            "remaining_tickets": remaining_tickets,
            "usage_percentage": usage_percentage,
            "projected_usage": projected_usage,
            "days_remaining": days_remaining,
            "days_total": total_days,
            "elapsed_days": elapsed_days,
            "daily_average": daily_average,
            "peak_day": peak_day,
            "peak_day_count": peak_day_count,
            "history": history,
            "category_breakdown": category_breakdown,
            "overage_rate": plan.get("overage_rate", plan.get("overage_price", 0)),
        }
    finally:
        db.close()
