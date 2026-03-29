from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.db.models import Complaint, Customer
from app.services.customer_deduplication import CustomerDeduplicator
from app.services.customer_profile import CustomerProfileService


def calculate_churn_risk(db: Session, customer_email: str, client_id: str) -> dict:
    """
    Calculate churn risk for a customer from recent complaint activity.
    """
    normalized_email = CustomerDeduplicator._normalize_email(customer_email)
    profile = _find_customer_profile(db, normalized_email, client_id)
    if profile:
        CustomerProfileService(db).refresh_customer_metrics(profile, commit=False)
        indicators = CustomerProfileService(db)._calculate_churn_indicators(profile)
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
        unresolved_count = (
            db.query(Complaint)
            .filter(
                Complaint.customer_id == profile.id,
                Complaint.created_at >= thirty_days_ago,
                Complaint.resolution_status != "resolved",
            )
            .count()
        )
        risk_score = int(round(profile.churn_risk_score or 0))
        if risk_score >= 75:
            risk_level = "critical"
        elif risk_score >= 50:
            risk_level = "high"
        elif risk_score >= 25:
            risk_level = "medium"
        else:
            risk_level = "low"
        return {
            "risk_score": risk_score,
            "risk_level": risk_level,
            "complaint_count": profile.total_tickets,
            "unresolved_count": unresolved_count,
            "avg_sentiment": None,
            "recommendation": get_churn_recommendation(risk_level),
        }

    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    recent_complaints = (
        db.query(Complaint)
        .filter(
            Complaint.client_id == client_id,
            Complaint.customer_email == normalized_email,
            Complaint.created_at >= thirty_days_ago,
        )
        .all()
    )

    if not recent_complaints:
        return {"risk_score": 0, "risk_level": "none", "reason": "No recent complaints"}

    complaint_count = len(recent_complaints)
    unresolved_count = len([item for item in recent_complaints if item.resolution_status != "resolved"])
    avg_sentiment = sum([(item.sentiment_score or 3) for item in recent_complaints]) / complaint_count

    risk_score = 0.0
    risk_score += min(complaint_count * 15, 45)
    risk_score += min(unresolved_count * 10, 30)
    risk_score += min((avg_sentiment - 1) * 6.25, 25)

    if risk_score >= 75:
        risk_level = "critical"
    elif risk_score >= 50:
        risk_level = "high"
    elif risk_score >= 25:
        risk_level = "medium"
    else:
        risk_level = "low"

    return {
        "risk_score": int(round(risk_score)),
        "risk_level": risk_level,
        "complaint_count": complaint_count,
        "unresolved_count": unresolved_count,
        "avg_sentiment": round(avg_sentiment, 2),
        "recommendation": get_churn_recommendation(risk_level),
    }


def get_churn_recommendation(risk_level: str) -> str:
    recommendations = {
        "critical": "Immediate action required. Assign a senior support agent and consider compensation.",
        "high": "Priority follow-up needed. Review unresolved complaints and reach out proactively.",
        "medium": "Monitor closely. Keep response times low and follow up on open issues.",
        "low": "Standard support process is sufficient. Maintain good response times.",
    }
    return recommendations.get(risk_level, "")


def get_high_risk_customers(db: Session, client_id: str) -> list[dict]:
    """Return recent customers with high or critical churn risk."""
    profiles = db.query(Customer).filter(Customer.client_id == client_id, Customer.is_master == True).all()
    if profiles:
        service = CustomerProfileService(db)
        high_risk_profiles: list[dict] = []
        for profile in profiles:
            service.refresh_customer_metrics(profile, commit=False)
            risk_score = int(round(profile.churn_risk_score or 0))
            risk_level = "critical" if risk_score >= 75 else "high" if risk_score >= 50 else "medium" if risk_score >= 25 else "low"
            if risk_level in {"high", "critical"}:
                high_risk_profiles.append(
                    {
                        "customer_email": profile.primary_email,
                        "customer_id": str(profile.id),
                        "risk_score": risk_score,
                        "risk_level": risk_level,
                        "recommendation": get_churn_recommendation(risk_level),
                    }
                )
        return sorted(high_risk_profiles, key=lambda item: item["risk_score"], reverse=True)

    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    customers = (
        db.query(Complaint.customer_email)
        .filter(
            Complaint.client_id == client_id,
            Complaint.created_at >= thirty_days_ago,
            Complaint.customer_email.isnot(None),
        )
        .distinct()
        .all()
    )

    high_risk_customers: list[dict] = []
    for (email,) in customers:
        if not email:
            continue
        risk = calculate_churn_risk(db, email, client_id)
        if risk["risk_level"] in {"high", "critical"}:
            high_risk_customers.append({"customer_email": email, **risk})

    return sorted(high_risk_customers, key=lambda item: item["risk_score"], reverse=True)


def _find_customer_profile(db: Session, normalized_email: str, client_id: str) -> Customer | None:
    if not normalized_email:
        return None

    direct = (
        db.query(Customer)
        .filter(
            Customer.client_id == client_id,
            Customer.is_master == True,
            Customer.primary_email == normalized_email,
        )
        .first()
    )
    if direct:
        return direct

    for customer in db.query(Customer).filter(Customer.client_id == client_id, Customer.is_master == True).all():
        if normalized_email in CustomerDeduplicator._emails_for(customer):
            return customer
    return None
