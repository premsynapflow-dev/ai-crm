from datetime import datetime, timedelta, timezone

from sqlalchemy import func

from app.db.models import Client, Complaint, EventLog, MaterializedAnalytics
from app.integrations.slack import send_slack_alert
from app.services.event_logger import log_event


def detect_complaint_spikes(
    db, 
    client_id, 
    send_alert: bool = True
) -> list[dict]:
    """Optimized spike detection with single query"""
    now = datetime.now(timezone.utc)
    last_hour = now - timedelta(hours=1)
    last_24h = now - timedelta(hours=24)

    # Single query with aggregation
    stats = db.query(
        func.count(Complaint.id).filter(
            Complaint.created_at >= last_hour
        ).label('hour_count'),
        func.count(Complaint.id).filter(
            Complaint.created_at >= last_24h
        ).label('day_count'),
        func.avg(Complaint.sentiment).filter(
            Complaint.created_at >= last_hour
        ).label('avg_sentiment'),
    ).filter(
        Complaint.client_id == client_id
    ).first()

    hour_count = stats.hour_count or 0
    day_count = stats.day_count or 0
    avg_sentiment = stats.avg_sentiment or 0.0

    expected_hourly = (day_count / 24) * 1.5

    spikes = []
    if hour_count > expected_hourly and hour_count > 10:
        spikes.append({
            "type": "volume_spike",
            "hour_count": hour_count,
            "expected": expected_hourly,
            "severity": "high" if hour_count > expected_hourly * 2 else "medium"
        })

    if avg_sentiment < -0.5 and hour_count > 5:
        spikes.append({
            "type": "sentiment_drop",
            "avg_sentiment": avg_sentiment,
            "severity": "high" if avg_sentiment < -0.7 else "medium"
        })

    return spikes


def _cached_pulse(db, client_id):
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    cached = (
        db.query(MaterializedAnalytics)
        .filter(
            MaterializedAnalytics.client_id == client_id,
            MaterializedAnalytics.metric_key == "customer_pulse",
            MaterializedAnalytics.generated_at >= today_start,
        )
        .order_by(MaterializedAnalytics.generated_at.desc())
        .first()
    )
    return cached


def generate_customer_pulse(db, client_id):
    cached = _cached_pulse(db, client_id)
    if cached:
        return cached.metric_value

    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)
    fourteen_days_ago = now - timedelta(days=14)

    issues = (
        db.query(Complaint.category, func.count(Complaint.id).label("count"))
        .filter(
            Complaint.client_id == client_id,
            Complaint.created_at >= seven_days_ago,
        )
        .group_by(Complaint.category)
        .order_by(func.count(Complaint.id).desc())
        .limit(5)
        .all()
    )

    current_sentiment = db.query(func.avg(Complaint.sentiment)).filter(
        Complaint.client_id == client_id,
        Complaint.created_at >= seven_days_ago,
    ).scalar()
    previous_sentiment = db.query(func.avg(Complaint.sentiment)).filter(
        Complaint.client_id == client_id,
        Complaint.created_at >= fourteen_days_ago,
        Complaint.created_at < seven_days_ago,
    ).scalar()

    current_value = float(current_sentiment or 0.0)
    previous_value = float(previous_sentiment or 0.0)
    if current_value > previous_value:
        direction = "improving"
    elif current_value < previous_value:
        direction = "worsening"
    else:
        direction = "stable"

    angry_customers = (
        db.query(
            Complaint.customer_email,
            func.count(Complaint.id).label("complaint_count"),
            func.avg(Complaint.sentiment).label("avg_sentiment"),
        )
        .filter(
            Complaint.client_id == client_id,
            Complaint.customer_email.isnot(None),
        )
        .group_by(Complaint.customer_email)
        .having(func.avg(Complaint.sentiment) < -0.25)
        .order_by(func.avg(Complaint.sentiment).asc(), func.count(Complaint.id).desc())
        .limit(5)
        .all()
    )

    spikes = detect_complaint_spikes(db, client_id, send_alert=False)
    top_issues = [
        {"category": category or "unknown", "count": count}
        for category, count in issues
    ]
    churn_risk_customers = [
        {
            "customer_email": email,
            "complaint_count": count,
            "avg_sentiment": round(float(avg_sentiment or 0.0), 2),
        }
        for email, count, avg_sentiment in angry_customers
    ]
    suggested_actions = []
    if top_issues:
        suggested_actions.append(
            f"Focus on {top_issues[0]['category']} complaints first; it is your top issue right now."
        )
    if spikes:
        suggested_actions.append(
            f"Investigate spike in {spikes[0]['category']} complaints before it spreads further."
        )
    if direction == "worsening":
        suggested_actions.append("Review AI replies and escalation rules to improve customer sentiment.")
    if not suggested_actions:
        suggested_actions.append("Maintain current response quality and keep monitoring daily complaint trends.")

    pulse = {
        "top_issues": top_issues,
        "sentiment_trend": {
            "current_avg": round(current_value, 2),
            "previous_avg": round(previous_value, 2),
            "direction": direction,
        },
        "churn_risk_customers": churn_risk_customers,
        "new_complaint_spikes": spikes,
        "suggested_actions": suggested_actions,
    }

    cached = MaterializedAnalytics(
        client_id=client_id,
        metric_key="customer_pulse",
        metric_value=pulse,
        period_start=seven_days_ago,
        period_end=now,
    )
    db.add(cached)
    db.commit()
    return pulse
