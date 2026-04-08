from datetime import datetime, timezone

from app.config import get_settings
from app.db.models import AIReplyQueue
from app.integrations.email import send_email
from app.integrations.slack import send_slack_alert
from app.services.channel_router import send_reply_via_original_channel
from app.services.event_logger import log_event
from app.services.response_tracking import mark_first_response
from app.utils.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)
REVIEWED_REPLY_QUEUE_STATUSES = {"approved", "edited"}


def ensure_manual_reply_review(db, complaint, *, reviewer_email: str | None, reply_text: str):
    queue_entry = getattr(complaint, "reply_queue", None)
    if queue_entry is not None and queue_entry.status in REVIEWED_REPLY_QUEUE_STATUSES:
        return queue_entry

    normalized_reply = (reply_text or complaint.ai_reply or "").strip()
    if queue_entry is None:
        queue_entry = AIReplyQueue(
            complaint_id=complaint.id,
            client_id=complaint.client_id,
            generated_reply=normalized_reply or "Manual reply",
            confidence_score=1.0,
            generation_strategy="manual",
            generation_metadata={"source": "manual_reply"},
        )
        db.add(queue_entry)
        complaint.reply_queue = queue_entry
    else:
        queue_entry.generated_reply = normalized_reply or queue_entry.generated_reply

    queue_entry.status = "edited"
    queue_entry.reviewed_by = reviewer_email
    queue_entry.reviewed_at = datetime.now(timezone.utc)
    queue_entry.edited_reply = normalized_reply or None
    queue_entry.rejection_reason = None
    db.flush()
    return queue_entry


def send_complaint_reply(
    db,
    complaint,
    client=None,
    reply_text: str | None = None,
    status_on_success: str = "sent",
):

    # ENFORCEMENT: Only allow sending if reply_queue exists and was reviewed.
    reply_queue = getattr(complaint, "reply_queue", None)
    if reply_queue is None or reply_queue.status not in REVIEWED_REPLY_QUEUE_STATUSES:
        logger.warning(
            "Blocked reply send: Complaint %s does not have reviewed AIReplyQueue entry.",
            complaint.id,
        )
        complaint.ai_reply_status = "agent_review"
        db.flush()
        return {"sent": False, "channels": []}

    text_to_send = (reply_text or complaint.ai_reply or "").strip()
    channels_sent: list[str] = []
    delivered_to_customer = False

    if not text_to_send:
        complaint.ai_reply_status = "agent_review"
        db.flush()
        return {"sent": False, "channels": channels_sent}

    native_send_result = send_reply_via_original_channel(
        db=db,
        complaint=complaint,
        client=client,
        reply_text=text_to_send,
    )
    if native_send_result["sent"]:
        channels_sent.extend(native_send_result["channels"])
        delivered_to_customer = True

    legacy_fallback_allowed = complaint.source not in {"gmail", "whatsapp", "email"}

    if complaint.customer_email and not delivered_to_customer and legacy_fallback_allowed:
        email_sent = send_email(
            to_email=complaint.customer_email,
            subject=f"Support Ticket {complaint.ticket_id}",
            body=text_to_send,
        )
        if email_sent and "email" not in channels_sent:
            channels_sent.append("email")
            delivered_to_customer = True

    slack_webhook = None
    if client is not None:
        slack_webhook = client.slack_webhook_url

    if complaint.source == "whatsapp" and complaint.customer_phone and not delivered_to_customer and legacy_fallback_allowed:
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
    elif not channels_sent and legacy_fallback_allowed and (slack_webhook or settings.slack_webhook_url):
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
