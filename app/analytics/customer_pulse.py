from datetime import datetime, timedelta, timezone

from sqlalchemy import func

from app.db.models import Client, Complaint, EventLog, MaterializedAnalytics
from app.integrations.slack import send_slack_alert
from app.services.event_logger import log_event


def detect_complaint_spikes(db, client_id, send_alert=True, min_count=10):
    now = datetime.now(timezone.utc)
    current_start = now - timedelta(hours=24)
    previous_start = now - timedelta(hours=48)

    current_rows = (
        db.query(Complaint.category, func.count(Complaint.id))
        .filter(
            Complaint.client_id == client_id,
            Complaint.created_at >= current_start,
        )
        .group_by(Complaint.category)
        .all()
    )
    previous_rows = (
        db.query(Complaint.category, func.count(Complaint.id))
        .filter(
            Complaint.client_id == client_id,
            Complaint.created_at >= previous_start,
            Complaint.created_at < current_start,
        )
        .group_by(Complaint.category)
        .all()
    )
    previous_map = {category: count for category, count in previous_rows}
    spikes = []

    for category, count in current_rows:
        previous_count = previous_map.get(category, 0)
        threshold = max(min_count, (previous_count * 2) if previous_count else min_count)
        if count < threshold:
            continue

        spike = {
            "category": category or "unknown",
            "current_count": count,
            "previous_count": previous_count,
        }
        spikes.append(spike)

        if not send_alert:
            continue

        recent_alerts = (
            db.query(EventLog)
            .filter(
                EventLog.client_id == client_id,
                EventLog.event_type == "complaint_spike_alert",
                EventLog.created_at >= now - timedelta(hours=6),
            )
            .all()
        )
        duplicate = any((item.payload or {}).get("category") == spike["category"] for item in recent_alerts)
        if duplicate:
            continue

        client = db.query(Client).filter(Client.id == client_id).first()
        if client:
            try:
                send_slack_alert(
                    (
                        "*Complaint Spike Detected*\n"
                        f"Category: {spike['category']}\n"
                        f"Current 24h: {spike['current_count']}\n"
                        f"Previous 24h: {spike['previous_count']}"
                    ),
                    webhook_url=client.slack_webhook_url,
                )
            except Exception:
                pass

        log_event(
            db,
            client_id,
            "complaint_spike_alert",
            spike,
        )

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
