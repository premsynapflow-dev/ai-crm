from app.integrations.slack import send_slack_alert
from app.utils.logging import get_logger

logger = get_logger(__name__)


def dispatch_action(
    action: str,
    client_name: str,
    complaint_id: str,
    message: str,
    category: str,
    sentiment: float,
    urgency: float,
) -> None:
    if action != "ESCALATE_HIGH":
        return

    slack_message = (
        f"*High Priority Complaint Escalation*\n"
        f"Client: {client_name}\n"
        f"Complaint ID: {complaint_id}\n"
        f"Category: {category}\n"
        f"Sentiment: {sentiment:.3f}\n"
        f"Urgency: {urgency:.3f}\n"
        f"Message: {message[:800]}"
    )

    try:
        send_slack_alert(slack_message)
    except Exception as exc:
        logger.exception("Slack dispatch failed: %s", exc)
