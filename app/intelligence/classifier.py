import json
import os

import httpx

from app.utils.logging import get_logger

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


def classify_message(message: str) -> dict:
    """
    Classify a customer message using Gemini 2.0 Flash (free tier).
    Returns a dict with keys:
      intent, category, sentiment, urgency_score,
      priority, recommended_action, confidence, summary
    Falls back to safe defaults on any error.
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        logger.warning("GEMINI_API_KEY not set - using fallback classification.")
        return dict(_FALLBACK, summary=message[:120])

    prompt = (
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
    "Also include a short 1 sentence summary of the message.\n\n"
    "Return exactly this structure:\n"
    "{\n"
    '  "intent": "one of: complaint/refund_request/sales_lead/support/order_status/feature_request",\n'
    '  "category": "one of: refund/billing/technical/abuse/general/sales",\n'
    '  "sentiment": <float -1.0 to 1.0>,\n'
    '  "urgency_score": <float 0.0 to 1.0>,\n'
    '  "priority": <integer 1-5>,\n'
    '  "recommended_action": "one of: escalate/notify_sales/support_ticket/auto_reply/product_feedback",\n'
    '  "confidence": <float 0.0 to 1.0>,\n'
    '  "summary": "short 1 sentence summary of the message"\n'
    "}"
)

    try:
        response = httpx.post(
            _GEMINI_URL,
            params={"key": api_key},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0},
            },
            timeout=10.0,
        )
        response.raise_for_status()

        raw_text = (
            response.json()["candidates"][0]["content"]["parts"][0]["text"]
        )
        clean = (
            raw_text.strip()
            .removeprefix("```json")
            .removeprefix("```")
            .removesuffix("```")
            .strip()
        )
        result = json.loads(clean)

        # Validate and sanitise each field - fall back per-field if invalid
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

    except Exception as exc:
        logger.warning("Gemini classification failed, using fallback: %s", exc)
        return dict(_FALLBACK, summary=message[:120])
