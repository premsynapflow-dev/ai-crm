"""Churn probability calibration.

Converts a behavioral risk score (0–100) into a calibrated churn probability (0–1)
using conservative band mapping with linear interpolation within each band.

WHY NOT score/100:
  The risk score is an additive weighted index, not a probability.
  A score of 80 does NOT mean 80% chance of churn — it means the customer exhibits
  many high-risk behavioral signals.  Treating it as a probability would produce
  wildly overconfident predictions (e.g., 80% sounds certain; calibrated truth
  may be 45–55% for a typical dataset).

WHY BAND MAPPING:
  Without historical churn outcome data to train a logistic regression, we cannot
  directly estimate probabilities.  Band mapping provides conservative, defensible
  estimates that understate rather than overstate risk.  The bands should be recalibrated
  once actual churn outcomes are accumulated in the churn_outcomes table.
"""
from __future__ import annotations

from app.intelligence.constants import CHURN_PROB_BANDS


def calibrate_churn_probability(risk_score: float) -> float:
    """Map a 0–100 behavioral risk score to a calibrated churn probability (0–1).

    Uses linear interpolation within each band defined in CHURN_PROB_BANDS.
    Never returns a value above 0.70 — probabilities above that require a
    validated ML model trained on actual churn outcomes.

    Args:
        risk_score: Customer risk score in [0, 100].

    Returns:
        Calibrated probability in [0.0, 0.70].
    """
    score = max(0.0, min(100.0, float(risk_score)))

    for low_s, high_s, low_p, high_p in CHURN_PROB_BANDS:
        if low_s <= score <= high_s:
            # Linear interpolation within band
            band_width = high_s - low_s
            if band_width == 0:
                return round(low_p, 4)
            position = (score - low_s) / band_width
            prob = low_p + position * (high_p - low_p)
            return round(prob, 4)

    # Edge case: exactly 100
    return 0.70


def calibrate_churn_probability_batch(scores: list[float]) -> list[float]:
    """Vectorised version for bulk calibration."""
    return [calibrate_churn_probability(s) for s in scores]


def probability_to_label(prob: float) -> str:
    """Convert a churn probability to a human-readable risk label."""
    if prob >= 0.45:
        return "high"
    if prob >= 0.12:
        return "medium"
    return "low"
