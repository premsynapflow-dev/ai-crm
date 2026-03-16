from app.integrations.slack import send_slack_alert


def execute_action(rule, complaint, client):

    action = rule.action_type

    if action == "notify_slack":

        message = f"""
Automation Rule Triggered

Client: {client.name}
Ticket: {complaint.ticket_id}
Summary: {complaint.summary}
Intent: {complaint.intent}
"""

        send_slack_alert(message, webhook_url=client.slack_webhook_url)

    elif action == "mark_high_priority":

        complaint.priority = 5

    elif action == "auto_resolve":

        complaint.resolution_status = "resolved"
