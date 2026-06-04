import json
import os
import asyncio
import httpx
import time
from typing import Any, Dict, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.intelligence.prompt_builder import build_classification_prompt
from app.services.model_orchestration import audit_model_call, get_model_orchestrator, parse_json_model_output, timed_ms
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
    "emotion_dimensions": {},
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

# Keyword sets per category — checked in priority order when Gemini returns 'general'
# Keys must match _ALLOWED_CATEGORIES exactly.
_CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "refund": (
        "refund", "money back", "reimburse", "reimbursement",
        "chargeback", "return my money", "give me my money", "want my money",
        "get my money", "i want a refund", "need a refund", "get a refund",
        "request a refund", "please refund", "full refund", "partial refund",
        "cash back", "credit back", "reversal",
    ),
    "billing": (
        "charged", "overcharged", "double charged", "wrong charge", "extra charge",
        "incorrect charge", "unauthorized charge", "unexpected charge",
        "invoice", "billing error", "billing issue", "payment failed",
        "payment issue", "payment declined", "subscription", "subscription fee",
        "auto-renew", "auto renew", "direct debit", "emi", "installment",
        "credit card charge", "transaction", "receipt", "statement",
        "charged twice", "charged wrong", "billed", "bill",
    ),
    "technical": (
        "not working", "doesn't work", "broken", "bug", "error", "crash",
        "glitch", "issue with", "problem with", "login issue", "can't login",
        "cannot login", "won't log in", "password", "forgot password",
        "app not loading", "page not loading", "404", "500", "server error",
        "slow", "lagging", "freezing", "not responding", "keeps crashing",
        "offline", "down", "outage", "service down", "api error",
        "sync issue", "data missing", "integration", "not syncing",
        "feature not working", "button not working", "link not working",
    ),
    "sales": (
        "pricing", "price list", "how much does", "what does it cost",
        "cost of", "quote", "quotation", "get a quote", "demo",
        "free trial", "trial", "upgrade", "downgrade", "switch plan",
        "enterprise plan", "bulk", "wholesale", "volume discount",
        "discount", "offer", "promotion", "looking to buy", "interested in buying",
        "want to purchase", "want to buy", "can i buy", "purchase",
        "what plans", "which plan", "compare plans",
    ),
    "abuse": (
        "threaten", "threatening", "threat", "sue you", "take you to court",
        "lawyer", "legal action", "lawsuit", "going to court", "harassment",
        "harassing", "abusive", "offensive language", "racist", "sexist",
        "discriminat", "hate", "inappropriate", "vulgar",
    ),
    "spam": (
        "unsubscribe", "opt out", "stop emailing", "stop contacting",
        "remove me from", "remove from list", "do not contact",
        "unsolicited", "i never signed up", "i did not sign up",
        "spam", "junk mail", "phishing",
    ),
}

# When intent is X and Gemini returned 'general', override category to Y
_INTENT_TO_CATEGORY: dict[str, str] = {
    "refund_request": "refund",
    "sales_lead": "sales",
}

# When category is X, the most natural intent if Gemini left it as 'complaint'
_CATEGORY_TO_INTENT: dict[str, str] = {
    "refund": "refund_request",
    "sales": "sales_lead",
    "technical": "support",
    "billing": "complaint",
    "abuse": "complaint",
    "spam": "complaint",
}

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


def _correct_classification(category: str, intent: str, message: str) -> tuple[str, str]:
    """
    Post-process Gemini's category/intent to fix systematic under-classification.

    Strategy:
      1. Intent → category: if intent strongly implies a category but Gemini left category='general'
      2. Keyword scan: only applied when category='general' to avoid overriding a valid Gemini pick;
         checked in priority order so the most specific match wins.
      3. Category → intent: if we corrected the category and intent is still 'complaint', nudge to
         the natural intent for that category.
    """
    # Step 1: intent-driven category correction (only when category is ambiguous)
    if category == "general" and intent in _INTENT_TO_CATEGORY:
        category = _INTENT_TO_CATEGORY[intent]

    # Step 2: keyword scan — only override 'general'; trust any specific Gemini pick
    if category == "general":
        msg = message.lower()
        for cat, keywords in _CATEGORY_KEYWORDS.items():
            if any(kw in msg for kw in keywords):
                category = cat
                break  # priority order: refund > billing > technical > sales > abuse > spam

    # Step 3: nudge intent to match the category when intent was left as plain 'complaint'
    if intent == "complaint" and category in _CATEGORY_TO_INTENT:
        intent = _CATEGORY_TO_INTENT[category]

    return category, intent


def normalize_classification_output(result: Optional[dict[str, Any]], message: str) -> dict[str, Any]:
    result = result or {}

    intent = result.get("intent", "complaint")
    if intent not in _ALLOWED_INTENTS:
        intent = "complaint"

    category = result.get("category", "general")
    if category not in _ALLOWED_CATEGORIES:
        category = "general"

    category, intent = _correct_classification(category, intent, message)

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

    def _emotion_dimensions(raw: Any) -> dict[str, float]:
        if not isinstance(raw, dict):
            return {}
        allowed = ("frustration", "urgency", "confusion", "satisfaction", "aggression", "loyalty")
        return {
            key: round(_clamp(raw.get(key), 0.0, 1.0, 0.0), 4)
            for key in allowed
            if raw.get(key) is not None
        }

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
        "emotion_dimensions": _emotion_dimensions(result.get("emotion_dimensions")),
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
    if not message or not message.strip():
        logger.warning("Empty message received - using fallback classification.")
        return normalize_classification_output(_FALLBACK, message)

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        logger.warning("GEMINI_API_KEY not set - using fallback classification.")
        return normalize_classification_output(_FALLBACK, message)

    prompt = _build_classification_prompt(message, client_config)
    started = time.perf_counter()
    try:
        raw = await get_model_orchestrator().classify_message(message, client_config)
        parsed = normalize_classification_output(parse_json_model_output(raw["raw_text"]), message)
        return parsed
    except CircuitBreakerOpenError:
        logger.warning("Gemini circuit breaker is OPEN - using fallback")
        return normalize_classification_output(_FALLBACK, message)
    except Exception as exc:
        logger.warning(f"Gemini classification failed after retries: {exc}")
        return normalize_classification_output(_FALLBACK, message)


def classify_message(message: str, client_config: Optional[dict] = None) -> Dict:
    """
    Sync wrapper for classification. Safe to call from both sync and async contexts.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop in this thread — safe to use asyncio.run()
        return asyncio.run(classify_message_async(message, client_config))

    # Called from inside a running event loop (e.g. an async FastAPI route).
    # Run the coroutine in a separate thread pool to avoid blocking.
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(asyncio.run, classify_message_async(message, client_config))
        try:
            return future.result(timeout=30)
        except Exception as exc:
            logger.warning("classify_message thread-pool execution failed: %s", exc)
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
