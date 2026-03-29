from app.db.models import Complaint
from app.services.customer_history import _history_query


def get_customer_timeline(db, email, client_id=None):
    query = _history_query(db, email, client_id=client_id)
    if query is None:
        return []

    return query.order_by(Complaint.created_at.desc()).limit(20).all()
