from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db.models import AgentCorrection, ChurnOutcome, Customer
from app.services.customer_profile import CustomerProfileService
from app.services.event_logger import log_event


def record_churn_outcome(
    db: Session,
    *,
    client_id,
    customer_id,
    outcome_type: str,
    reason: str | None = None,
    recorded_by: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> ChurnOutcome:
    customer = db.query(Customer).filter(Customer.id == customer_id, Customer.client_id == client_id).first()
    if customer is None:
        raise ValueError("Customer not found")
    risk = CustomerProfileService(db).compute_churn_risk(customer)
    existing = (
        db.query(ChurnOutcome)
        .filter(
            ChurnOutcome.client_id == client_id,
            ChurnOutcome.customer_id == customer_id,
            ChurnOutcome.outcome_type == outcome_type,
        )
        .first()
    )
    outcome = existing or ChurnOutcome(client_id=client_id, customer_id=customer_id, outcome_type=outcome_type)
    if existing is None:
        db.add(outcome)
    outcome.reason = reason
    outcome.recorded_by = recorded_by
    outcome.risk_score_at_outcome = float(risk.get("score") or 0)
    outcome.metadata_json = metadata or {}
    log_event(
        db,
        client_id,
        "churn_outcome_recorded",
        {
            "customer_id": str(customer_id),
            "outcome_type": outcome_type,
            "risk_score": outcome.risk_score_at_outcome,
            "reason": reason,
        },
        customer_id=customer_id,
        source="feedback",
        actor_type="agent",
        risk_delta=outcome.risk_score_at_outcome,
    )
    db.flush()
    return outcome


def record_agent_correction(
    db: Session,
    *,
    client_id,
    correction_type: str,
    corrected_value: dict[str, Any],
    complaint_id=None,
    customer_id=None,
    original_value: dict[str, Any] | None = None,
    feedback_score: int | None = None,
    notes: str | None = None,
    corrected_by: str | None = None,
) -> AgentCorrection:
    correction = AgentCorrection(
        client_id=client_id,
        complaint_id=complaint_id,
        customer_id=customer_id,
        correction_type=correction_type,
        original_value=original_value,
        corrected_value=corrected_value,
        feedback_score=feedback_score,
        notes=notes,
        corrected_by=corrected_by,
    )
    db.add(correction)
    log_event(
        db,
        client_id,
        "agent_correction_recorded",
        {
            "correction_type": correction_type,
            "complaint_id": str(complaint_id) if complaint_id else None,
            "customer_id": str(customer_id) if customer_id else None,
            "feedback_score": feedback_score,
        },
        customer_id=customer_id,
        complaint_id=complaint_id,
        source="feedback",
        actor_type="agent",
    )
    db.flush()
    return correction
