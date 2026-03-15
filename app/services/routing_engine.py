"""
Intent routing is now handled by the unified Gemini classifier.
This module keeps the public interface for backward compatibility.
"""
from app.intelligence.classifier import classify_message


def classify_intent(message: str) -> tuple[str, str, float, int]:
    """
    Returns (intent, recommended_action, confidence, priority).
    Delegates to the unified Gemini classifier.
    """
    result = classify_message(message)
    return (
        result["intent"],
        result["recommended_action"],
        result["confidence"],
        result["priority"],
    )
