from types import SimpleNamespace

from app.intelligence.reply_engine import generate_ai_reply


def generate_reply(summary, intent, category):
    complaint = SimpleNamespace(
        summary=summary,
        intent=intent,
        category=category,
        sentiment=0.0,
    )
    result = generate_ai_reply(complaint, customer_history=[])
    return result.get("reply_text", "")
