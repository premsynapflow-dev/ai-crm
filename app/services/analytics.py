from sqlalchemy import func

from app.db.models import Complaint


def complaint_category_breakdown(db, client_id):

    return (
        db.query(
            Complaint.category,
            func.count(Complaint.id)
        )
        .filter(Complaint.client_id == client_id)
        .group_by(Complaint.category)
        .all()
    )


def sentiment_distribution(db, client_id):

    return (
        db.query(
            Complaint.sentiment,
            func.count(Complaint.id)
        )
        .filter(Complaint.client_id == client_id)
        .group_by(Complaint.sentiment)
        .all()
    )


def urgency_distribution(db, client_id):

    return (
        db.query(
            Complaint.priority,
            func.count(Complaint.id)
        )
        .filter(Complaint.client_id == client_id)
        .group_by(Complaint.priority)
        .all()
    )


def top_complaint_sources(db, client_id):

    return (
        db.query(
            Complaint.source,
            func.count(Complaint.id)
        )
        .filter(Complaint.client_id == client_id)
        .group_by(Complaint.source)
        .all()
    )


def get_complaint_stats(db, client_id):
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
