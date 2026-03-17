def decide_reply_action(confidence: float) -> str:
    if confidence > 0.85:
        return "auto_send_reply"
    return "mark_for_agent_review"
