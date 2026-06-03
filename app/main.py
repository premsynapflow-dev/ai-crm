import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

try:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    _HAS_SENTRY = True
except ImportError:
    _HAS_SENTRY = False

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.api.analytics import router as analytics_api_router
from app.api.admin.overview import router as admin_overview_router
from app.api.billing import router as billing_api_router
from app.api.chatbot import router as chatbot_api_router
from app.api.invoices import router as invoices_router
from app.api.plans import router as plans_router
from app.api.public import router as public_api_router
from app.api.settings import router as settings_router
from app.api.session_auth import router as session_auth_router
from app.api.v1.auth import router as auth_v1_router
from app.api.v1.complaints import router as complaints_v1_router
from app.api.v1.compliance_escalation import router as compliance_escalation_router
from app.api.v1.customers import router as customers_v1_router
from app.api.v1.dashboard_assignments import router as dashboard_assignments_router
from app.api.v1.feedback import router as feedback_v1_router
from app.api.v1.knowledge import router as knowledge_v1_router
from app.api.v1.me import router as me_router
from app.api.v1.model_audit import router as model_audit_v1_router
from app.api.v1.notifications import router as notifications_v1_router
from app.api.v1.queue_health import router as queue_health_v1_router
from app.api.v1.rbi_compliance import router as rbi_compliance_v1_router
from app.api.v1.reply_queue import router as reply_queue_v1_router
from app.api.v1.security_test import router as security_test_router
from app.api.v1.teams import router as teams_v1_router
from app.api.v1.tickets import router as tickets_v1_router
from app.api.v1.workflows import router as workflows_v1_router
from app.api.v1.channel_connections import router as channel_connections_v1_router
from app.api.v1.prompts import router as prompts_v1_router
from app.api.admin_prompts import router as admin_prompts_router
from app.api.v1.bulk_import import router as bulk_import_v1_router
from app.api.v1.entities import router as entities_v1_router
from app.api.v1.widget import router as widget_router
from app.api.v1.executive_summary import router as executive_summary_router
from app.api.v1.revenue_risk import router as revenue_risk_router
from app.api.v1.clusters import router as clusters_router
from app.api.v1.copilot import router as copilot_router
from app.api.v1.forecasting import router as forecasting_router
from app.api.v1.approvals import router as approvals_router
from app.api.v1.outcomes import router as outcomes_router
from app.billing.router import router as billing_router
from app.client_portal import router as client_portal_router
from app.config import get_settings
from app.dashboard import router as dashboard_router
from app.db.schema_guard import ensure_schema
from app.db.session import SessionLocal
from app.integrations.email import router as email_integration_router
from app.integrations.gmail import router as gmail_integration_router
from app.integrations.whatsapp import router as whatsapp_integration_router
from app.integrations.voice import router as voice_integration_router
from app.inboxes.router import router as inboxes_router
from app.intake.webhook import router as webhook_router
from app.middleware.security import SecurityHeadersMiddleware
from app.middleware.rls_context import RLSContextMiddleware
from app.middleware.rate_limiter import DatabaseRateLimitMiddleware
from app.middleware.audit import RequestAuditMiddleware
from app.middleware.feature_gate import FeatureGateMiddleware
from app.monitoring.health import router as health_router
from app.monitoring.metrics import record_metric, router as metrics_router
from app.queue.worker import start_worker_thread
from app.security_check import run_all_security_checks
from app.utils.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)
try:
    settings = get_settings()
except RuntimeError as exc:
    logger.error("Configuration validation failed: %s", exc)
    raise

logger.info("Running security verification checks...")
security_status = run_all_security_checks()
if not security_status:
    logger.warning("SECURITY: Some security checks failed. Review the logs above.")

# Initialize Sentry (optional)
if _HAS_SENTRY and settings.environment != "dev":
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN", ""),
        environment=settings.environment,
        traces_sample_rate=0.1,  # 10% of transactions
        profiles_sample_rate=0.1,
        integrations=[
            FastApiIntegration(),
            SqlalchemyIntegration(),
        ],
        before_send=lambda event, hint: event,  # Can filter events here
    )

