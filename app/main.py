import time
import uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.sessions import SessionMiddleware

from app.api.analytics import router as analytics_api_router
from app.api.chatbot import router as chatbot_api_router
from app.api.public import router as public_api_router
from app.api.v1.auth import router as auth_v1_router
from app.api.v1.complaints import router as complaints_v1_router
from app.billing.router import router as billing_router
from app.client_portal import router as client_portal_router
from app.config import get_settings
from app.dashboard import router as dashboard_router
from app.db.models import Base
from app.db.session import engine
from app.intake.webhook import router as webhook_router
from app.middleware.rate_limiter import DatabaseRateLimitMiddleware
from app.middleware.security import SecurityHeadersMiddleware
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
    return FileResponse(Path("app/public/index.html"))


@app.get("/widget.js")
def widget_js() -> RedirectResponse:
    return RedirectResponse(url="/public/widget.js")


def _ensure_required_columns() -> None:
    required_columns = {
        "complaints": {
            "first_response_at": "ALTER TABLE complaints ADD COLUMN IF NOT EXISTS first_response_at TIMESTAMP WITH TIME ZONE",
            "response_time_seconds": "ALTER TABLE complaints ADD COLUMN IF NOT EXISTS response_time_seconds INTEGER",
            "resolved_at": "ALTER TABLE complaints ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMP WITH TIME ZONE",
        },
        "job_queue": {
            "last_error": "ALTER TABLE job_queue ADD COLUMN IF NOT EXISTS last_error TEXT",
        },
    }

    with engine.begin() as conn:
        inspector = inspect(conn)
        tables = set(inspector.get_table_names())

        for table_name, columns in required_columns.items():
            if table_name not in tables:
                logger.warning("Schema safety: table '%s' does not exist yet; create_all() will create it.", table_name)
                continue

            existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
            missing_columns = [column_name for column_name in columns if column_name not in existing_columns]
            if missing_columns:
                logger.warning("Schema safety: table '%s' is missing columns %s", table_name, ", ".join(missing_columns))
                for column_name in missing_columns:
                    conn.execute(text(columns[column_name]))

        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_complaints_response_time
                ON complaints (response_time_seconds)
                """
            )
        )


@app.on_event("startup")
def on_startup() -> None:
    global worker_thread
    try:
        _ensure_required_columns()
        Base.metadata.create_all(bind=engine)
        logger.info("Database schema ensured.")
    except SQLAlchemyError as exc:
        logger.error("Database unavailable during startup. Error: %s", exc)

    if worker_thread is None:
        worker_thread = start_worker_thread(interval_seconds=30)


app.include_router(webhook_router)
app.include_router(dashboard_router)
app.include_router(client_portal_router)
app.include_router(billing_router)
app.include_router(chatbot_api_router)
app.include_router(analytics_api_router)
app.include_router(public_api_router)
app.include_router(auth_v1_router)
app.include_router(complaints_v1_router)
app.include_router(health_router)
app.include_router(metrics_router)
