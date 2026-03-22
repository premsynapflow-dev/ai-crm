from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.db.models import Complaint


def generate_root_cause_report(db: Session, client_id: str, period_days: int = 30) -> dict:
    """
    Generate a root cause analysis report for recent complaint trends.
    """
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=period_days)
    previous_start = start_date - timedelta(days=period_days)

    current_complaints = (
        db.query(Complaint)
        .filter(
            Complaint.client_id == client_id,
            Complaint.created_at >= start_date,
            Complaint.created_at <= end_date,
        )
        .all()
    )
    previous_complaints = (
        db.query(Complaint)
        .filter(
            Complaint.client_id == client_id,
            Complaint.created_at >= previous_start,
            Complaint.created_at < start_date,
        )
        .all()
    )

    current_categories = Counter([item.category for item in current_complaints if item.category])
    previous_categories = Counter([item.category for item in previous_complaints if item.category])

    category_trends = []
    current_total = len(current_complaints)
    for category, current_count in current_categories.most_common():
        previous_count = previous_categories.get(category, 0)
        if previous_count > 0:
            change_pct = ((current_count - previous_count) / previous_count) * 100
        elif current_count > 0:
            change_pct = 100.0
        else:
            change_pct = 0.0

        category_trends.append(
            {
                "category": category,
                "current_count": current_count,
                "previous_count": previous_count,
                "change_percentage": round(change_pct, 1),
                "percentage_of_total": round((current_count / current_total) * 100, 1) if current_total else 0.0,
            }
        )

    top_issues = category_trends[:5]
    trending_up = [item for item in category_trends if item["change_percentage"] > 10][:3]

    resolution_rates = {}
    for category in current_categories.keys():
        category_complaints = [item for item in current_complaints if item.category == category]
        resolved = len([item for item in category_complaints if item.resolution_status == "resolved"])
        resolution_rates[category] = round((resolved / len(category_complaints)) * 100, 1) if category_complaints else 0.0

    previous_total = len(previous_complaints)
    overall_change = (
        ((current_total - previous_total) / previous_total) * 100 if previous_total > 0 else 0.0
    )

    return {
        "period": f"Last {period_days} days",
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "total_complaints": current_total,
        "previous_period_total": previous_total,
        "overall_change_percentage": round(overall_change, 1),
        "top_issues": top_issues,
        "trending_up": trending_up,
        "resolution_rates": resolution_rates,
        "insights": generate_insights(current_complaints, category_trends),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_insights(complaints: list[Complaint], trends: list[dict]) -> list[str]:
    insights: list[str] = []

    for trend in trends[:3]:
        if trend["change_percentage"] > 20:
            insights.append(
                f"{trend['category']} complaints increased by {trend['change_percentage']}%. Investigate the root cause and prioritize fixes."
            )

    for trend in trends[:3]:
        if trend["percentage_of_total"] > 30:
            insights.append(
                f"{trend['category']} represents {trend['percentage_of_total']}% of all complaints. This is a major pain point."
            )

    if not insights:
        insights.append("No critical complaint spikes were detected in the selected period.")

    return insights
