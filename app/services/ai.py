import json
import re
from dataclasses import dataclass

import httpx

from app.config import get_settings


@dataclass
class GeminiResponse:
    text: str


class GeminiClient:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def generate_content(
        self,
        prompt: str,
        *,
        model: str = "gemini-2.5-flash-lite",
        max_output_tokens: int = 700,
        temperature: float = 0.2,
    ) -> GeminiResponse:
        response = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            params={"key": self.api_key},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": temperature,
                    "maxOutputTokens": max_output_tokens,
                },
            },
            timeout=20.0,
        )
        response.raise_for_status()
        payload = response.json()
        text = (
            payload.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )
        return GeminiResponse(text=text)


def get_gemini_client() -> GeminiClient:
    settings = get_settings()
    api_key = (settings.gemini_api_key or "").strip()
    if not api_key:
        raise RuntimeError("Gemini API key is not configured")
    return GeminiClient(api_key)


def _extract_json_payload(raw_text: str) -> dict:
    text = raw_text.strip()
    fenced_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fenced_match:
        text = fenced_match.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        json_match = re.search(r"(\{.*\})", text, re.DOTALL)
        if not json_match:
            raise
        return json.loads(json_match.group(1))


def suggest_response(complaint_text: str, category: str, similar_resolved: list[dict]) -> dict:
    """
    Generate an AI-suggested response using similar resolved complaints as context.
    """
    try:
        client = get_gemini_client()
        context = "\n\n".join(
            [
                f"Similar complaint: {item.get('complaint_text', '')}\nResolution: {item.get('resolution', '')}"
                for item in similar_resolved[:3]
            ]
        ) or "No similar resolved complaints found."

        prompt = f"""You are a customer support AI assistant. Generate a professional, empathetic response to this complaint.

Complaint Category: {category}
Complaint: {complaint_text}

Context from similar resolved complaints:
{context}

Generate a response that:
1. Acknowledges the customer's concern
2. Shows empathy
3. Provides a clear solution or next steps
4. Maintains a professional tone
5. Stays concise (2-3 short paragraphs maximum)

Response:"""

        response = client.generate_content(prompt, temperature=0.35, max_output_tokens=500)
        suggested_text = response.text.strip()

        return {
            "suggested_response": suggested_text,
            "confidence": 0.85 if similar_resolved else 0.72,
            "based_on_similar_cases": len(similar_resolved),
        }
    except Exception as exc:
        return {
            "suggested_response": (
                "I apologize for the inconvenience. Our team is reviewing this issue and "
                "will get back to you shortly with the next steps."
            ),
            "confidence": 0.5,
            "error": str(exc),
        }


__all__ = [
    "GeminiClient",
    "GeminiResponse",
    "get_gemini_client",
    "suggest_response",
    "_extract_json_payload",
]
