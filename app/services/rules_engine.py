from typing import List, Dict
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from app.db.models import AutomationRule


def get_matching_rules(
    db: Session, 
    client_id: UUID, 
    classification: Dict
) -> List[AutomationRule]:
    """Get automation rules with eager loading to avoid N+1"""
    
    # Eager load client relationship
    rules = db.query(AutomationRule).options(
        joinedload(AutomationRule.client)
    ).filter(
        AutomationRule.client_id == client_id,
        AutomationRule.enabled == True
    ).all()
    
    # Filter rules based on classification
    matching_rules = []
    for rule in rules:
        if should_trigger_rule(rule, classification):
            matching_rules.append(rule)
    
    return matching_rules


def should_trigger_rule(rule: AutomationRule, classification: Dict) -> bool:
    """Check if rule should trigger based on classification"""
    trigger_type = rule.trigger_type
    trigger_value = rule.trigger_value
    
    if trigger_type == "category":
        return classification.get("category") == trigger_value
    elif trigger_type == "sentiment":
        threshold = float(trigger_value)
        return classification.get("sentiment", 0) < threshold
    elif trigger_type == "urgency":
        threshold = float(trigger_value)
        return classification.get("urgency_score", 0) > threshold
    elif trigger_type == "intent":
        return classification.get("intent") == trigger_value
    
    return False