worker_thread = None

app = FastAPI(title="AI Complaint Intelligence API", version="2.0.0")


@app.get("/health")
async def health_check():
    """
    Health check endpoint for Railway monitoring.
    Returns database connection status.
    """
    db = None
    timestamp = datetime.utcnow().isoformat()

    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": timestamp,
        }
    except Exception as exc:
        logger.error("Health check failed: %s", exc)
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "database": "disconnected",
                "error": str(exc),
                "timestamp": timestamp,
            },
        )
    finally:
        if db is not None:
            db.close()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=512)
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)
app.add_middleware(RLSContextMiddleware)
app.add_middleware(FeatureGateMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(DatabaseRateLimitMiddleware)
app.add_middleware(RequestAuditMiddleware)

# Ensure the public directory exists to prevent RuntimeError on mount
os.makedirs("public", exist_ok=True)
app.mount("/public", StaticFiles(directory="public"), name="public")



_SKIP_LOGGING_PREFIXES = ("/_next/", "/public/", "/favicon.ico", "/static/", "/assets/")


@app.middleware("http")
async def request_logging(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("Request failed [%s]", request_id)
        raise

    duration_ms = round((time.perf_counter() - started) * 1000, 2)

    # Skip metric recording and verbose logging for static asset requests
    if not request.url.path.startswith(_SKIP_LOGGING_PREFIXES):
        client_id = getattr(request.state, "client_id", None) or "-"
        logger.info(
            {
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "client_id": client_id,
                "status": response.status_code,
                "latency_ms": duration_ms,
            }
        )
        record_metric("request_duration_ms", duration_ms, {"path": request.url.path, "method": request.method})
        if response.status_code >= 400:
            record_metric("error_count", 1, {"path": request.url.path, "status": response.status_code})

    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": "Invalid request data",
            "details": exc.errors(),
            "request_id": getattr(request.state, "request_id", "n/a"),
        },
    )


@app.exception_handler(Exception)
async def internal_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    logger.exception(
        "Unhandled request error [%s]",
        request_id,
        exc_info=exc,
    )
    record_metric("error_count", 1, {"path": request.url.path, "status": 500})
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "request_id": request_id,
        },
    )


@app.api_route("/", methods=["GET", "HEAD"])
def landing_page():
    frontend_index = Path("frontend/out/index.html")
    if frontend_index.exists():
        return FileResponse(frontend_index)
    return FileResponse(Path("app/public/index.html"))


@app.on_event("startup")
def on_startup() -> None:
    global worker_thread
    disable_schema_guard = os.getenv("DISABLE_SCHEMA_GUARD", "").strip().lower() in {"1", "true", "yes"}
    if not disable_schema_guard:
        try:
            ensure_schema()
            logger.info("Database schema ensured.")
        except SQLAlchemyError as exc:
            logger.error("Database unavailable during startup. Error: %s", exc)

    disable_workers = os.getenv("DISABLE_BACKGROUND_WORKERS", "").strip().lower() in {"1", "true", "yes"}
    if worker_thread is None and not disable_workers:
        worker_thread = start_worker_thread(interval_seconds=30)


