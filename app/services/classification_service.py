from __future__ import annotations

from copy import deepcopy
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Client, EscalationRule
from app.intelligence.prompt_builder import DEFAULT_CONFIG, get_prompt_config_for_client
from app.workflow.rule_engine import decide_action

_ACTION_MAP = {
    "escalate": "ESCALATE_HIGH",
    "notify_sales": "NOTIFY_SALES",
    "support_ticket": "AUTO_REPLY",
    "auto_reply": "AUTO_REPLY",
    "product_feedback": "PRODUCT_FEEDBACK",
}


def _merge_config(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge_config(base[key], value)
        else:
            base[key] = value
    return base


def _serialize_escalation_rule(rule: EscalationRule) -> dict[str, Any]:
    return {
        "name": rule.rule_name,
        "trigger_condition": rule.trigger_condition,
        "escalation_level": rule.escalation_level,
        "trigger_after_hours": rule.trigger_after_hours,
        "category_code": rule.category_code,
        "escalate_to": rule.escalate_to_email or rule.escalate_to_team,
    }


def build_client_classification_config(db: Session, client: Client | None) -> dict[str, Any]:
    config = deepcopy(DEFAULT_CONFIG)
    prompt_config = get_prompt_config_for_client(client) if client is not None else None
    if isinstance(prompt_config, dict):
        _merge_config(config, prompt_config)

    if client is None:
        config["escalation_rules"] = []
        return config

    escalation_rules = (
        db.query(EscalationRule)
        .filter(
            EscalationRule.client_id == client.id,
            EscalationRule.enabled == True,
        )
        .order_by(EscalationRule.escalation_level.asc(), EscalationRule.rule_name.asc())
        .all()
    )
    config["escalation_rules"] = [_serialize_escalation_rule(rule) for rule in escalation_rules]
    return config


def classification_to_action(classification: dict[str, Any]) -> str:
    recommended_action = str(classification.get("recommended_action") or "").strip()
    mapped_action = _ACTION_MAP.get(recommended_action)
    if mapped_action:
        return mapped_action

    return decide_action(
        category=str(classification.get("category") or "general"),
        sentiment=float(classification.get("sentiment") or 0.0),
        urgency=float(classification.get("urgency_score") or 0.3),
    )
