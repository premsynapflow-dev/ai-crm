"""
Urgency scoring is now handled inside classify_message() in classifier.py.
This module keeps the public function for backward compatibility.
"""
from app.intelligence.classifier import classify_message


def compute_urgency_score(message: str, category: str, sentiment: float) -> float:
    """Return urgency score in [0, 1]. Delegates to the unified Gemini classifier."""
    result = classify_message(message)
    return result["urgency_score"]
