from fastapi import FastAPI
from sqlalchemy.exc import SQLAlchemyError

from app.db.models import Base
from app.db.session import engine
from app.intake.webhook import router as webhook_router
from app.utils.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)

app = FastAPI(title="AI Complaint Intelligence API", version="1.0.0")

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
