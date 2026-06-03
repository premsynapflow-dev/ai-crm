"""Workflow outcome tracker — Layer 9 completion.

Measures post-execution outcomes at T+48h for every workflow execution:
  - resolved: was the complaint resolved?
  - sla_met: was SLA on_track at resolution?
  - escalation_prevented: did escalation_level stay at 0?
  - customer_churned: did a churn CustomerEvent appear within 30 days?
  - churn_score_before / after: change in churn risk score

Usage:
  1. When a workflow execution succeeds, call schedule_outcome_measurement() to
     set measure_outcome_at = now() + 48h on the WorkflowExecution.
  2. The background worker calls process_pending_outcomes() every 30 minutes.
  3. process_pending_outcomes() measures and stores WorkflowOutcome records.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from statistics import mean
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import (
    Complaint,
    Customer,
    CustomerEvent,
    WorkflowExecution,
    WorkflowOutcome,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)

_OUTCOME_DELAY_HOURS = 48
_CHURN_LOOKBACK_DAYS = 30


def schedule_outcome_measurement(
    db: Session,
    execution: WorkflowExecution,
    commit: bool = False,
) -> None:
    """Set measure_outcome_at on a workflow execution so the worker picks it up later."""
    execution.measure_outcome_at = datetime.now(timezone.utc) + timedelta(hours=_OUTCOME_DELAY_HOURS)
    if commit:
        db.commit()
    else:
        db.flush()


def _safe_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _measure_one(db: Session, execution: WorkflowExecution) -> WorkflowOutcome | None:
    """Measure outcomes for a single workflow execution. Returns None if already measured."""
    existing = (
        db.query(WorkflowOutcome)
        .filter(WorkflowOutcome.execution_id == execution.id)
        .first()
    )
    if existing:
        return None  # already measured

    now = datetime.now(timezone.utc)

    complaint: Complaint | None = None
    customer: Customer | None = None
    if execution.complaint_id:
        complaint = db.query(Complaint).filter(Complaint.id == execution.complaint_id).first()
    if complaint and complaint.customer_id:
        customer = db.query(Customer).filter(Customer.id == complaint.customer_id).first()

    # Resolution
    resolved = None
    sla_met = None
    escalation_prevented = None
    resolution_time_hours = None
    if complaint:
        resolved = complaint.resolution_status == "resolved" or complaint.status == "RESOLVED"
        sla_met = complaint.sla_status in ("on_track", "resolved") if resolved else None
        escalation_prevented = (complaint.escalation_level or 0) == 0
        if resolved and complaint.resolved_at and complaint.created_at:
            created = _safe_utc(complaint.created_at)
            resolved_at = _safe_utc(complaint.resolved_at)
            if created and resolved_at:
                resolution_time_hours = round((resolved_at - created).total_seconds() / 3600, 2)

    # Churn signal
    churn_score_before: float | None = None
    churn_score_after: float | None = None
    customer_churned: bool | None = None
    if customer:
        churn_score_after = customer.churn_risk_score
        # Look for a churn event in the 30 days after the execution
        exec_time = _safe_utc(execution.executed_at) or now
        churn_event = (
            db.query(CustomerEvent)
            .filter(
                CustomerEvent.customer_id == customer.id,
                CustomerEvent.event_type.in_(["churn", "customer_churned", "subscription_cancelled"]),
                CustomerEvent.event_timestamp >= exec_time,
                CustomerEvent.event_timestamp <= exec_time + timedelta(days=_CHURN_LOOKBACK_DAYS),
            )
            .first()
        )
        customer_churned = churn_event is not None

    outcome = WorkflowOutcome(
        client_id=execution.client_id,
        execution_id=execution.id,
        complaint_id=execution.complaint_id,
        customer_id=customer.id if customer else execution.customer_id,
        resolved=resolved,
        sla_met=sla_met,
        escalation_prevented=escalation_prevented,
        customer_churned=customer_churned,
        churn_score_before=churn_score_before,
        churn_score_after=churn_score_after,
        resolution_time_hours=resolution_time_hours,
        measure_at=_safe_utc(execution.measure_outcome_at),
        measured_at=now,
    )
    db.add(outcome)
    return outcome


def process_pending_outcomes(db: Session, batch_size: int = 50) -> int:
    """
    Find workflow executions whose measure_outcome_at has passed and measure their outcomes.
    Returns count of outcomes recorded.
    """
    now = datetime.now(timezone.utc)
    executions = (
        db.query(WorkflowExecution)
        .filter(
            WorkflowExecution.measure_outcome_at.isnot(None),
            WorkflowExecution.measure_outcome_at <= now,
            WorkflowExecution.execution_status == "succeeded",
        )
        .limit(batch_size)
        .all()
    )

    recorded = 0
    for execution in executions:
        try:
            outcome = _measure_one(db, execution)
            if outcome:
                recorded += 1
            # Clear measure_outcome_at so we don't re-process
            execution.measure_outcome_at = None
        except Exception as exc:
            logger.warning("Outcome measurement failed for execution=%s: %s", execution.id, exc)

    if recorded:
        db.commit()

    return recorded


def get_outcomes_summary(db: Session, client_id: str, days: int = 30) -> dict[str, Any]:
    """
    Aggregate outcome metrics for the dashboard.
    Returns resolution_rate, sla_compliance_rate, escalation_prevention_rate, churn_prevention_rate.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    outcomes = (
        db.query(WorkflowOutcome)
        .filter(
            WorkflowOutcome.client_id == client_id,
            WorkflowOutcome.created_at >= cutoff,
            WorkflowOutcome.measured_at.isnot(None),
        )
        .all()
    )

    if not outcomes:
        return {
            "total_measured": 0,
            "resolution_rate": None,
            "sla_compliance_rate": None,
            "escalation_prevention_rate": None,
            "churn_prevention_rate": None,
            "avg_resolution_hours": None,
        }

    resolved = [o for o in outcomes if o.resolved is not None]
    sla_applicable = [o for o in outcomes if o.sla_met is not None]
    escalation_applicable = [o for o in outcomes if o.escalation_prevented is not None]
    churn_applicable = [o for o in outcomes if o.customer_churned is not None]

    return {
        "total_measured": len(outcomes),
        "resolution_rate": round(
            sum(1 for o in resolved if o.resolved) / len(resolved) * 100, 1
        ) if resolved else None,
        "sla_compliance_rate": round(
            sum(1 for o in sla_applicable if o.sla_met) / len(sla_applicable) * 100, 1
        ) if sla_applicable else None,
        "escalation_prevention_rate": round(
            sum(1 for o in escalation_applicable if o.escalation_prevented) / len(escalation_applicable) * 100, 1
        ) if escalation_applicable else None,
        "churn_prevention_rate": round(
            sum(1 for o in churn_applicable if not o.customer_churned) / len(churn_applicable) * 100, 1
        ) if churn_applicable else None,
        "avg_resolution_hours": round(
            mean(o.resolution_time_hours for o in outcomes if o.resolution_time_hours is not None), 1
        ) if any(o.resolution_time_hours for o in outcomes) else None,
    }