app.include_router(webhook_router)
app.include_router(email_integration_router)
app.include_router(gmail_integration_router)
app.include_router(whatsapp_integration_router)
app.include_router(voice_integration_router)
app.include_router(inboxes_router)
app.include_router(dashboard_router)
app.include_router(client_portal_router)
app.include_router(billing_router)
app.include_router(billing_api_router)
app.include_router(chatbot_api_router)
app.include_router(analytics_api_router)
app.include_router(admin_overview_router, prefix="/api")
app.include_router(session_auth_router)
app.include_router(public_api_router)
app.include_router(auth_v1_router)
app.include_router(complaints_v1_router)
app.include_router(compliance_escalation_router)
app.include_router(customers_v1_router)
app.include_router(dashboard_assignments_router)
app.include_router(feedback_v1_router)
app.include_router(knowledge_v1_router)
app.include_router(me_router)
app.include_router(model_audit_v1_router)
app.include_router(notifications_v1_router)
app.include_router(queue_health_v1_router)
app.include_router(reply_queue_v1_router)
app.include_router(rbi_compliance_v1_router)
app.include_router(security_test_router)
app.include_router(teams_v1_router)
app.include_router(tickets_v1_router)
app.include_router(workflows_v1_router)
app.include_router(channel_connections_v1_router)
app.include_router(prompts_v1_router)
app.include_router(plans_router)
app.include_router(invoices_router)
app.include_router(settings_router)
app.include_router(admin_prompts_router)
app.include_router(health_router)
app.include_router(metrics_router)
app.include_router(bulk_import_v1_router)
app.include_router(entities_v1_router)
app.include_router(widget_router)
app.include_router(executive_summary_router)
app.include_router(revenue_risk_router)
app.include_router(clusters_router)
app.include_router(copilot_router)
app.include_router(forecasting_router)
app.include_router(approvals_router)
app.include_router(outcomes_router)

frontend_dir = Path("frontend/out")

_IMMUTABLE_CACHE = {"Cache-Control": "public, max-age=31536000, immutable"}
_SHORT_CACHE = {"Cache-Control": "public, max-age=3600"}
_NO_CACHE = {"Cache-Control": "no-cache, no-store, must-revalidate"}


def _static_cache_headers(path: Path) -> dict[str, str]:
    suffix = path.suffix.lower()
    if suffix in {".js", ".css", ".woff", ".woff2", ".ttf", ".otf", ".eot"}:
        return _IMMUTABLE_CACHE
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".ico"}:
        return _SHORT_CACHE
    return _NO_CACHE


if (frontend_dir / "_next").exists():
    @app.api_route("/_next/{file_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    async def serve_next_static(file_path: str):
        full_path = frontend_dir / "_next" / file_path
        if not full_path.is_file():
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
        return FileResponse(full_path, headers=_IMMUTABLE_CACHE)


_LEGACY_PATH_REDIRECTS = {
    "dashboard": "/app/dashboard",
    "complaints": "/app/complaints",
    "analytics": "/app/analytics",
    "settings": "/app/settings",
    "workflows": "/app/settings/automations",
    "usage": "/app/billing",
    "pricing": "/app/billing",
    "inbox": "/app/complaints",
}

if frontend_dir.exists():
    @app.api_route("/customers/{customer_id}", methods=["GET", "HEAD"], include_in_schema=False)
    async def redirect_legacy_customer_route(customer_id: str):
        return RedirectResponse(url=f"/customer/?id={quote(customer_id, safe='')}", status_code=307)

    @app.api_route("/{full_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    async def serve_frontend(full_path: str):
        reserved_prefixes = {"api", "auth", "billing", "portal", "public", "webhook", "webhooks", "integrations", "inboxes", "health", "admin", "metrics", "docs", "redoc", "openapi.json"}
        first_segment = full_path.split("/", 1)[0]

        if first_segment in reserved_prefixes:
            return JSONResponse(status_code=404, content={"detail": "Not Found"})

        # Redirect legacy Next.js-era paths to new SPA paths
        bare_path = full_path.split("?")[0].strip("/")
        if bare_path in _LEGACY_PATH_REDIRECTS:
            return RedirectResponse(url=_LEGACY_PATH_REDIRECTS[bare_path], status_code=302)

        file_path = frontend_dir / full_path
        if file_path.is_file():
            return FileResponse(file_path, headers=_static_cache_headers(file_path))

        html_path = frontend_dir / f"{full_path}.html"
        if html_path.is_file():
            return FileResponse(html_path, headers=_NO_CACHE)

        index_path = frontend_dir / full_path / "index.html"
        if index_path.is_file():
            return FileResponse(index_path, headers=_NO_CACHE)

        return FileResponse(frontend_dir / "index.html", headers=_NO_CACHE)
