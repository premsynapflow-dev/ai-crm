from sqlalchemy import func, or_

from app.db.models import Complaint, Customer
from app.services.customer_deduplication import CustomerDeduplicator


def _matching_customer_ids(db, email, client_id=None):
    normalized_email = CustomerDeduplicator._normalize_email(email)
    if not normalized_email:
        return []

    query = db.query(Customer).filter(Customer.is_master == True)
    if client_id is not None:
        query = query.filter(Customer.client_id == client_id)

    matches = []
    for customer in query.all():
        if normalized_email in CustomerDeduplicator._emails_for(customer):
            matches.append(customer.id)
    return matches


def _history_query(db, email, client_id=None):
    normalized_email = CustomerDeduplicator._normalize_email(email)
    if not normalized_email:
        return None

    query = db.query(Complaint)
    if client_id is not None:
        query = query.filter(Complaint.client_id == client_id)

    filters = [func.lower(Complaint.customer_email) == normalized_email]
    customer_ids = _matching_customer_ids(db, normalized_email, client_id=client_id)
    if customer_ids:
        filters.append(Complaint.customer_id.in_(customer_ids))

    return query.filter(or_(*filters))


def get_customer_history(db, email, client_id=None):
    query = _history_query(db, email, client_id=client_id)
    if query is None:
        return []

    return query.order_by(Complaint.created_at.desc()).limit(20).all()


def get_customer_memory(db, email, limit=5, client_id=None):
    query = _history_query(db, email, client_id=client_id)
    if query is None:
        return []

    rows = (
        query.with_entities(Complaint.summary)
        .order_by(Complaint.created_at.desc())
        .limit(limit)
        .all()
    )
    return [row[0] for row in rows if row and row[0]]
