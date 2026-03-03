def compute_urgency_score(message: str, category: str, sentiment: float) -> float:
    text = message.lower()

    urgency = 0.2
    if category == "refund":
        urgency += 0.3
    if category == "abuse":
        urgency += 0.4

    urgency += max(0.0, (-sentiment) * 0.5)

    hot_keywords = ("immediately", "urgent", "lawyer", "legal", "cancel", "fraud")
    if any(word in text for word in hot_keywords):
        urgency += 0.2

    return max(0.0, min(1.0, urgency))
