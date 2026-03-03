def decide_action(category: str, sentiment: float, urgency: float) -> str:
    if category == "refund" and urgency > 0.7:
        return "ESCALATE_HIGH"
    if sentiment < -0.8:
        return "ESCALATE_HIGH"
    return "AUTO_REPLY"
