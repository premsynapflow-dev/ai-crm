import os
import time
import uuid
from pathlib import Path

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
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.sessions import SessionMiddleware

from app.api.analytics import router as analytics_api_router
from app.api.billing import router as billing_api_router
from app.api.chatbot import router as chatbot_api_router
from app.api.invoices import router as invoices_router
from app.api.plans import router as plans_router
from app.api.public import router as public_api_router
from app.api.settings import router as settings_router
from app.api.session_auth import router as session_auth_router
from app.api.v1.auth import router as auth_v1_router
from app.api.v1.complaints import router as complaints_v1_router
from app.api.v1.me import router as me_router
from app.api.admin_prompts import router as admin_prompts_router
from app.billing.router import router as billing_router
from app.client_portal import router as client_portal_router
from app.config import get_settings
from app.dashboard import router as dashboard_router
from app.db.schema_guard import ensure_schema
from app.intake.webhook import router as webhook_router
from app.middleware.security import SecurityHeadersMiddleware
from app.middleware.rate_limiter import DatabaseRateLimitMiddleware
from app.middleware.audit import RequestAuditMiddleware
from app.monitoring.health import router as health_router
from app.monitoring.metrics import record_metric, router as metrics_router
from app.queue.worker import start_worker_thread
from app.utils.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)
try:
    settings = get_settings()
except RuntimeError as exc:
    logger.error("Configuration validation failed: %s", exc)
    raise

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(DatabaseRateLimitMiddleware)
app.add_middleware(RequestAuditMiddleware)

app.mount("/public", StaticFiles(directory="public"), name="public")


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


@app.middleware("http")
async def error_handling_middleware(request: Request, call_next):
    return await call_next(request)


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


@app.get("/")
def landing_page():
    frontend_index = Path("frontend/out/index.html")
    if frontend_index.exists():
        return FileResponse(frontend_index)
    return FileResponse(Path("app/public/index.html"))


@app.get("/widget.js")
def widget_js() -> RedirectResponse:
    return RedirectResponse(url="/public/widget.js")

@app.on_event("startup")
def on_startup() -> None:
    global worker_thread
    try:
        ensure_schema()
        logger.info("Database schema ensured.")
    except SQLAlchemyError as exc:
        logger.error("Database unavailable during startup. Error: %s", exc)

    if worker_thread is None:
        worker_thread = start_worker_thread(interval_seconds=30)


app.include_router(webhook_router)
app.include_router(dashboard_router)
app.include_router(client_portal_router)
app.include_router(billing_router)
app.include_router(billing_api_router)
app.include_router(chatbot_api_router)
app.include_router(analytics_api_router)
app.include_router(session_auth_router)
app.include_router(public_api_router)
app.include_router(auth_v1_router)
app.include_router(complaints_v1_router)
app.include_router(me_router)
app.include_router(plans_router)
app.include_router(invoices_router)
app.include_router(settings_router)
app.include_router(admin_prompts_router)
app.include_router(health_router)
app.include_router(metrics_router)

frontend_dir = Path("frontend/out")

if (frontend_dir / "_next").exists():
    app.mount("/_next", StaticFiles(directory=frontend_dir / "_next"), name="next-static")


if frontend_dir.exists():
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str):
        reserved_prefixes = {"api", "auth", "billing", "portal", "public", "webhook", "metrics", "docs", "redoc", "openapi.json"}
        first_segment = full_path.split("/", 1)[0]

        if first_segment in reserved_prefixes:
            return JSONResponse(status_code=404, content={"detail": "Not Found"})

        file_path = frontend_dir / full_path
        if file_path.is_file():
            return FileResponse(file_path)

        html_path = frontend_dir / f"{full_path}.html"
        if html_path.is_file():
            return FileResponse(html_path)

        index_path = frontend_dir / full_path / "index.html"
        if index_path.is_file():
            return FileResponse(index_path)

        return FileResponse(frontend_dir / "index.html")
