from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.db.models import Client
from app.db.session import get_db
from app.services.analytics import (
    analytics_customers,
    analytics_overview,
    category_breakdown_over_time,
    complaint_category_breakdown,
    trend_detection,
)

router = APIRouter(prefix="/api/analytics", tags=["analytics-api"])


@router.get("/overview")
def analytics_overview_endpoint(x_api_key: str = Header(default="", alias="x-api-key"), db: Session = Depends(get_db)):
    client = db.query(Client).filter(Client.api_key == x_api_key).first()
    if not client:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return analytics_overview(db, client.id)


@router.get("/trends")
def analytics_trends_endpoint(days: int = 7, x_api_key: str = Header(default="", alias="x-api-key"), db: Session = Depends(get_db)):
    client = db.query(Client).filter(Client.api_key == x_api_key).first()
    if not client:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return trend_detection(db, client.id, days=days)


@router.get("/categories")
def analytics_categories_endpoint(days: int = 30, x_api_key: str = Header(default="", alias="x-api-key"), db: Session = Depends(get_db)):
    client = db.query(Client).filter(Client.api_key == x_api_key).first()
    if not client:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return {
        "current": complaint_category_breakdown(db, client.id),
        "timeline": category_breakdown_over_time(db, client.id, days=days),
    }


@router.get("/customers")
def analytics_customers_endpoint(x_api_key: str = Header(default="", alias="x-api-key"), db: Session = Depends(get_db)):
    client = db.query(Client).filter(Client.api_key == x_api_key).first()
    if not client:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return analytics_customers(db, client.id)
