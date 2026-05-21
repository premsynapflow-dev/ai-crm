from __future__ import annotations

from app.integrations.slack import send_slack_alert
from app.db.models import WorkflowExecution
from app.services.event_logger import log_event
from sqlalchemy.orm import object_session


def execute_action(
    rule,
    complaint,
    client,
    *,
    db=None,
    trigger_event_type: str | None = None,
    execution: WorkflowExecution | None = None,
    action_payload: dict | None = None,
):
    db = db or object_session(rule)
    action_payload = action_payload or {}
    action = action_payload.get("type") or rule.action_type
    if db is not None:
        if execution is None:
            execution = WorkflowExecution(
                client_id=client.id,
                automation_rule_id=rule.id,
                complaint_id=complaint.id,
                customer_id=complaint.customer_id,
                trigger_event_type=trigger_event_type or rule.trigger_type,
                action_type=action,
                execution_status="running",
                execution_logs={
                    "rule_id": str(rule.id),
                    "trigger_type": rule.trigger_type,
                    "trigger_value": rule.trigger_value,
                    "mode": "sync",
                },
            )
            db.add(execution)
        else:
            execution.execution_status = "running"
            execution.action_type = action
            execution.execution_logs = {
                **(execution.execution_logs or {}),
                "rule_id": str(rule.id),
                "trigger_type": rule.trigger_type,
                "trigger_value": rule.trigger_value,
                "mode": "async",
            }
        db.flush()

    try:
        if action == "notify_slack":

            message = f"""
Automation Rule Triggered

Client: {client.name}
Ticket: {complaint.ticket_id}
Summary: {complaint.summary}
Intent: {complaint.intent}
"""

            send_slack_alert(message, webhook_url=client.slack_webhook_url)

        elif action in {"mark_high_priority", "assign_priority_agent"}:

            complaint.priority = 5

        elif action == "auto_resolve":

            complaint.resolution_status = "resolved"

        elif action == "create_escalation_ticket":

            complaint.escalation_level = max(int(complaint.escalation_level or 0), 1)
            complaint.status = "ESCALATE_HIGH"

        else:
            raise ValueError(f"Unsupported automation action: {action}")

        if execution is not None:
            execution.execution_status = "succeeded"
            execution.execution_logs = {
                **(execution.execution_logs or {}),
                "outcome": "action_completed",
                "ticket_id": complaint.ticket_id,
            }
        if db is not None:
            log_event(
                db,
                client.id,
                "workflow_action_succeeded",
                {
                    "rule_id": str(rule.id),
                    "action_type": action,
                    "ticket_id": complaint.ticket_id,
                    "complaint_id": str(complaint.id),
                    "customer_id": str(complaint.customer_id) if complaint.customer_id else None,
                    "workflow_execution_id": str(execution.id) if execution is not None else None,
                },
                customer_id=complaint.customer_id,
                complaint_id=complaint.id,
                source="workflow",
                actor_type="system",
            )
        return execution
    except Exception as exc:
        if execution is not None:
            execution.execution_status = "failed"
            execution.error_message = str(exc)
            execution.execution_logs = {
                **(execution.execution_logs or {}),
                "outcome": "action_failed",
                "error": str(exc),
            }
        if db is not None:
            log_event(
                db,
                client.id,
                "workflow_action_failed",
                {
                    "rule_id": str(rule.id),
                    "action_type": action,
                    "ticket_id": complaint.ticket_id,
                    "complaint_id": str(complaint.id),
                    "customer_id": str(complaint.customer_id) if complaint.customer_id else None,
                    "workflow_execution_id": str(execution.id) if execution is not None else None,
                    "error": str(exc),
                },
                customer_id=complaint.customer_id,
                complaint_id=complaint.id,
                source="workflow",
                actor_type="system",
            )
        raise
