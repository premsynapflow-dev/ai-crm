from datetime import datetime, timedelta, timezone

try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address
except ImportError:  # pragma: no cover
    Limiter = None

    def get_remote_address(request):
        return request.client.host if request.client else "unknown"

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.db.models import RequestAudit
from app.db.session import SessionLocal

limiter = Limiter(key_func=get_remote_address) if Limiter else None


class DatabaseRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.rules = {
            "/webhook/complaint": 100,
            "/dashboard": 20,
            "/portal": 20,
        }

    async def dispatch(self, request, call_next):
        matching_prefix = None
        for prefix in self.rules:
            if request.url.path.startswith(prefix):
                matching_prefix = prefix
                break

        if matching_prefix:
            db = SessionLocal()
            try:
                cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
                ip_address = request.client.host if request.client else "unknown"
                recent_count = (
                    db.query(RequestAudit)
                    .filter(
                        RequestAudit.ip_address == ip_address,
                        RequestAudit.path.like(f"{matching_prefix}%"),
                        RequestAudit.created_at >= cutoff,
                    )
                    .count()
                )
                if recent_count >= self.rules[matching_prefix]:
                    return JSONResponse(
                        status_code=429,
                        content={"detail": "Rate limit exceeded. Please try again later."},
                    )
            finally:
                db.close()

        return await call_next(request)
