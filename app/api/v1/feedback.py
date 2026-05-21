from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.models import AgentCorrection, ChurnOutcome
from app.db.session import get_db
from app.dependencies.auth import require_api_key
from app.services.feedback_learning import record_agent_correction, record_churn_outcome

router = APIRouter(prefix="/api/v1/feedback", tags=["feedback-v1"])


class ChurnOutcomeRequest(BaseModel):
    customer_id: str
    outcome_type: str = Field(..., pattern="^(churned|retained|at_risk|recovered)$")
    reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    recorded_by: str | None = None


class AgentCorrectionRequest(BaseModel):
    correction_type: str
    corrected_value: dict[str, Any]
    original_value: dict[str, Any] | None = None
    complaint_id: str | None = None
    customer_id: str | None = None
    feedback_score: int | None = Field(default=None, ge=1, le=5)
    notes: str | None = None
    corrected_by: str | None = None


@router.post("/churn-outcomes")
def create_churn_outcome(payload: ChurnOutcomeRequest, db: Session = Depends(get_db), current_client=Depends(require_api_key)):
    try:
        outcome = record_churn_outcome(
            db,
            client_id=current_client.id,
            customer_id=uuid.UUID(payload.customer_id),
            outcome_type=payload.outcome_type,
            reason=payload.reason,
            recorded_by=payload.recorded_by,
            metadata=payload.metadata,
        )
        db.commit()
        db.refresh(outcome)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, "id": str(outcome.id), "risk_score_at_outcome": outcome.risk_score_at_outcome}


@router.post("/corrections")
def create_agent_correction(payload: AgentCorrectionRequest, db: Session = Depends(get_db), current_client=Depends(require_api_key)):
    correction = record_agent_correction(
        db,
        client_id=current_client.id,
        correction_type=payload.correction_type,
        corrected_value=payload.corrected_value,
        original_value=payload.original_value,
        complaint_id=uuid.UUID(payload.complaint_id) if payload.complaint_id else None,
        customer_id=uuid.UUID(payload.customer_id) if payload.customer_id else None,
        feedback_score=payload.feedback_score,
        notes=payload.notes,
        corrected_by=payload.corrected_by,
    )
    db.commit()
    db.refresh(correction)
    return {"success": True, "id": str(correction.id)}


@router.get("/summary")
def feedback_summary(db: Session = Depends(get_db), current_client=Depends(require_api_key)):
    outcomes = db.query(ChurnOutcome).filter(ChurnOutcome.client_id == current_client.id).all()
    corrections = db.query(AgentCorrection).filter(AgentCorrection.client_id == current_client.id).all()
    outcome_counts: dict[str, int] = {}
    for outcome in outcomes:
        outcome_counts[outcome.outcome_type] = outcome_counts.get(outcome.outcome_type, 0) + 1
    return {
        "outcome_counts": outcome_counts,
        "correction_count": len(corrections),
        "avg_feedback_score": round(
            sum(c.feedback_score for c in corrections if c.feedback_score is not None)
            / max(1, len([c for c in corrections if c.feedback_score is not None])),
            2,
        ),
    }
