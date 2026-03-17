from app.db.models import Complaint


def get_customer_history(db, email):

    if not email:
        return []

    return (
        db.query(Complaint)
        .filter(Complaint.customer_email == email)
        .order_by(Complaint.created_at.desc())
        .limit(20)
        .all()
    )


def get_customer_memory(db, email, limit=5):
    if not email:
        return []

    rows = (
        db.query(Complaint.summary)
        .filter(Complaint.customer_email == email)
        .order_by(Complaint.created_at.desc())
        .limit(limit)
        .all()
    )
    return [row[0] for row in rows if row and row[0]]
