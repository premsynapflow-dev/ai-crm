import os

import httpx
from typing import Dict, List, Optional
from tenacity import retry, stop_after_attempt, wait_exponential

from app.db.models import Complaint
from app.intelligence.prompt_builder import build_reply_prompt
from app.utils.logging import get_logger

logger = get_logger(__name__)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
async def _call_gemini_for_reply(prompt: str, api_key: str) -> str:
    """Generate reply using Gemini API"""
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent",
            params={"key": api_key},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 500
                },
            }
        )
        response.raise_for_status()
        data = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]


async def generate_ai_reply_async(
    complaint: Complaint,
    customer_history: List[Dict],
    custom_config: Optional[Dict] = None,
) -> Dict:
    """Async version of reply generation with custom prompt support"""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return {
            "reply_text": "Thank you for contacting us. We'll review your message and get back to you soon.",
            "confidence_score": 0.3
        }

    # Build custom prompt using template
    prompt = build_reply_prompt(
        complaint.summary,
        customer_history,
        custom_config  # Pass custom config
    )

    try:
        reply_text = await _call_gemini_for_reply(prompt, api_key)
        confidence = 0.85 if complaint.confidence > 0.7 else 0.65
        
        return {
            "reply_text": reply_text.strip(),
            "confidence_score": confidence
        }
    except Exception as e:
        logger.warning(f"AI reply generation failed: {e}")
        return {
            "reply_text": "Thank you for your message. Our team will review and respond shortly.",
            "confidence_score": 0.3
        }


def generate_ai_reply(
    complaint: Complaint,
    customer_history: List[Dict],
    custom_config: Optional[Dict] = None,
) -> Dict:
    """Sync wrapper - use generate_ai_reply_async in async contexts"""
    import asyncio
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(
        generate_ai_reply_async(complaint, customer_history, custom_config)
    )
