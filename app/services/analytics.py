from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import Complaint


def get_complaint_stats(db: Session, client_id):
    total = db.query(func.count(Complaint.id)).filter(
        Complaint.client_id == client_id
    ).scalar()

    leads = db.query(func.count(Complaint.id)).filter(
        Complaint.client_id == client_id,
        Complaint.intent == "sales_lead"
    ).scalar()

    complaints = db.query(func.count(Complaint.id)).filter(
        Complaint.client_id == client_id,
        Complaint.intent == "complaint"
    ).scalar()

    return {
        "total_messages": total,
        "sales_leads": leads,
        "complaints": complaints
    }
