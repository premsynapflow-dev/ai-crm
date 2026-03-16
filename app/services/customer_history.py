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
