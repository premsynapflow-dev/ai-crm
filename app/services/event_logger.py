from app.db.models import EventLog


def log_event(db, client_id, event_type: str, payload: dict | None = None):
    event = EventLog(
        client_id=client_id,
        event_type=event_type,
        payload=payload or {},
    )
    db.add(event)
    db.flush()
    return event
