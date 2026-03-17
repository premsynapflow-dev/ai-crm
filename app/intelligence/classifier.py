import json
import os
import httpx
from typing import Dict
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

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
_ALLOWED_CATEGORIES = {"refund", "billing", "technical", "abuse", "general", "sales"}
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


def _build_classification_prompt(message: str) -> str:
    """Build prompt for classification"""
    return (
        'Classify this customer message and return ONLY valid JSON, no markdown.\n\n'
        f'Message: "{message}"\n\n'
        "Rules for recommended_action:\n"
        "- Use 'escalate' when: refund request, fraud claim, urgent complaint, "
        "legal threat, abuse, or sentiment is very negative (below -0.7)\n"
        "- Use 'notify_sales' when: pricing inquiry, enterprise/bulk question, "
        "upgrade interest, or sales opportunity\n"
        "- Use 'support_ticket' when: general help, order status, technical issue\n"
        "- Use 'auto_reply' when: simple FAQ, easily resolved automatically\n"
        "- Use 'product_feedback' when: feature request or product suggestion\n\n"
        "Also include a short concise summary of the message.\n\n"
        "Return exactly this structure:\n"
        "{\n"
        '  "intent": "one of: complaint/refund_request/sales_lead/support/order_status/feature_request",\n'
        '  "category": "one of: refund/billing/technical/abuse/general/sales",\n'
        '  "sentiment": <float -1.0 to 1.0>,\n'
        '  "urgency_score": <float 0.0 to 1.0>,\n'
        '  "priority": <integer 1-5>,\n'
        '  "recommended_action": "one of: escalate/notify_sales/support_ticket/auto_reply/product_feedback",\n'
        '  "confidence": <float 0.0 to 1.0>,\n'
        '  "summary": "short concise summary of the message"\n'
        "}"
    )


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
        result = json.loads(clean)
        
        # Validate and sanitize each field
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
        
        return {
            "intent": intent,
            "category": category,
            "sentiment": _clamp(result.get("sentiment"), -1.0, 1.0, 0.0),
            "urgency_score": _clamp(result.get("urgency_score"), 0.0, 1.0, 0.3),
            "priority": max(1, min(5, int(result.get("priority", 2)))),
            "recommended_action": recommended_action,
            "confidence": _clamp(result.get("confidence"), 0.0, 1.0, 0.5),
            "summary": summary,
        }
    except Exception as e:
        logger.warning(f"Failed to parse Gemini response: {e}")
        return dict(_FALLBACK, summary=message[:120])


async def classify_message_async(message: str) -> Dict:
    """ 
    Async version: Classify a customer message using Gemini.
    Returns classification dict or fallback on error.
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        logger.warning("GEMINI_API_KEY not set - using fallback classification.")
        return dict(_FALLBACK, summary=message[:120])
    
    try:
        prompt = _build_classification_prompt(message)
        raw_response = await _call_gemini_api(prompt, api_key)
        return _parse_and_validate(raw_response, message)
    except CircuitBreakerOpenError:
        logger.warning("Gemini circuit breaker is OPEN - using fallback")
        return dict(_FALLBACK, summary=message[:120])
    except Exception as exc:
        logger.warning(f"Gemini classification failed after retries: {exc}")
        return dict(_FALLBACK, summary=message[:120])


def classify_message(message: str) -> Dict:
    """
    Sync wrapper for backwards compatibility.
    Use classify_message_async in async contexts.
    """
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If called from async context, use async version
            raise RuntimeError("Use classify_message_async in async context")
        return loop.run_until_complete(classify_message_async(message))
    except RuntimeError:
        # Fallback for sync contexts
        logger.warning("Called sync classify_message - consider using async version")
        return dict(_FALLBACK, summary=message[:120])


def summarize_if_needed(message: str, classification: dict) -> str:
    """Summarize long messages"""
    words = message.split()
    
    if len(words) <= 40:
        return message.strip()
    
    summary = classification.get("summary")
    if summary:
        return str(summary).strip()[:400]
    
    return " ".join(words[:40])
