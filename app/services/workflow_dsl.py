from __future__ import annotations

import operator
from dataclasses import dataclass
from typing import Any

from app.db.models import AutomationRule, Complaint


OPS = {
    "==": operator.eq,
    "!=": operator.ne,
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
    "in": lambda left, right: left in right if isinstance(right, list) else False,
    "contains": lambda left, right: str(right).lower() in str(left or "").lower(),
}


@dataclass
class WorkflowEvaluation:
    matched: bool
    reasons: list[str]
    actions: list[dict[str, Any]]


def legacy_rule_to_dsl(rule: AutomationRule) -> dict[str, Any]:
    return {
        "trigger": {"type": rule.trigger_type, "value": rule.trigger_value},
        "conditions": [{"field": rule.trigger_type, "operator": "legacy", "value": rule.trigger_value}],
        "actions": [{"type": rule.action_type, "config": rule.action_config or {}}],
    }


def validate_workflow_definition(payload: dict[str, Any]) -> dict[str, Any]:
    trigger = payload.get("trigger") or {}
    conditions = payload.get("conditions") or []
    actions = payload.get("actions") or []
    errors: list[str] = []
    if not isinstance(trigger, dict) or not trigger.get("type"):
        errors.append("trigger.type is required")
    if not isinstance(conditions, list):
        errors.append("conditions must be a list")
    if not isinstance(actions, list) or not actions:
        errors.append("actions must be a non-empty list")
    for condition in conditions if isinstance(conditions, list) else []:
        if not isinstance(condition, dict):
            errors.append("each condition must be an object")
            continue
        if condition.get("operator") not in OPS and condition.get("operator") != "legacy":
            errors.append(f"unsupported operator: {condition.get('operator')}")
        if not condition.get("field"):
            errors.append("condition.field is required")
    for action in actions if isinstance(actions, list) else []:
        if not isinstance(action, dict) or not action.get("type"):
            errors.append("each action requires type")
    return {"valid": not errors, "errors": errors}


def _value_for_field(context: dict[str, Any], field: str):
    current: Any = context
    for part in field.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            current = getattr(current, part, None)
    return current


def _legacy_condition_matches(condition: dict[str, Any], context: dict[str, Any]) -> bool:
    field = condition.get("field")
    value = condition.get("value")
    if field == "category":
        return context.get("category") == value
    if field == "sentiment":
        return float(context.get("sentiment") or 0) < float(value)
    if field == "urgency":
        return float(context.get("urgency_score") or 0) > float(value)
    if field == "intent":
        return context.get("intent") == value
    return False


def evaluate_rule(rule: AutomationRule, context: dict[str, Any]) -> WorkflowEvaluation:
    definition = {
        "trigger": rule.trigger_definition,
        "conditions": rule.condition_definition,
        "actions": rule.action_definition,
    }
    if not definition["trigger"] and not definition["conditions"] and not definition["actions"]:
        definition = legacy_rule_to_dsl(rule)

    conditions = definition.get("conditions") or []
    actions = definition.get("actions") or []
    reasons: list[str] = []
    for condition in conditions:
        if condition.get("operator") == "legacy":
            matched = _legacy_condition_matches(condition, context)
        else:
            left = _value_for_field(context, condition.get("field", ""))
            right = condition.get("value")
            try:
                matched = bool(OPS[condition.get("operator", "==")](left, right))
            except Exception:
                matched = False
        reasons.append(f"{condition.get('field')} {condition.get('operator')} {condition.get('value')} => {matched}")
        if not matched:
            return WorkflowEvaluation(matched=False, reasons=reasons, actions=[])
    return WorkflowEvaluation(matched=True, reasons=reasons, actions=actions or [{"type": rule.action_type, "config": rule.action_config or {}}])


def context_from_complaint(complaint: Complaint, classification: dict[str, Any] | None = None) -> dict[str, Any]:
    classification = classification or {}
    return {
        "category": classification.get("category", complaint.category),
        "sentiment": classification.get("sentiment", complaint.sentiment),
        "urgency_score": classification.get("urgency_score", complaint.urgency_score),
        "intent": classification.get("intent", complaint.intent),
        "priority": classification.get("priority", complaint.priority),
        "status": complaint.status,
        "resolution_status": complaint.resolution_status,
        "customer_id": str(complaint.customer_id) if complaint.customer_id else None,
        "complaint": complaint,
    }
