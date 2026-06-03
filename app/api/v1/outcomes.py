"""Workflow Outcomes Dashboard API — Layer 9: autonomous ops effectiveness."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.models import Client, WorkflowOutcome
from app.db.session import get_db
from app.dependencies.auth import require_api_key
from app.services.feedback_loop import get_weights, recalibrate
from app.services.outcome_tracker import get_outcomes_summary
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/outcomes")
def outcomes_dashboard(
    days: int = Query(30, ge=1, le=90),
    db: Session = Depends(get_db),
    current_client: Client = Depends(require_api_key),
):
    """
    Workflow effectiveness dashboard.

    Returns:
      - resolution_rate: % of complaints resolved after workflow ran
      - sla_compliance_rate: % where SLA was met
      - escalation_prevention_rate: % where escalation level stayed at 0
      - churn_prevention_rate: % of at-risk customers who didn't churn
      - current_weights: churn-risk scoring weights from the feedback loop
    """
    client_id = str(current_client.id)

    summary = get_outcomes_summary(db, client_id, days=days)
    weights = get_weights(db, client_id)

    # Per-action-type breakdown
    from datetime import datetime, timedelta, timezone
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    from app.db.models import WorkflowExecution
    outcomes_with_exec = (
        db.query(WorkflowOutcome, WorkflowExecution)
        .join(WorkflowExecution, WorkflowExecution.id == WorkflowOutcome.execution_id)
        .filter(
            WorkflowOutcome.client_id == client_id,
            WorkflowOutcome.measured_at.isnot(None),
            WorkflowOutcome.created_at >= cutoff,
        )
        .all()
    )

    action_stats: dict[str, dict] = {}
    for outcome, execution in outcomes_with_exec:
        action = execution.action_type or "unknown"
        if action not in action_stats:
            action_stats[action] = {"total": 0, "resolved": 0, "sla_met": 0}
        action_stats[action]["total"] += 1
        if outcome.resolved:
            action_stats[action]["resolved"] += 1
        if outcome.sla_met:
            action_stats[action]["sla_met"] += 1

    per_action = [
        {
            "action_type": action,
            "total": stats["total"],
            "resolution_rate": round(stats["resolved"] / stats["total"] * 100, 1) if stats["total"] else 0,
            "sla_compliance_rate": round(stats["sla_met"] / stats["total"] * 100, 1) if stats["total"] else 0,
        }
        for action, stats in action_stats.items()
    ]
    per_action.sort(key=lambda x: x["total"], reverse=True)

    return {
        "client_id": client_id,
        "period_days": days,
        "summary": summary,
        "current_churn_weights": weights,
        "per_action_type": per_action,
    }


@router.post("/outcomes/recalibrate")
def trigger_recalibration(
    db: Session = Depends(get_db),
    current_client: Client = Depends(require_api_key),
):
    """Manually trigger the feedback loop weight recalibration for this client."""
    result = recalibrate(db, str(current_client.id))
    return result
