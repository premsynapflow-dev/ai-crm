from datetime import datetime, timedelta, timezone
from statistics import mean, stdev

from sqlalchemy import func

from app.db.models import Client, Complaint, EventLog, MaterializedAnalytics
from app.integrations.slack import send_slack_alert
from app.intelligence.constants import (
    SPIKE_ZSCORE_HIGH, SPIKE_ZSCORE_MEDIUM, SPIKE_MIN_COUNT, SPIKE_ROLLING_WINDOW_DAYS,
    SENTIMENT_STRONG_NEG,
)
from app.services.event_logger import log_event


def detect_complaint_spikes(
    db,
    client_id,
    send_alert: bool = True,
) -> list[dict]:
    """Z-score based spike detection against a rolling 7-day hourly baseline.

    Uses statistical significance rather than arbitrary multipliers.
    A spike is flagged when the current hour's count is more than SPIKE_ZSCORE_MEDIUM
    standard deviations above the rolling mean.  Low-volume clients are protected
    by SPIKE_MIN_COUNT — no spike fires for trivially small counts.
    """
    now = datetime.now(timezone.utc)
    last_hour_start = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    window_start = now - timedelta(days=SPIKE_ROLLING_WINDOW_DAYS)

    # Current hour count
    hour_count = (
        db.query(func.count(Complaint.id))
        .filter(
            Complaint.client_id == client_id,
            Complaint.created_at >= last_hour_start,
        )
        .scalar()
        or 0
    )

    # Current hour sentiment
    avg_sentiment = float(
        db.query(func.avg(Complaint.sentiment))
        .filter(
            Complaint.client_id == client_id,
            Complaint.created_at >= last_hour_start,
        )
        .scalar()
        or 0.0
    )

    # Build rolling baseline: hourly counts over last SPIKE_ROLLING_WINDOW_DAYS
    from sqlalchemy import text
    hourly_rows = (
        db.query(
            func.date_trunc("hour", Complaint.created_at).label("hr"),
            func.count(Complaint.id).label("cnt"),
        )
        .filter(
            Complaint.client_id == client_id,
            Complaint.created_at >= window_start,
            Complaint.created_at < last_hour_start,
        )
        .group_by(text("hr"))
        .all()
    )
    baseline_counts = [float(row.cnt) for row in hourly_rows]

    spikes = []

    # Volume spike detection
    if baseline_counts and hour_count >= SPIKE_MIN_COUNT:
        rolling_mean = mean(baseline_counts)
        rolling_std = stdev(baseline_counts) if len(baseline_counts) > 1 else 0.5
        rolling_std = max(rolling_std, 0.5)  # floor to avoid div/zero
        z_score = (hour_count - rolling_mean) / rolling_std

        if z_score > SPIKE_ZSCORE_MEDIUM:
            spikes.append({
                "type": "volume_spike",
                "hour_count": hour_count,
                "rolling_mean": round(rolling_mean, 1),
                "z_score": round(z_score, 2),
                "severity": "high" if z_score > SPIKE_ZSCORE_HIGH else "medium",
                "detection_method": "z_score",
            })

    # Sentiment drop detection (separate signal, uses canonical threshold)
    if hour_count >= SPIKE_MIN_COUNT and avg_sentiment < SENTIMENT_STRONG_NEG:
        spikes.append({
            "type": "sentiment_drop",
            "avg_sentiment": round(avg_sentiment, 3),
            "severity": "high" if avg_sentiment < -0.65 else "medium",
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
