import json
import os
import asyncio
import httpx
from typing import Any, Dict, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.intelligence.prompt_builder import build_classification_prompt
from app.utils.logging import get_logger
from app.utils.circuit_breaker import gemini_breaker, CircuitBreakerOpenError

logger = get_logger(__name__)

_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.5-flash-lite:generateContent"
)

_FALLBACK = {
    "intent": "complaint",
    "category": "general",
    "sentiment": 0.0,
    "urgency_score": 0.3,
    "priority": 2,
    "recommended_action": "support_ticket",
    "confidence": 0.0,
    "summary": "",
}

_ALLOWED_INTENTS = {
    "complaint",
    "refund_request",
    "sales_lead",
    "support",
    "order_status",
    "feature_request",
}
_ALLOWED_CATEGORIES = {"refund", "billing", "technical", "abuse", "general", "sales", "spam"}
_ALLOWED_ACTIONS = {
    "escalate",
    "notify_sales",
    "support_ticket",
    "auto_reply",
    "product_feedback",
}


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPStatusError)),
    reraise=True,
)
async def _call_gemini_api(prompt: str, api_key: str) -> dict:
    """Make async API call to Gemini with retry logic"""
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            _GEMINI_URL,
            params={"key": api_key},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0},
            },
        )
        response.raise_for_status()
        return response.json()


def _build_classification_prompt(message: str, client_config: Optional[dict] = None) -> str:
    """Build classification prompt - uses merged client config when provided."""
    return build_classification_prompt(message, client_config)


def normalize_classification_output(result: Optional[dict[str, Any]], message: str) -> dict[str, Any]:
    result = result or {}

    intent = result.get("intent", "complaint")
    if intent not in _ALLOWED_INTENTS:
        intent = "complaint"

    category = result.get("category", "general")
    if category not in _ALLOWED_CATEGORIES:
        category = "general"

    recommended_action = result.get("recommended_action", "support_ticket")
    if recommended_action not in _ALLOWED_ACTIONS:
        recommended_action = "support_ticket"

    summary = result.get("summary", message[:120])
    if not isinstance(summary, str):
        summary = message[:120]
    summary = summary.strip() or message[:120]

    def _clamp(val, lo, hi, default):
        try:
            return max(lo, min(hi, float(val)))
        except (TypeError, ValueError):
            return default

    try:
        priority = max(1, min(5, int(result.get("priority", 2))))
    except (TypeError, ValueError):
        priority = 2

    return {
        "intent": intent,
        "category": category,
        "sentiment": _clamp(result.get("sentiment"), -1.0, 1.0, 0.0),
        "urgency_score": _clamp(result.get("urgency_score"), 0.0, 1.0, 0.3),
        "priority": priority,
        "recommended_action": recommended_action,
        "confidence": _clamp(result.get("confidence"), 0.0, 1.0, 0.5),
        "summary": summary,
    }


def _parse_and_validate(raw_response: dict, message: str) -> dict:
    """Parse and validate Gemini response"""
    try:
        raw_text = raw_response["candidates"][0]["content"]["parts"][0]["text"]
        clean = (
            raw_text.strip()
            .removeprefix("```json")
            .removeprefix("```")
            .removesuffix("```")
            .strip()
        )
        return normalize_classification_output(json.loads(clean), message)
    except Exception as e:
        logger.warning(f"Failed to parse Gemini response: {e}")
        return normalize_classification_output(_FALLBACK, message)


async def classify_message_async(message: str, client_config: Optional[dict] = None) -> Dict:
    """ 
    Async version: Classify a customer message using Gemini.

    Args:
        message: Customer message to classify
        client_config: Optional merged client classification config

    Returns:
        Classification dict or fallback on error.
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        logger.warning("GEMINI_API_KEY not set - using fallback classification.")
        return normalize_classification_output(_FALLBACK, message)
    
    try:
        prompt = _build_classification_prompt(message, client_config)
        raw_response = await _call_gemini_api(prompt, api_key)
        return _parse_and_validate(raw_response, message)
    except CircuitBreakerOpenError:
        logger.warning("Gemini circuit breaker is OPEN - using fallback")
        return normalize_classification_output(_FALLBACK, message)
    except Exception as exc:
        logger.warning(f"Gemini classification failed after retries: {exc}")
        return normalize_classification_output(_FALLBACK, message)


def classify_message(message: str, client_config: Optional[dict] = None) -> Dict:
    """
    Sync wrapper for classification.
    Use classify_message_async in async contexts.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(classify_message_async(message, client_config))

    logger.warning("classify_message called in async context; use classify_message_async instead")
    return normalize_classification_output(_FALLBACK, message)


def summarize_if_needed(message: str, classification: dict) -> str:
    """Summarize long messages"""
    words = message.split()
    
    if len(words) <= 40:
        return message.strip()
    
    summary = classification.get("summary")
    if summary:
        return str(summary).strip()[:400]
    
    return " ".join(words[:40])
