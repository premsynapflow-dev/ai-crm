from datetime import datetime, timedelta, timezone

from app.billing.plans import PLANS
from app.queue.simple_queue import enqueue_job


def enqueue_welcome_sequence(client, user_email):
    now = datetime.now(timezone.utc)
    enqueue_job(
        "send_email",
        {
            "to_email": user_email,
            "subject": "Welcome to SynapFlow",
            "body": "Welcome to SynapFlow. Start by connecting your channels and setting up your workspace.",
        },
    )
    enqueue_job(
        "send_email",
        {
            "to_email": user_email,
            "subject": "Need help getting started?",
            "body": "Reply to this email if you want help configuring your complaint channels.",
        },
        scheduled_for=now + timedelta(days=3),
    )
    enqueue_job(
        "send_email",
        {
            "to_email": user_email,
            "subject": "Ready to unlock more automation?",
            "body": "Upgrade to Starter, Pro, Max, or Scale any time from the billing section when you need more volume and automation.",
        },
        scheduled_for=now + timedelta(days=6),
    )
    enqueue_job(
        "send_email",
        {
            "to_email": user_email,
            "subject": "Need more capacity?",
            "body": "If you are approaching your Free plan limits, upgrade to unlock more tickets, more seats, and advanced automation features.",
        },
        scheduled_for=now + timedelta(days=8),
    )


def apply_signup_plan(client):
    plan = PLANS["free"]
    client.plan_id = "free"
    client.plan = "free"
    client.monthly_ticket_limit = plan["monthly_tickets"]
    client.trial_ends_at = None
    return client
