import json
import os

import httpx

from app.utils.logging import get_logger

logger = get_logger(__name__)

_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.5-flash-lite:generateContent"
)

_FALLBACK_REPLY = (
    "Hello,\n\n"
    "Thank you for reaching out. We have received your message and our team is "
    "reviewing it now. We will follow up with the next steps shortly.\n\n"
    "Regards,\nSupport Team"
)


def _clamp_confidence(value, default=0.0) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def generate_ai_reply(complaint, customer_history) -> dict:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        logger.warning("GEMINI_API_KEY not set - using fallback AI reply.")
        return {
            "reply_text": _FALLBACK_REPLY,
            "confidence_score": 0.0,
        }

    history = "\n".join(f"- {item}" for item in customer_history if item) or "- No previous complaints"
    prompt = (
        "You are a professional customer support agent.\n\n"
        f"Customer complaint:\n{complaint.summary}\n\n"
        f"Customer sentiment:\n{complaint.sentiment}\n\n"
        f"Customer previous complaints:\n{history}\n\n"
        "Write a short empathetic reply explaining next steps.\n"
        "Return ONLY valid JSON in this exact shape:\n"
        "{\n"
        '  "reply_text": "short professional reply",\n'
        '  "confidence_score": <float 0.0 to 1.0>\n'
        "}"
    )

    try:
        response = httpx.post(
            _GEMINI_URL,
            params={"key": api_key},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.2},
            },
            timeout=12.0,
        )
        response.raise_for_status()
        raw_text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        clean = (
            raw_text.strip()
            .removeprefix("```json")
            .removeprefix("```")
            .removesuffix("```")
            .strip()
        )
        result = json.loads(clean)
        reply_text = str(result.get("reply_text", "")).strip() or _FALLBACK_REPLY
        confidence_score = _clamp_confidence(
            result.get("confidence_score"),
            default=0.0,
        )
        return {
            "reply_text": reply_text,
            "confidence_score": confidence_score,
        }
    except Exception as exc:
        logger.warning("AI reply generation failed, using fallback reply: %s", exc)
        return {
            "reply_text": _FALLBACK_REPLY,
            "confidence_score": 0.0,
        }
