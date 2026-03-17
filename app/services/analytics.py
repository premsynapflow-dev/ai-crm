from datetime import datetime, timedelta, timezone

from sqlalchemy import func

from app.db.models import Complaint, MaterializedAnalytics


def complaint_category_breakdown(db, client_id):
    return (
        db.query(Complaint.category, func.count(Complaint.id))
        .filter(Complaint.client_id == client_id)
        .group_by(Complaint.category)
        .all()
    )


def sentiment_distribution(db, client_id):
    return (
        db.query(Complaint.sentiment, func.count(Complaint.id))
        .filter(Complaint.client_id == client_id)
        .group_by(Complaint.sentiment)
        .all()
    )


def urgency_distribution(db, client_id):
    return (
        db.query(Complaint.priority, func.count(Complaint.id))
        .filter(Complaint.client_id == client_id)
        .group_by(Complaint.priority)
        .all()
    )


def top_complaint_sources(db, client_id):
    return (
        db.query(Complaint.source, func.count(Complaint.id))
        .filter(Complaint.client_id == client_id)
        .group_by(Complaint.source)
        .all()
    )


def trend_detection(db, client_id, days=7):
    now = datetime.now(timezone.utc)
    current_start = now - timedelta(days=days)
    previous_start = now - timedelta(days=days * 2)
    current_count = db.query(func.count(Complaint.id)).filter(
        Complaint.client_id == client_id,
        Complaint.created_at >= current_start,
    ).scalar() or 0
    previous_count = db.query(func.count(Complaint.id)).filter(
        Complaint.client_id == client_id,
        Complaint.created_at >= previous_start,
        Complaint.created_at < current_start,
    ).scalar() or 0
    direction = "flat"
    if current_count > previous_count:
        direction = "up"
    elif current_count < previous_count:
        direction = "down"
    return {
        "window_days": days,
        "current": current_count,
        "previous": previous_count,
        "direction": direction,
    }


def category_breakdown_over_time(db, client_id, days=30):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    return (
        db.query(
            func.date(Complaint.created_at).label("day"),
            Complaint.category,
            func.count(Complaint.id),
        )
        .filter(Complaint.client_id == client_id, Complaint.created_at >= cutoff)
        .group_by(func.date(Complaint.created_at), Complaint.category)
        .order_by(func.date(Complaint.created_at))
        .all()
    )


def response_time_tracking(db, client_id):
    average = db.query(func.avg(Complaint.response_time_seconds)).filter(
        Complaint.client_id == client_id,
        Complaint.response_time_seconds.isnot(None),
    ).scalar()
    return {"average_response_time_seconds": float(average or 0.0)}


def customer_satisfaction_score(db, client_id):
    score = db.query(func.avg(Complaint.customer_satisfaction_score)).filter(
        Complaint.client_id == client_id,
        Complaint.customer_satisfaction_score.isnot(None),
    ).scalar()
    if score is None:
        resolved = db.query(func.count(Complaint.id)).filter(
            Complaint.client_id == client_id,
            Complaint.resolution_status == "resolved",
        ).scalar() or 0
        total = db.query(func.count(Complaint.id)).filter(Complaint.client_id == client_id).scalar() or 1
        score = resolved / total * 5
    return {"customer_satisfaction_score": round(float(score or 0.0), 2)}


def cache_metric(db, client_id, metric_key, metric_value, period_start=None, period_end=None):
    cached = (
        db.query(MaterializedAnalytics)
        .filter(
            MaterializedAnalytics.client_id == client_id,
            MaterializedAnalytics.metric_key == metric_key,
        )
        .order_by(MaterializedAnalytics.generated_at.desc())
        .first()
    )
    if cached:
        cached.metric_value = metric_value
        cached.period_start = period_start
        cached.period_end = period_end
    else:
        cached = MaterializedAnalytics(
            client_id=client_id,
            metric_key=metric_key,
            metric_value=metric_value,
            period_start=period_start,
            period_end=period_end,
        )
        db.add(cached)
    db.commit()
    return cached


def analytics_overview(db, client_id):
    overview = {
        "trend": trend_detection(db, client_id, days=7),
        "response_time": response_time_tracking(db, client_id),
        "csat": customer_satisfaction_score(db, client_id),
        "sources": top_complaint_sources(db, client_id),
    }
    cache_metric(db, client_id, "overview", overview)
    return overview


def analytics_customers(db, client_id):
    return (
        db.query(Complaint.customer_email, func.count(Complaint.id).label("count"))
        .filter(Complaint.client_id == client_id, Complaint.customer_email.isnot(None))
        .group_by(Complaint.customer_email)
        .order_by(func.count(Complaint.id).desc())
        .limit(10)
        .all()
    )
