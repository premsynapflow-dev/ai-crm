from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.db.models import Complaint


def get_team_performance(db: Session, client_id: str, period_days: int = 30) -> dict:
    """
    Aggregate complaint performance metrics by assigned agent/team owner.
    """
    start_date = datetime.now(timezone.utc) - timedelta(days=period_days)
    complaints = (
        db.query(Complaint)
        .filter(
            Complaint.client_id == client_id,
            Complaint.created_at >= start_date,
        )
        .all()
    )

    agent_metrics: dict[str, dict] = {}
    for complaint in complaints:
        agent = complaint.assigned_to or complaint.assigned_team or "Unassigned"

        if agent not in agent_metrics:
            agent_metrics[agent] = {
                "agent_name": agent,
                "total_tickets": 0,
                "resolved_tickets": 0,
                "response_times": [],
                "satisfaction_scores": [],
                "handle_times": [],
            }

        metrics = agent_metrics[agent]
        metrics["total_tickets"] += 1

        if complaint.resolution_status == "resolved":
            metrics["resolved_tickets"] += 1
            if complaint.resolved_at and complaint.created_at:
                handle_time = (complaint.resolved_at - complaint.created_at).total_seconds() / 3600
                metrics["handle_times"].append(handle_time)

        if complaint.first_response_at and complaint.created_at:
            response_time = (complaint.first_response_at - complaint.created_at).total_seconds() / 3600
            metrics["response_times"].append(response_time)

        satisfaction_score = complaint.satisfaction_score or complaint.customer_satisfaction_score
        if satisfaction_score:
            metrics["satisfaction_scores"].append(satisfaction_score)

    performance_data = []
    for _, metrics in agent_metrics.items():
        total_tickets = metrics["total_tickets"]
        resolved_tickets = metrics["resolved_tickets"]
        avg_response_time = (
            sum(metrics["response_times"]) / len(metrics["response_times"]) if metrics["response_times"] else 0.0
        )
        avg_handle_time = (
            sum(metrics["handle_times"]) / len(metrics["handle_times"]) if metrics["handle_times"] else 0.0
        )
        avg_satisfaction = (
            sum(metrics["satisfaction_scores"]) / len(metrics["satisfaction_scores"])
            if metrics["satisfaction_scores"]
            else 0.0
        )
        resolution_rate = (resolved_tickets / total_tickets) * 100 if total_tickets else 0.0

        performance_data.append(
            {
                "agent_name": metrics["agent_name"],
                "total_tickets": total_tickets,
                "resolved_tickets": resolved_tickets,
                "resolution_rate": round(resolution_rate, 1),
                "avg_response_time_hours": round(avg_response_time, 2),
                "avg_handle_time_hours": round(avg_handle_time, 2),
                "avg_satisfaction": round(avg_satisfaction, 2),
            }
        )

    performance_data.sort(key=lambda item: item["total_tickets"], reverse=True)
    total_tickets = sum([item["total_tickets"] for item in performance_data])
    total_resolved = sum([item["resolved_tickets"] for item in performance_data])

    return {
        "period_days": period_days,
        "team_performance": performance_data,
        "team_totals": {
            "total_tickets": total_tickets,
            "total_resolved": total_resolved,
            "avg_team_resolution_rate": round((total_resolved / total_tickets) * 100, 1) if total_tickets else 0.0,
        },
    }
