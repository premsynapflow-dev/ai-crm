from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.db.models import Complaint, Customer
from app.intelligence.constants import RISK_HIGH_THRESHOLD, RISK_LEVEL_HIGH, RISK_LEVEL_MEDIUM
from app.services.customer_deduplication import CustomerDeduplicator
from app.services.customer_profile import CustomerProfileService


def calculate_churn_risk(db: Session, customer_email: str, client_id: str) -> dict:
    """
    Calculate churn risk for a customer from their profile or recent complaint activity.

    Uses CustomerProfileService._weighted_churn_score as the single scoring path.
    The legacy fallback formula (complaint_count * 15) has been removed — it used
    a different sentiment scale (1–5) and different weight multipliers, producing
    inconsistent scores vs. the main engine.
    """
    normalized_email = CustomerDeduplicator._normalize_email(customer_email)
    profile = _find_customer_profile(db, normalized_email, client_id)

    if profile:
        service = CustomerProfileService(db)
        service.refresh_customer_metrics(profile, commit=False)
        churn = service.compute_churn_risk(profile)
        indicators = churn["signals"]
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
        risk_score = int(round(churn["score"]))
        risk_level = _score_to_level(risk_score)
        return {
            "risk_score": risk_score,
            "risk_level": risk_level,
            "complaint_count": profile.total_tickets,
            "unresolved_count": unresolved_count,
            "avg_sentiment": None,
            "recommendation": get_churn_recommendation(risk_level),
            "signals": indicators,
            "explanation": churn.get("explanation", []),
        }

    # No profile found — insufficient data to score
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
    unresolved_count = len([c for c in recent_complaints if c.resolution_status != "resolved"])

    # Minimal fallback: only complaint count + unresolved (no fabricated revenue or probabilities)
    # Capped at 40 to avoid falsely inflating risk without a full profile
    raw = min(complaint_count * 8, 24) + min(unresolved_count * 8, 16)
    risk_score = int(round(min(40.0, raw)))
    risk_level = _score_to_level(risk_score)

    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "complaint_count": complaint_count,
        "unresolved_count": unresolved_count,
        "avg_sentiment": None,
        "recommendation": get_churn_recommendation(risk_level),
        "note": "Limited data — full scoring requires a customer profile",
    }


def _score_to_level(score: int) -> str:
    if score >= RISK_LEVEL_HIGH:
        return "high"
    if score >= RISK_LEVEL_MEDIUM:
        return "medium"
    if score > 0:
        return "low"
    return "none"


def get_churn_recommendation(risk_level: str) -> str:
    recommendations = {
        "high": "Priority follow-up needed. Review unresolved complaints and reach out proactively.",
        "medium": "Monitor closely. Keep response times low and follow up on open issues.",
        "low": "Standard support process is sufficient. Maintain good response times.",
        "none": "No recent activity. No action required.",
    }
    return recommendations.get(risk_level, "")


def get_high_risk_customers(db: Session, client_id: str) -> list[dict]:
    """Return customers with high churn risk."""
    profiles = db.query(Customer).filter(Customer.client_id == client_id, Customer.is_master == True).all()
    if profiles:
        service = CustomerProfileService(db)
        high_risk_profiles: list[dict] = []
        for profile in profiles:
            service.refresh_customer_metrics(profile, commit=False)
            risk_score = int(round(profile.churn_risk_score or 0))
            risk_level = _score_to_level(risk_score)
            if risk_level == "high":
                churn = service.compute_churn_risk(profile)
                high_risk_profiles.append(
                    {
                        "customer_email": profile.primary_email,
                        "customer_id": str(profile.id),
                        "risk_score": risk_score,
                        "risk_level": risk_level,
                        "recommendation": get_churn_recommendation(risk_level),
                        "signals": churn.get("signals", {}),
                        "explanation": churn.get("explanation", []),
                    }
                )
        return sorted(high_risk_profiles, key=lambda item: item["risk_score"], reverse=True)

    # No profiles — fall back to email-level scoring
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
        if risk["risk_level"] == "high":
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
