from app.integrations.slack import send_slack_alert
from app.utils.logging import get_logger

logger = get_logger(__name__)


def dispatch_action(
    action: str,
    client_name: str,
    complaint_id: str,
    summary: str,
    category: str,
    sentiment: float,
    urgency: float,
    intent: str = "complaint",
    recommended_action: str = "support_ticket",
    client_slack_webhook: str | None = None,
    customer_email: str | None = None,
    customer_phone: str | None = None,
) -> None:
    """
    Dispatch post-classification actions.

    - Sales leads    -> Slack alert to client's workspace
    - ESCALATE_HIGH  -> Slack alert to client's workspace
     - Everything else -> no-op (future: email, CRM)
    """
    if recommended_action == "notify_sales":
        slack_message = (
            f"*New Sales Lead Detected*\n"
            f"Client: {client_name}\n"
            f"Complaint ID: {complaint_id}\n"
            f"Intent: {intent}\n"
            f"Customer Email: {customer_email or 'Not provided'}\n"
            f"Customer Phone: {customer_phone or 'Not provided'}\n"
            f"Summary: {summary[:500]}"
        )
        try:
            send_slack_alert(slack_message, webhook_url=client_slack_webhook)
            logger.info("Sales lead Slack alert sent for complaint %s", complaint_id)
        except Exception as exc:
            logger.exception("Slack dispatch failed for sales lead: %s", exc)
        return

    if action == "ESCALATE_HIGH" or recommended_action == "escalate":
        slack_message = (
            f"*High Priority Complaint Escalation*\n"
            f"Client: {client_name}\n"
            f"Complaint ID: {complaint_id}\n"
            f"Category: {category}\n"
            f"Sentiment: {sentiment:.3f}\n"
            f"Urgency: {urgency:.3f}\n"
            f"Customer Email: {customer_email or 'Not provided'}\n"
            f"Customer Phone: {customer_phone or 'Not provided'}\n"
            f"Summary: {summary[:500]}"
        )
        try:
            send_slack_alert(slack_message, webhook_url=client_slack_webhook)
            logger.info("Escalation Slack alert sent for complaint %s", complaint_id)
        except Exception as exc:
            logger.exception("Slack dispatch failed for escalation: %s", exc)
