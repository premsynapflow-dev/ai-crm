from datetime import datetime

from fastapi import APIRouter
from sqlalchemy import text

from app.config import get_settings
from app.db.session import SessionLocal

router = APIRouter(tags=["health"])
settings = get_settings()


@router.get("/health")
def health():
    return {"status": "ok", "environment": settings.environment}


@router.get("/health/db")
def health_db():
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok"}
    finally:
        db.close()


@router.get("/health/ai")
def health_ai():
    return {
        "status": "ok" if settings.gemini_api_key else "degraded",
        "configured": bool(settings.gemini_api_key),
        "checked_at": datetime.utcnow().isoformat(),
    }
