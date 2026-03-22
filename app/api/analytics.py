"""
Analytics API endpoints.

SECURITY NOTE: All analytics queries MUST filter by client_id.
Never aggregate or return data across multiple clients.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session

from app.auth import resolve_current_client
from app.db.models import Client, Complaint
from app.db.session import get_db
from app.middleware.feature_gate import ensure_feature_access
from app.services.analytics import (
    analytics_customers,
    analytics_overview,
    category_breakdown_over_time,
    complaint_category_breakdown,
    sentiment_distribution,
    trend_detection,
)

router = APIRouter(prefix="/api/analytics", tags=["analytics-api"])


def _resolve_client(request: Request, db: Session, x_api_key: str) -> Client:
    if x_api_key:
        client = db.query(Client).filter(Client.api_key == x_api_key).first()
        if client:
            request.state.client_id = str(client.id)
            return client
    return resolve_current_client(request, db, required=True)


def _serialize_category_breakdown(db: Session, client_id):
    return [
        {"category": str(category or "unknown"), "count": int(count)}
        for category, count in complaint_category_breakdown(db, client_id)
    ]


def _serialize_sentiment_distribution(db: Session, client_id):
    buckets = {"positive": 0, "neutral": 0, "negative": 0}
    for raw_sentiment, count in sentiment_distribution(db, client_id):
        sentiment_value = float(raw_sentiment or 0)
        if sentiment_value > 0.2:
            buckets["positive"] += int(count)
        elif sentiment_value < -0.2:
            buckets["negative"] += int(count)
        else:
            buckets["neutral"] += int(count)
    return [{"sentiment": key, "count": value} for key, value in buckets.items()]


def _ticket_metrics(db: Session, client_id) -> dict[str, int]:
    total_leads = (
        db.query(Complaint)
        .filter(
            Complaint.client_id == client_id,
            Complaint.intent == "sales_lead",
        )
        .count()
    )
    open_tickets = (
        db.query(Complaint)
        .filter(
            Complaint.client_id == client_id,
            Complaint.resolution_status == "open",
        )
        .count()
    )
    resolved_tickets = (
        db.query(Complaint)
        .filter(
            Complaint.client_id == client_id,
            Complaint.resolution_status == "resolved",
        )
        .count()
    )
    return {
        "total_leads": total_leads,
        "open_tickets": open_tickets,
        "resolved_tickets": resolved_tickets,
    }


@router.get("/overview")
def analytics_overview_endpoint(
    request: Request,
    days: int = 30,
    x_api_key: str = Header(default="", alias="x-api-key"),
    db: Session = Depends(get_db),
):
    client = _resolve_client(request, db, x_api_key)
    overview = analytics_overview(db, client.id, days=max(1, min(days, 90)))
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    total = db.query(Complaint).filter(Complaint.client_id == client.id).count()
    resolved_today = (
        db.query(Complaint)
        .filter(
            Complaint.client_id == client.id,
            Complaint.resolution_status == "resolved",
            Complaint.resolved_at.isnot(None),
            Complaint.resolved_at >= today_start,
        )
        .count()
    )

    return {
        "total_complaints": total,
        "resolved_today": resolved_today,
        "avg_response_time": overview.get("response_time", {}).get("average_response_time_seconds", 0),
        "customer_satisfaction": overview.get("csat", {}).get("customer_satisfaction_score", 0),
        "category_breakdown": _serialize_category_breakdown(db, client.id),
        "sentiment_distribution": _serialize_sentiment_distribution(db, client.id),
        "days": days,
        **_ticket_metrics(db, client.id),
        **overview,
    }


@router.get("/trends")
def analytics_trends_endpoint(
    request: Request,
    days: int = 7,
    x_api_key: str = Header(default="", alias="x-api-key"),
    db: Session = Depends(get_db),
):
    client = _resolve_client(request, db, x_api_key)
    return trend_detection(db, client.id, days=days)


@router.get("/categories")
def analytics_categories_endpoint(
    request: Request,
    days: int = 30,
    x_api_key: str = Header(default="", alias="x-api-key"),
    db: Session = Depends(get_db),
):
    client = _resolve_client(request, db, x_api_key)
    return {
        "current": _serialize_category_breakdown(db, client.id),
        "timeline": category_breakdown_over_time(db, client.id, days=days),
    }


@router.get("/category-breakdown")
def analytics_category_breakdown_endpoint(
    request: Request,
    x_api_key: str = Header(default="", alias="x-api-key"),
    db: Session = Depends(get_db),
):
    client = _resolve_client(request, db, x_api_key)
    return _serialize_category_breakdown(db, client.id)


@router.get("/sentiment-distribution")
def analytics_sentiment_distribution_endpoint(
    request: Request,
    x_api_key: str = Header(default="", alias="x-api-key"),
    db: Session = Depends(get_db),
):
    client = _resolve_client(request, db, x_api_key)
    ensure_feature_access(client, "sentiment_analysis")
    from app.services.sentiment import get_sentiment_distribution

    return get_sentiment_distribution(db, client.id)


@router.get("/churn-risk")
def analytics_churn_risk_endpoint(
    request: Request,
    x_api_key: str = Header(default="", alias="x-api-key"),
    db: Session = Depends(get_db),
):
    client = _resolve_client(request, db, x_api_key)
    ensure_feature_access(client, "churn_risk_scoring")
    from app.services.churn_risk import get_high_risk_customers

    return get_high_risk_customers(db, client.id)


@router.get("/root-cause-analysis")
def analytics_root_cause_endpoint(
    request: Request,
    period_days: int = 30,
    x_api_key: str = Header(default="", alias="x-api-key"),
    db: Session = Depends(get_db),
):
    client = _resolve_client(request, db, x_api_key)
    ensure_feature_access(client, "root_cause_analysis")
    from app.services.root_cause import generate_root_cause_report

    return generate_root_cause_report(db, client.id, period_days=max(7, min(period_days, 180)))


@router.get("/team-performance")
def analytics_team_performance_endpoint(
    request: Request,
    period_days: int = 30,
    x_api_key: str = Header(default="", alias="x-api-key"),
    db: Session = Depends(get_db),
):
    client = _resolve_client(request, db, x_api_key)
    ensure_feature_access(client, "team_performance")
    from app.services.team_performance import get_team_performance

    return get_team_performance(db, client.id, period_days=max(7, min(period_days, 180)))


@router.get("/customers")
def analytics_customers_endpoint(
    request: Request,
    x_api_key: str = Header(default="", alias="x-api-key"),
    db: Session = Depends(get_db),
):
    client = _resolve_client(request, db, x_api_key)
    return analytics_customers(db, client.id)
