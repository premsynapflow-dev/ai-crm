from datetime import datetime, timezone

from app.config import get_settings
from app.integrations.email import send_email
from app.integrations.slack import send_slack_alert
from app.services.event_logger import log_event
from app.services.response_tracking import mark_first_response
from app.utils.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)


def send_complaint_reply(
    db,
    complaint,
    client=None,
    reply_text: str | None = None,
    status_on_success: str = "sent",
):
    text_to_send = (reply_text or complaint.ai_reply or "").strip()
    channels_sent: list[str] = []
    delivered_to_customer = False

    if not text_to_send:
        complaint.ai_reply_status = "agent_review"
        db.flush()
        return {"sent": False, "channels": channels_sent}

    if complaint.customer_email:
        email_sent = send_email(
            to_email=complaint.customer_email,
            subject=f"Support Ticket {complaint.ticket_id}",
            body=text_to_send,
        )
        if email_sent:
            channels_sent.append("email")
            delivered_to_customer = True

    slack_webhook = None
    if client is not None:
        slack_webhook = client.slack_webhook_url

    if complaint.source == "whatsapp" and complaint.customer_phone:
        slack_sent = send_slack_alert(
            (
                "*WhatsApp AI Reply*\n"
                f"Ticket: {complaint.ticket_id}\n"
                f"Phone: {complaint.customer_phone}\n"
                f"Reply:\n{text_to_send}"
            ),
            webhook_url=slack_webhook,
        )
        if slack_sent:
            channels_sent.append("slack")
    elif not channels_sent and (slack_webhook or settings.slack_webhook_url):
        slack_sent = send_slack_alert(
            (
                "*AI Reply Sent*\n"
                f"Ticket: {complaint.ticket_id}\n"
                f"Source: {complaint.source}\n"
                f"Reply:\n{text_to_send}"
            ),
            webhook_url=slack_webhook,
        )
        if slack_sent:
            channels_sent.append("slack")

    if not delivered_to_customer:
        logger.warning(
            "No customer delivery channel available for complaint %s; keeping for agent review.",
            complaint.id,
        )
        complaint.ai_reply = text_to_send
        complaint.ai_reply_status = "agent_review"
        log_event(
            db,
            complaint.client_id,
            "agent_review_requested",
            {
                "ticket_id": complaint.ticket_id,
                "complaint_id": str(complaint.id),
                "summary": complaint.summary,
            },
        )
        db.flush()
        return {"sent": False, "channels": channels_sent}

    sent_at = datetime.now(timezone.utc)
    complaint.ai_reply = text_to_send
    complaint.ai_reply_status = status_on_success
    if complaint.ai_reply_sent_at is None:
        complaint.ai_reply_sent_at = sent_at
    mark_first_response(db, complaint, responded_at=sent_at)
    log_event(
        db,
        complaint.client_id,
        "ai_reply_sent",
        {
            "ticket_id": complaint.ticket_id,
            "complaint_id": str(complaint.id),
            "summary": text_to_send,
            "channels": channels_sent,
            "status": status_on_success,
        },
    )
    db.flush()
    return {"sent": True, "channels": channels_sent}
