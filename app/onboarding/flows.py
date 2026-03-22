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
            "body": "Welcome to SynapFlow. Start by connecting your channels and Slack workspace.",
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
            "subject": "Your trial is ending soon",
            "body": "Your SynapFlow Starter trial is almost over. Upgrade any time from the billing section.",
        },
        scheduled_for=now + timedelta(days=6),
    )
    enqueue_job(
        "send_email",
        {
            "to_email": user_email,
            "subject": "Your trial has ended",
            "body": "Your trial has ended. Upgrade to Pro, Max, or Scale to keep processing tickets.",
        },
        scheduled_for=now + timedelta(days=8),
    )


def apply_trial_plan(client):
    plan = PLANS["starter"]
    client.plan_id = "starter"
    client.plan = "starter"
    client.monthly_ticket_limit = plan["monthly_tickets"]
    client.trial_ends_at = datetime.now(timezone.utc) + timedelta(days=plan["trial_days"])
    return client
