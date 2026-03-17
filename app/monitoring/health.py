from datetime import datetime

from fastapi import APIRouter
from sqlalchemy import text

from app.config import get_settings
from app.db.session import SessionLocal
from app.queue.worker import is_worker_alive

router = APIRouter(tags=["health"])
settings = get_settings()


@router.get("/health")
def health():
    db_ok = False
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    finally:
        db.close()

    ai_ok = bool(settings.gemini_api_key)
    worker_ok = is_worker_alive()
    status = "healthy" if db_ok and worker_ok else "degraded"
    return {
        "status": status,
        "database": db_ok,
        "gemini_configured": ai_ok,
        "worker_alive": worker_ok,
        "environment": settings.environment,
    }


@router.get("/health/db")
def health_db():
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}
    finally:
        db.close()


@router.get("/health/ai")
def health_ai():
    return {
        "status": "ok" if settings.gemini_api_key else "degraded",
        "configured": bool(settings.gemini_api_key),
        "checked_at": datetime.utcnow().isoformat(),
    }
