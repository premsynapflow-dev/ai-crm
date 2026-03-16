import uuid


def generate_ticket_id():
    uid = uuid.uuid4().hex[:8].upper()

    return f"TKT-{uid}"


def generate_thread_id():
    uid = uuid.uuid4().hex[:10]

    return f"TH-{uid}"
