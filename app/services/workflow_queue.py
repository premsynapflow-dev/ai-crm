from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import AutomationRule, Client, Complaint, JobQueue, WorkflowExecution
from app.services.action_executor import execute_action
from app.services.event_logger import log_event
from app.utils.logging import get_logger

logger = get_logger(__name__)

WORKFLOW_JOB_TYPE = "execute_workflow_action"
TERMINAL_STATUSES = {"succeeded", "dead_letter", "skipped"}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_uuid(value) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


def _idempotency_key(
    *,
    client_id,
    automation_rule_id,
    complaint_id,
    action_type: str,
    trigger_event_type: str | None,
    trigger_event_id=None,
) -> str:
    trigger_part = str(trigger_event_id or trigger_event_type or "manual")
    return ":".join(
        [
            "workflow",
            str(client_id),
            str(automation_rule_id),
            str(complaint_id or "none"),
            str(action_type),
            trigger_part,
        ]
    )[:255]


def enqueue_workflow_action(
    db: Session,
    *,
    rule: AutomationRule,
    complaint: Complaint,
    client: Client,
    action_payload: dict[str, Any] | None = None,
    trigger_event_type: str | None = None,
    trigger_event_id=None,
    max_retries: int = 3,
) -> WorkflowExecution:
    """Create a workflow execution and queue its worker job in the caller's transaction."""
    action_payload = action_payload or {"type": rule.action_type, "config": rule.action_config or {}}
    action_type = str(action_payload.get("type") or rule.action_type)
    key = _idempotency_key(
        client_id=client.id,
        automation_rule_id=rule.id,
        complaint_id=complaint.id,
        action_type=action_type,
        trigger_event_type=trigger_event_type or rule.trigger_type,
        trigger_event_id=trigger_event_id,
    )
    existing = (
        db.query(WorkflowExecution)
        .filter(
            WorkflowExecution.client_id == client.id,
            WorkflowExecution.idempotency_key == key,
            WorkflowExecution.execution_status.in_(["queued", "running", "succeeded"]),
        )
        .first()
    )
    if existing is not None:
        return existing

    execution = WorkflowExecution(
        client_id=client.id,
        automation_rule_id=rule.id,
        complaint_id=complaint.id,
        customer_id=complaint.customer_id,
        trigger_event_id=trigger_event_id,
        trigger_event_type=trigger_event_type or rule.trigger_type,
        action_type=action_type,
        execution_status="queued",
        retry_count=0,
        max_retries=max(1, max_retries),
        idempotency_key=key,
        execution_logs={
            "rule_id": str(rule.id),
            "trigger_type": rule.trigger_type,
            "trigger_value": rule.trigger_value,
            "action": action_payload,
            "mode": "async",
        },
        created_at=_utcnow(),
        executed_at=_utcnow(),
    )
    db.add(execution)
    db.flush()

    job = JobQueue(
        job_type=WORKFLOW_JOB_TYPE,
        payload={
            "workflow_execution_id": str(execution.id),
            "client_id": str(client.id),
            "automation_rule_id": str(rule.id),
            "complaint_id": str(complaint.id),
            "action": action_payload,
        },
        status="queued",
        retry_count=0,
    )
    db.add(job)
    db.flush()
    execution.job_id = job.id

    log_event(
        db,
        client.id,
        "workflow_action_queued",
        {
            "workflow_execution_id": str(execution.id),
            "job_id": str(job.id),
            "rule_id": str(rule.id),
            "action_type": action_type,
            "complaint_id": str(complaint.id),
            "ticket_id": complaint.ticket_id,
            "customer_id": str(complaint.customer_id) if complaint.customer_id else None,
        },
        customer_id=complaint.customer_id,
        complaint_id=complaint.id,
        source="workflow",
        actor_type="system",
    )
    return execution


