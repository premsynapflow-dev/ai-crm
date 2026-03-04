from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.sessions import SessionMiddleware

from app.client_portal import router as client_portal_router
from app.config import get_settings
from app.dashboard import router as dashboard_router
from app.db.models import Base
from app.db.session import engine
from app.intake.webhook import router as webhook_router
from app.utils.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)
settings = get_settings()

app = FastAPI(title="AI Complaint Intelligence API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.on_event("startup")
def on_startup() -> None:
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database schema ensured.")
    except SQLAlchemyError as exc:
        logger.error(
            "Database unavailable during startup. Server is running, but DB operations will fail until connectivity is restored. Error: %s",
            exc,
        )


app.include_router(webhook_router)
app.include_router(dashboard_router)
app.include_router(client_portal_router)
