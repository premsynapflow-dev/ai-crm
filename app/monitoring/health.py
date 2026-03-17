from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Response
from sqlalchemy import text

from app.db.session import SessionLocal, engine
from app.db.models import JobQueue
from app.queue.worker import is_worker_alive
from app.utils.logging import get_logger
import httpx
import os

router = APIRouter(tags=["health"])
logger = get_logger(__name__)


@router.get("/health")
def health_check():
    """Basic health check"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@router.get("/health/db")
def database_health():
    """Database connectivity check"""
    db = SessionLocal()
    try:
        # Test query
        result = db.execute(text("SELECT 1")).scalar()
        
        # Check pool stats
        pool = engine.pool
        pool_stats = {
            "size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
        }
        
        return {
            "status": "healthy",
            "connected": result == 1,
            "pool_stats": pool_stats
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return Response(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)}
        )
    finally:
        db.close()


@router.get("/health/ai")
async def ai_service_health():
    """Check Gemini API connectivity"""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return {"status": "unconfigured", "message": "No API key set"}
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent",
                params={"key": api_key},
                json={
                    "contents": [{"parts": [{"text": "test"}]}],
                    "generationConfig": {"temperature": 0, "maxOutputTokens": 10},
                }
            )
            response.raise_for_status()
            return {"status": "healthy", "latency_ms": response.elapsed.total_seconds() * 1000}
    except Exception as e:
        logger.error(f"AI health check failed: {e}")
        return Response(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)}
        )


@router.get("/health/worker")
def worker_health():
    """Background worker health check"""
    db = SessionLocal()
    try:
        alive = is_worker_alive()
        
        # Check queue depth
        pending = db.query(JobQueue).filter(
            JobQueue.status == 'queued'
        ).count()
        
        # Check stuck jobs (queued >1 hour)
        stuck = db.query(JobQueue).filter(
            JobQueue.status == 'queued',
            JobQueue.created_at < datetime.now(timezone.utc) - timedelta(hours=1)
        ).count()
        
        # Check failed jobs in last hour
        recent_failures = db.query(JobQueue).filter(
            JobQueue.status == 'failed',
            JobQueue.processed_at >= datetime.now(timezone.utc) - timedelta(hours=1)
        ).count()
        
        healthy = alive and stuck == 0 and pending < 1000
        
        response_data = {
            "status": "healthy" if healthy else "degraded",
            "worker_alive": alive,
            "pending_jobs": pending,
            "stuck_jobs": stuck,
            "recent_failures": recent_failures,
        }
        
        if not healthy:
            return Response(status_code=503, content=response_data)
        
        return response_data
    finally:
        db.close()


@router.get("/health/full")
async def full_health_check():
    """Comprehensive health check"""
    checks = {
        "api": {"status": "healthy"},
        "database": None,
        "ai_service": None,
        "worker": None,
    }
    
    # Database check
    try:
        db_health = database_health()
        checks["database"] = db_health
    except:
        checks["database"] = {"status": "unhealthy"}
    
    # AI check
    try:
        ai_health = await ai_service_health()
        checks["ai_service"] = ai_health
    except:
        checks["ai_service"] = {"status": "unhealthy"}
    
    # Worker check
    try:
        worker_health_data = worker_health()
        checks["worker"] = worker_health_data
    except:
        checks["worker"] = {"status": "unhealthy"}
    
    # Overall status
    all_healthy = all(
        check.get("status") in ["healthy", "unconfigured"]
        for check in checks.values()
        if check
    )
    
    checks["overall"] = "healthy" if all_healthy else "degraded"
    
    if not all_healthy:
        return Response(status_code=503, content=checks)
    
    return checks
