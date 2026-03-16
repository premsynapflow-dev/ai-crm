def assign_team(category, intent):

    if intent == "sales_lead":
        return "sales"

    if category == "billing":
        return "finance"

    if category == "technical":
        return "engineering"

    return "support"
