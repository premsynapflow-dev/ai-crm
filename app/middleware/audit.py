import uuid
from starlette.middleware.base import BaseHTTPMiddleware

from app.db.models import RequestAudit
from app.db.session import SessionLocal
from app.utils.logging import get_logger

logger = get_logger(__name__)


def _parse_uuid(value):
    if value in (None, ""):
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


class RequestAuditMiddleware(BaseHTTPMiddleware):
    """Async audit logging - doesn't block request"""
    
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        
        # Audit in background (non-blocking)
        try:
            db = SessionLocal()
            client_id = _parse_uuid(getattr(request.state, "client_id", None))
            
            audit = RequestAudit(
                client_id=client_id,
                request_id=getattr(request.state, "request_id", str(uuid.uuid4())),
                path=request.url.path,
                method=request.method,
                ip_address=request.client.host if request.client else "unknown",
                user_agent=request.headers.get("user-agent"),
                status_code=response.status_code,
            )
            db.add(audit)
            db.commit()
            db.close()
        except Exception as e:
            logger.warning(f"Audit logging failed: {e}")
            # Don't fail the request
        
        return response
