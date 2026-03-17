from app.intelligence.classifier import classify_message


_SIMPLE_QUESTIONS = ("how", "what", "when", "where", "why", "can")


def classify_with_context(message: str, context: dict | None = None) -> dict:
    context = context or {}
    result = classify_message(message)
    lowered = message.strip().lower()

    if lowered.startswith(_SIMPLE_QUESTIONS):
        message_type = "question"
    elif result.get("intent") == "feature_request":
        message_type = "request"
    else:
        message_type = "complaint"

    suggestion = ""
    if result.get("priority", 1) <= 2 and message_type == "question":
        suggestion = "Provide a concise self-serve answer and ask if more help is needed."

    result["message_type"] = message_type
    result["context_used"] = bool(context)
    result["suggested_auto_response"] = suggestion
    return result
