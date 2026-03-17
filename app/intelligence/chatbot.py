import hashlib
import os

import httpx

from app.db.models import ReplyCache
from app.db.session import SessionLocal
from app.intelligence.classifier import classify_message


GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"


def _cache_key(message, context, history):
    source = f"{message}|{context}|{history}"
    return hashlib.sha256(source.encode()).hexdigest()


def generate_reply(message, context=None, conversation_history=None):
    context = context or {}
    conversation_history = conversation_history or []
    classification = classify_message(message)
    escalate = classification.get("priority", 1) >= 4 or classification.get("recommended_action") == "escalate"
    cache_key = _cache_key(message, context, conversation_history)

    db = SessionLocal()
    try:
        cached = db.query(ReplyCache).filter(ReplyCache.cache_key == cache_key).first()
        if cached:
            cached.hit_count += 1
            db.commit()
            return {"reply": cached.response, "escalate": escalate}
    finally:
        db.close()

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return {"reply": "", "escalate": escalate}

    prompt = f"""
You are a customer support assistant.
Context: {context}
Conversation History: {conversation_history}
Customer Message: {message}
Write a concise, helpful response. Escalate to a human if the message sounds urgent, legal, billing-sensitive, or emotionally intense.
"""

    try:
        response = httpx.post(
            GEMINI_URL,
            params={"key": api_key},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=10.0,
        )
        response.raise_for_status()
        reply = response.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        return {"reply": "", "escalate": escalate}

    db = SessionLocal()
    try:
        db.add(ReplyCache(cache_key=cache_key, prompt=prompt, response=reply))
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()

    return {"reply": reply, "escalate": escalate}
