import os

import httpx
from typing import Dict, List
from tenacity import retry, stop_after_attempt, wait_exponential

from app.db.models import Complaint
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
    customer_history: List[Dict]
) -> Dict:
    """Async version of reply generation"""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return {
            "reply_text": "Thank you for contacting us. We'll review your message and get back to you soon.",
            "confidence_score": 0.3
        }

    # Build context
    history_text = ""
    if customer_history:
        history_text = "Previous interactions:\n"
        for item in customer_history[-3:]:  # Last 3 only
            history_text += f"- {item.get('summary', '')}\n"

    prompt = f"""You are a helpful customer service agent. Generate a professional, empathetic reply.

Customer message: {complaint.summary}
Category: {complaint.category}
Sentiment: {complaint.sentiment}
{history_text}

Requirements:
- Be empathetic and professional
- Address the specific issue
- Provide actionable next steps if applicable
- Keep it concise (2-3 paragraphs max)
- Don't make promises you can't keep

Reply:"""
    
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


def generate_ai_reply(complaint: Complaint, customer_history: List[Dict]) -> Dict:
    """Sync wrapper - use generate_ai_reply_async in async contexts"""
    import asyncio
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(
        generate_ai_reply_async(complaint, customer_history)
    )
