from app.billing.plans import PLANS


def apply_plan_to_client(client, plan_id: str):
    plan = PLANS.get(plan_id)
    if not client or not plan:
        return client

    client.plan_id = plan_id
    client.plan = plan_id
    client.monthly_ticket_limit = plan.get("tickets_per_month", client.monthly_ticket_limit)
    client.trial_ends_at = None
    return client
