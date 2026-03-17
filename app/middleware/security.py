import uuid

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.db.models import Client, RequestAudit
from app.db.session import SessionLocal


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > 2_000_000:
            return JSONResponse(status_code=413, content={"detail": "Request body too large"})

        response = await call_next(request)

        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        db = SessionLocal()
        try:
            api_key = request.headers.get("x-api-key", "").strip()
            client = None
            if api_key:
                client = db.query(Client).filter(Client.api_key == api_key).first()
            audit = RequestAudit(
                client_id=client.id if client else None,
                request_id=getattr(request.state, "request_id", str(uuid.uuid4())),
                path=request.url.path,
                method=request.method,
                ip_address=request.client.host if request.client else "unknown",
                user_agent=request.headers.get("user-agent"),
                status_code=response.status_code,
            )
            db.add(audit)
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

        return response
