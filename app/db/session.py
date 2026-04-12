import os
from contextvars import ContextVar
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

settings = get_settings()
_current_client_id: ContextVar[str | None] = ContextVar("current_client_id", default=None)

db_url = os.getenv("DATABASE_URL")
if not db_url:
    # Try pydantic settings as fallback just in case
    db_url = getattr(settings, "database_url", None)
    if not db_url:
        raise RuntimeError("DATABASE_URL is not set")

print("Using DATABASE_URL:", db_url[:30], "...")

engine = create_engine(
    db_url,
    connect_args={"sslmode": "require"} if "postgresql" in db_url else {},
    poolclass=NullPool,
    pool_pre_ping=True,
    echo=False,
    future=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=Session)


def set_current_client_context(client_id: str | None):
    return _current_client_id.set(str(client_id) if client_id else None)


def reset_current_client_context(token) -> None:
    _current_client_id.reset(token)


def get_current_client_context() -> str | None:
    return _current_client_id.get()


def _supports_postgres_rls(db: Session) -> bool:
    bind = db.get_bind()
    return bool(bind and bind.dialect.name.startswith("postgresql"))


def apply_rls_context(db: Session) -> None:
    client_id = get_current_client_context()
    if not client_id:
        return
    db.info["current_client_id"] = client_id
    if settings.enable_rls and _supports_postgres_rls(db):
        db.execute(text("SELECT set_config('app.current_client_id', :client_id, false)"), {"client_id": client_id})


def clear_rls_context(db: Session) -> None:
    if settings.enable_rls and _supports_postgres_rls(db) and db.info.get("current_client_id"):
        try:
            db.execute(text("SELECT set_config('app.current_client_id', '', false)"))
        except Exception:
            pass
    db.info.pop("current_client_id", None)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        apply_rls_context(db)
        yield db
    finally:
        clear_rls_context(db)
        db.close()
