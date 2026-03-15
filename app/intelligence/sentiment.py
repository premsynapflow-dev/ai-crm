"""
Sentiment scoring is now handled inside classify_message() in classifier.py.
This module keeps the public function for backward compatibility.
"""
from app.intelligence.classifier import classify_message
from app.utils.logging import get_logger

logger = get_logger(__name__)


def analyze_sentiment(message: str) -> float:
    """Return sentiment score in [-1, 1]. Delegates to the unified Gemini classifier."""
    result = classify_message(message)
    return result["sentiment"]
