from __future__ import annotations

from datetime import datetime, timedelta, timezone
from statistics import median

from sqlalchemy.orm import Session

from app.db.models import Complaint
from app.intelligence.constants import TEAM_PERF_MIN_SAMPLE, TEAM_PERF_LOW_CONF_N


def _percentile_75(values: list[float]) -> float | None:
    if not values:
        return None
    sorted_vals = sorted(values)
    idx = max(0, int(len(sorted_vals) * 0.75) - 1)
    return round(sorted_vals[idx], 2)


def get_team_performance(db: Session, client_id: str, period_days: int = 30) -> dict:
    """
    Aggregate complaint performance metrics by assigned agent/team owner.

    Statistical notes:
    - `n` (sample size) is always returned — averages based on <5 tickets are flagged
      as low_confidence.
    - Response time and handle time use median (more robust than mean for skewed
      distributions typical of support queues) plus p75 for outlier visibility.
    - response_time_n counts only tickets where first_response_at is set; this is
      documented in response_time_note so callers know the denominator.
    - Handle time counts only resolved tickets (not abandoned/open).
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

        m = agent_metrics[agent]
        m["total_tickets"] += 1

        if complaint.resolution_status == "resolved":
            m["resolved_tickets"] += 1
            if complaint.resolved_at and complaint.created_at:
                handle_time = (complaint.resolved_at - complaint.created_at).total_seconds() / 3600
                m["handle_times"].append(handle_time)

        if complaint.first_response_at and complaint.created_at:
            response_time = (complaint.first_response_at - complaint.created_at).total_seconds() / 3600
            m["response_times"].append(response_time)

        satisfaction_score = complaint.satisfaction_score or complaint.customer_satisfaction_score
        if satisfaction_score:
            m["satisfaction_scores"].append(float(satisfaction_score))

    performance_data = []
    for _, m in agent_metrics.items():
        n = m["total_tickets"]
        resolved = m["resolved_tickets"]
        has_enough_data = n >= TEAM_PERF_MIN_SAMPLE
        low_conf = n < TEAM_PERF_LOW_CONF_N

        rt = m["response_times"]
        ht = m["handle_times"]
        ss = m["satisfaction_scores"]

        performance_data.append({
            "agent_name": m["agent_name"],
            "total_tickets": n,
            "resolved_tickets": resolved,
            "resolution_rate": round((resolved / n) * 100, 1) if n else 0.0,
            # Response time
            "response_time_n": len(rt),
            "median_response_time_hours": round(median(rt), 2) if rt else None,
            "p75_response_time_hours": _percentile_75(rt),
            "avg_response_time_hours": round(sum(rt) / len(rt), 2) if rt else None,
            "response_time_note": "Based on tickets with first_response_at set",
            # Handle time (resolved only)
            "handle_time_n": len(ht),
            "median_handle_time_hours": round(median(ht), 2) if ht else None,
            "p75_handle_time_hours": _percentile_75(ht),
            "avg_handle_time_hours": round(sum(ht) / len(ht), 2) if ht else None,
            "handle_time_note": "Based on resolved tickets only",
            # Satisfaction
            "satisfaction_n": len(ss),
            "avg_satisfaction": round(sum(ss) / len(ss), 2) if ss else None,
            # Confidence
            "low_confidence": low_conf,
            "low_confidence_reason": f"Only {n} tickets (threshold: {TEAM_PERF_LOW_CONF_N})" if low_conf else None,
            # Suppress averages when sample too small
            "metrics_suppressed": not has_enough_data,
        })

        # Zero out numeric averages when sample is below minimum to prevent false precision
        if not has_enough_data:
            for key in ("median_response_time_hours", "p75_response_time_hours", "avg_response_time_hours",
                        "median_handle_time_hours", "p75_handle_time_hours", "avg_handle_time_hours",
                        "avg_satisfaction"):
                performance_data[-1][key] = None

    performance_data.sort(key=lambda x: x["total_tickets"], reverse=True)
    total_tickets = sum(x["total_tickets"] for x in performance_data)
    total_resolved = sum(x["resolved_tickets"] for x in performance_data)

    return {
        "period_days": period_days,
        "team_performance": performance_data,
        "team_totals": {
            "total_tickets": total_tickets,
            "total_resolved": total_resolved,
            "avg_team_resolution_rate": round((total_resolved / total_tickets) * 100, 1) if total_tickets else 0.0,
        },
    }
