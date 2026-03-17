import time
import uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
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
async def request_id_middleware(request: Request, call_next):
    request.state.request_id = str(uuid.uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    client_id = getattr(request.state, "client_id", None) or "-"
    logger.info(
        "request_id=%s path=%s method=%s client_id=%s status=%s latency_ms=%s",
        getattr(request.state, "request_id", "n/a"),
        request.url.path,
        request.method,
        client_id,
        response.status_code,
        duration_ms,
    )
    record_metric("request_duration_ms", duration_ms, {"path": request.url.path, "method": request.method})
    if response.status_code >= 400:
        record_metric("error_count", 1, {"path": request.url.path, "status": response.status_code})
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
    logger.error("Unhandled error %s", request_id, exc_info=exc)
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


@app.on_event("startup")
def on_startup() -> None:
    global worker_thread
    try:
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