def enqueue_matching_workflows(
    db: Session,
    *,
    rules: list[AutomationRule],
    complaint: Complaint,
    client: Client,
    trigger_event_type: str,
    trigger_event_id=None,
) -> list[WorkflowExecution]:
    executions: list[WorkflowExecution] = []
    for rule in rules:
        actions = rule.action_definition or [{"type": rule.action_type, "config": rule.action_config or {}}]
        for action_payload in actions:
            execution = enqueue_workflow_action(
                db,
                rule=rule,
                complaint=complaint,
                client=client,
                action_payload=action_payload,
                trigger_event_type=trigger_event_type,
                trigger_event_id=trigger_event_id,
            )
            executions.append(execution)
    return executions


def process_workflow_action_job(payload: dict[str, Any]) -> None:
    from app.db.session import SessionLocal

    execution_id = _as_uuid(payload["workflow_execution_id"])
    db = SessionLocal()
    try:
        query = db.query(WorkflowExecution).filter(WorkflowExecution.id == execution_id)
        if db.get_bind() is not None and db.get_bind().dialect.name.startswith("postgresql"):
            query = query.with_for_update()
        execution = query.first()
        if execution is None:
            logger.warning("Workflow execution job skipped; execution %s not found", execution_id)
            return
        if execution.execution_status in TERMINAL_STATUSES:
            return
        if execution.retry_count >= execution.max_retries:
            execution.execution_status = "dead_letter"
            execution.failed_at = _utcnow()
            execution.error_message = execution.error_message or "Retry budget exhausted before execution"
            db.commit()
            return

        rule = (
            db.query(AutomationRule)
            .filter(
                AutomationRule.id == execution.automation_rule_id,
                AutomationRule.client_id == execution.client_id,
            )
            .first()
        )
        complaint = (
            db.query(Complaint)
            .filter(
                Complaint.id == execution.complaint_id,
                Complaint.client_id == execution.client_id,
            )
            .first()
        )
        client = db.query(Client).filter(Client.id == execution.client_id).first()
        if rule is None or complaint is None or client is None:
            execution.execution_status = "dead_letter"
            execution.failed_at = _utcnow()
            execution.error_message = "Workflow execution references missing rule, complaint, or client"
            execution.error_json = {
                "missing_rule": rule is None,
                "missing_complaint": complaint is None,
                "missing_client": client is None,
            }
            db.commit()
            return

        execution.execution_status = "running"
        execution.started_at = execution.started_at or _utcnow()
        execution.executed_at = _utcnow()
        db.flush()

        action_payload = payload.get("action") or (execution.execution_logs or {}).get("action") or {}
        execute_action(
            rule,
            complaint,
            client,
            db=db,
            trigger_event_type=execution.trigger_event_type,
            execution=execution,
            action_payload=action_payload,
        )
        execution.execution_status = "succeeded"
        execution.completed_at = _utcnow()
        execution.error_message = None
        execution.error_json = {}
        db.commit()
    except Exception as exc:
        db.rollback()
        _mark_execution_failed(execution_id, exc)
        raise
    finally:
        db.close()


def _mark_execution_failed(execution_id: uuid.UUID, exc: Exception) -> None:
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        execution = db.query(WorkflowExecution).filter(WorkflowExecution.id == execution_id).first()
        if execution is None:
            return
        execution.retry_count = int(execution.retry_count or 0) + 1
        execution.error_message = str(exc)
        execution.error_json = {"type": exc.__class__.__name__, "message": str(exc)}
        execution.failed_at = _utcnow()
        execution.execution_status = "dead_letter" if execution.retry_count >= execution.max_retries else "failed"
        execution.execution_logs = {
            **(execution.execution_logs or {}),
            "last_failure_at": _utcnow().isoformat(),
            "retry_count": execution.retry_count,
        }
        log_event(
            db,
            execution.client_id,
            "workflow_action_dead_letter" if execution.execution_status == "dead_letter" else "workflow_action_retry_scheduled",
            {
                "workflow_execution_id": str(execution.id),
                "rule_id": str(execution.automation_rule_id) if execution.automation_rule_id else None,
                "action_type": execution.action_type,
                "retry_count": execution.retry_count,
                "max_retries": execution.max_retries,
                "error": str(exc),
            },
            customer_id=execution.customer_id,
            complaint_id=execution.complaint_id,
            source="workflow",
            actor_type="system",
        )
        db.commit()
    finally:
        db.close()
