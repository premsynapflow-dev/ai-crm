import asyncio
import concurrent.futures
import uuid
from starlette.middleware.base import BaseHTTPMiddleware

from app.db.models import RequestAudit
from app.db.session import SessionLocal
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Dedicated thread pool so audit writes never compete with the main executor
_audit_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="audit")

# Paths that don't need auditing — skip to save DB connections
_SKIP_PREFIXES = ("/_next/", "/public/", "/favicon.ico", "/health", "/metrics", "/static/")


def _should_skip_audit(path: str) -> bool:
    return path.startswith(_SKIP_PREFIXES)


def _parse_uuid(value):
    if value in (None, ""):
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


def _write_audit_sync(client_id, request_id, path, method, ip_address, user_agent, status_code):
    try:
        db = SessionLocal()
        audit = RequestAudit(
            client_id=client_id,
            request_id=request_id,
            path=path,
            method=method,
            ip_address=ip_address,
            user_agent=user_agent,
            status_code=status_code,
        )
        db.add(audit)
        db.commit()
        db.close()
    except Exception as exc:
        logger.warning("Audit logging failed: %s", exc)


class RequestAuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)

        if not _should_skip_audit(request.url.path):
            # Fire-and-forget: response is returned immediately, DB write happens in background thread
            asyncio.get_event_loop().run_in_executor(
                _audit_executor,
                _write_audit_sync,
                _parse_uuid(getattr(request.state, "client_id", None)),
                getattr(request.state, "request_id", str(uuid.uuid4())),
                request.url.path,
                request.method,
                request.client.host if request.client else "unknown",
                request.headers.get("user-agent"),
                response.status_code,
            )

        return response
