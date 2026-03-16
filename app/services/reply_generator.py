import os

import httpx


def generate_reply(summary, intent, category):

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        return ""

    prompt = f"""
Write a short customer support reply.

Summary: {summary}
Intent: {intent}
Category: {category}

Reply politely in 3-5 sentences.
"""

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

    try:
        response = httpx.post(
            url,
            params={"key": api_key},
            json={
                "contents": [{"parts": [{"text": prompt}]}]
            },
            timeout=10.0,
        )
        response.raise_for_status()
        text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        return ""

    return text
