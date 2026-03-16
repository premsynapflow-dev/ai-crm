from app.db.models import AutomationRule


def get_matching_rules(db, client_id, classification):

    rules = db.query(AutomationRule).filter(
        AutomationRule.client_id == client_id,
        AutomationRule.enabled == True
    ).all()

    matches = []

    for rule in rules:

        if rule.trigger_type == "intent":
            if classification["intent"] == rule.trigger_value:
                matches.append(rule)

        elif rule.trigger_type == "category":
            if classification["category"] == rule.trigger_value:
                matches.append(rule)

        elif rule.trigger_type == "priority":
            if str(classification["priority"]) == rule.trigger_value:
                matches.append(rule)

    return matches
