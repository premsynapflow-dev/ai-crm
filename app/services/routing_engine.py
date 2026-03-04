def classify_intent(message: str):
    msg = message.lower()

    if "refund" in msg or "money back" in msg:
        return "refund_request", "escalate", 0.9, 4

    if "where is my order" in msg or "order status" in msg:
        return "order_status", "auto_reply", 0.8, 2

    if "pricing" in msg or "bulk" in msg or "enterprise" in msg:
        return "sales_lead", "notify_sales", 0.8, 3

    if "feature" in msg or "add support" in msg:
        return "feature_request", "product_feedback", 0.7, 2

    if "help" in msg or "support" in msg:
        return "support", "support_ticket", 0.7, 2

    return "complaint", "support_ticket", 0.5, 3
