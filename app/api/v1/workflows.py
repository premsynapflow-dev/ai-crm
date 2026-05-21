from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.models import AutomationRule, WorkflowExecution
from app.db.session import get_db
from app.dependencies.auth import require_api_key
from app.services.workflow_dsl import evaluate_rule, validate_workflow_definition

router = APIRouter(prefix="/api/v1/workflows", tags=["workflows-v1"])


class WorkflowRuleRequest(BaseModel):
    workflow_name: str | None = None
    trigger: dict[str, Any] = Field(default_factory=dict)
    conditions: list[dict[str, Any]] = Field(default_factory=list)
    actions: list[dict[str, Any]] = Field(default_factory=list)
    enabled: bool = True


class WorkflowPreviewRequest(BaseModel):
    context: dict[str, Any] = Field(default_factory=dict)


def _serialize_rule(rule: AutomationRule) -> dict[str, Any]:
    return {
        "id": str(rule.id),
        "workflow_name": rule.workflow_name,
        "trigger": rule.trigger_definition or {"type": rule.trigger_type, "value": rule.trigger_value},
        "conditions": rule.condition_definition or [],
        "actions": rule.action_definition or [{"type": rule.action_type, "config": rule.action_config or {}}],
        "enabled": bool(rule.enabled),
        "created_at": rule.created_at.isoformat() if rule.created_at else None,
    }


@router.post("/validate")
def validate_workflow(payload: WorkflowRuleRequest, current_client=Depends(require_api_key)):
    return validate_workflow_definition(payload.model_dump())


@router.get("")
def list_workflows(db: Session = Depends(get_db), current_client=Depends(require_api_key)):
    rules = db.query(AutomationRule).filter(AutomationRule.client_id == current_client.id).order_by(AutomationRule.created_at.desc()).all()
    return {"items": [_serialize_rule(rule) for rule in rules]}


@router.post("")
def create_workflow(payload: WorkflowRuleRequest, db: Session = Depends(get_db), current_client=Depends(require_api_key)):
    validation = validate_workflow_definition(payload.model_dump())
    if not validation["valid"]:
        raise HTTPException(status_code=400, detail=validation["errors"])
    first_action = payload.actions[0]
    rule = AutomationRule(
        client_id=current_client.id,
        workflow_name=payload.workflow_name or payload.trigger.get("type") or "Workflow",
        trigger_type=str(payload.trigger.get("type") or "event"),
        trigger_value=str(payload.trigger.get("value") or ""),
        action_type=str(first_action.get("type")),
        action_config=first_action.get("config") or {},
        trigger_definition=payload.trigger,
        condition_definition=payload.conditions,
        action_definition=payload.actions,
        enabled=payload.enabled,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return {"success": True, "item": _serialize_rule(rule)}


@router.post("/{rule_id}/preview")
def preview_workflow(rule_id: str, payload: WorkflowPreviewRequest, db: Session = Depends(get_db), current_client=Depends(require_api_key)):
    rule = db.query(AutomationRule).filter(AutomationRule.id == uuid.UUID(rule_id), AutomationRule.client_id == current_client.id).first()
    if rule is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    result = evaluate_rule(rule, payload.context)
    return {"matched": result.matched, "reasons": result.reasons, "actions": result.actions}


@router.get("/executions")
def list_workflow_executions(limit: int = 50, db: Session = Depends(get_db), current_client=Depends(require_api_key)):
    rows = (
        db.query(WorkflowExecution)
        .filter(WorkflowExecution.client_id == current_client.id)
        .order_by(WorkflowExecution.executed_at.desc())
        .limit(max(1, min(limit, 100)))
        .all()
    )
    return {
        "items": [
            {
                "id": str(row.id),
                "automation_rule_id": str(row.automation_rule_id) if row.automation_rule_id else None,
                "complaint_id": str(row.complaint_id) if row.complaint_id else None,
                "customer_id": str(row.customer_id) if row.customer_id else None,
                "action_type": row.action_type,
                "execution_status": row.execution_status,
                "execution_logs": row.execution_logs or {},
                "error_message": row.error_message,
                "executed_at": row.executed_at.isoformat() if row.executed_at else None,
            }
            for row in rows
        ]
    }
