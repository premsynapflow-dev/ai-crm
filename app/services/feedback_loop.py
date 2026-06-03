"""Autonomous feedback loop — Layer 9.

Recalibrates churn_risk scoring weights based on measured workflow outcomes.

Default weights:
  unresolved_complaints: 0.35   — fraction of complaints still open
  escalation_count: 0.25        — number of escalations per period
  sentiment_score: 0.20         — average sentiment (inverted: lower = higher risk)
  response_time: 0.20           — avg response time vs SLA

After each calibration cycle:
  - If intervention resolved complaint AND churn_score dropped → reinforce resolution weight
  - If intervention did NOT resolve → penalize action type weight (stored per rule)
  - Weights clipped to [0.05, 0.60] to prevent collapse

Calibration runs weekly (triggered by worker). Weights stored in outcome_weights table.
Customer churn_risk_score is updated by the existing CustomerProfileService;
this service adjusts the weight config that feeds that scoring.
"""
from __future__ import annotations

from datetime import datetime, timezone
from statistics import mean
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Client, OutcomeWeight, WorkflowOutcome
from app.utils.logging import get_logger

logger = get_logger(__name__)

_DEFAULT_WEIGHTS: dict[str, float] = {
    "unresolved_complaints": 0.35,
    "escalation_count": 0.25,
    "sentiment_score": 0.20,
    "response_time": 0.20,
}
_MIN_WEIGHT = 0.05
_MAX_WEIGHT = 0.60
_LEARNING_RATE = 0.05
_MIN_SAMPLES = 10  # Need at least this many outcomes to recalibrate


def get_weights(db: Session, client_id: str) -> dict[str, float]:
    """Return current calibration weights for a client, falling back to defaults."""
    record = (
        db.query(OutcomeWeight)
        .filter(OutcomeWeight.client_id == client_id)
        .first()
    )
    if not record or not record.weights:
        return dict(_DEFAULT_WEIGHTS)
    # Merge with defaults to handle new weight keys
    w = dict(_DEFAULT_WEIGHTS)
    w.update({k: float(v) for k, v in record.weights.items()})
    return w


def _normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    """Ensure weights sum to 1.0 and are within bounds."""
    total = sum(weights.values())
    if total == 0:
        return dict(_DEFAULT_WEIGHTS)
    normalized = {k: max(_MIN_WEIGHT, min(_MAX_WEIGHT, v / total)) for k, v in weights.items()}
    # Re-normalize after clipping
    total2 = sum(normalized.values())
    return {k: round(v / total2, 4) for k, v in normalized.items()}


def recalibrate(db: Session, client_id: str) -> dict[str, Any]:
    """
    Recalibrate churn_risk weights using recent workflow outcomes.
    Returns {weights_updated, samples_used, new_weights}.
    """
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    outcomes = (
        db.query(WorkflowOutcome)
        .filter(
            WorkflowOutcome.client_id == client_id,
            WorkflowOutcome.measured_at.isnot(None),
            WorkflowOutcome.measured_at >= cutoff,
        )
        .all()
    )

    if len(outcomes) < _MIN_SAMPLES:
        return {
            "weights_updated": False,
            "samples_used": len(outcomes),
            "reason": f"Insufficient data ({len(outcomes)} < {_MIN_SAMPLES} samples required)",
        }

    current = get_weights(db, client_id)
    new_weights = dict(current)

    # Signal 1: Resolution effectiveness
    resolved_outcomes = [o for o in outcomes if o.resolved is not None]
    if resolved_outcomes:
        resolution_rate = sum(1 for o in resolved_outcomes if o.resolved) / len(resolved_outcomes)
        # If resolution rate is high, the unresolved_complaints weight was too aggressive → lower it
        # If resolution rate is low, the model is under-weighting unresolved complaints → raise it
        delta = _LEARNING_RATE * (0.5 - resolution_rate)
        new_weights["unresolved_complaints"] = current["unresolved_complaints"] + delta

    # Signal 2: Escalation prevention
    esc_outcomes = [o for o in outcomes if o.escalation_prevented is not None]
    if esc_outcomes:
        prevention_rate = sum(1 for o in esc_outcomes if o.escalation_prevented) / len(esc_outcomes)
        delta = _LEARNING_RATE * (0.5 - prevention_rate)
        new_weights["escalation_count"] = current["escalation_count"] + delta

    # Signal 3: Churn score accuracy
    churn_outcomes = [o for o in outcomes if o.customer_churned is not None and o.churn_score_after is not None]
    if churn_outcomes:
        # If high churn_score → customer actually churned → model was right → no change
        # If high churn_score → customer stayed → model was too aggressive on sentiment
        false_positives = [
            o for o in churn_outcomes
            if not o.customer_churned and (o.churn_score_after or 0) >= 70
        ]
        fp_rate = len(false_positives) / len(churn_outcomes)
        if fp_rate > 0.4:
            # Sentiment weight is over-contributing — reduce it slightly
            new_weights["sentiment_score"] = current["sentiment_score"] - _LEARNING_RATE * fp_rate

    # Signal 4: SLA / response time
    sla_outcomes = [o for o in outcomes if o.sla_met is not None]
    if sla_outcomes:
        sla_rate = sum(1 for o in sla_outcomes if o.sla_met) / len(sla_outcomes)
        delta = _LEARNING_RATE * (0.5 - sla_rate)
        new_weights["response_time"] = current["response_time"] + delta

    new_weights = _normalize_weights(new_weights)

    # Persist
    record = (
        db.query(OutcomeWeight)
        .filter(OutcomeWeight.client_id == client_id)
        .first()
    )
    now = datetime.now(timezone.utc)
    if record:
        record.weights = new_weights
        record.calibration_count += 1
        record.last_calibrated_at = now
        record.updated_at = now
    else:
        record = OutcomeWeight(
            client_id=client_id,
            weights=new_weights,
            calibration_count=1,
            last_calibrated_at=now,
        )
        db.add(record)

    db.commit()

    logger.info(
        "Feedback loop recalibrated client=%s samples=%s weights=%s",
        client_id, len(outcomes), new_weights,
    )

    return {
        "weights_updated": True,
        "samples_used": len(outcomes),
        "new_weights": new_weights,
        "previous_weights": current,
    }


def run_feedback_loop_for_all(db: Session) -> dict[str, Any]:
    """Run recalibration for every client that has outcome data. Called weekly by worker."""
    clients = db.query(Client).all()
    results = {"calibrated": 0, "skipped": 0, "total_clients": len(clients)}
    for client in clients:
        try:
            r = recalibrate(db, str(client.id))
            if r.get("weights_updated"):
                results["calibrated"] += 1
            else:
                results["skipped"] += 1
        except Exception as exc:
            if "does not exist" not in str(exc).lower():
                logger.warning("Feedback loop failed for client=%s: %s", client.id, exc)
            results["skipped"] += 1
    return results
