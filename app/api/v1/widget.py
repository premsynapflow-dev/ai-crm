"""Website chat widget API — no JWT required; authenticated via x-api-key in script tag."""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.models import Client, Conversation, UnifiedMessage
from app.db.session import SessionLocal
from app.services.unified_ingestion import IncomingMessage, process_incoming_message
from app.utils.logging import get_logger

router = APIRouter(prefix="/api/widget", tags=["widget"])
logger = get_logger(__name__)

_RATE_LIMIT: dict[str, list[float]] = {}
_RATE_WINDOW = 60.0
_RATE_MAX = 10


def _check_rate_limit(key: str) -> None:
    import time
    now = time.time()
    window = _RATE_LIMIT.setdefault(key, [])
    _RATE_LIMIT[key] = [t for t in window if now - t < _RATE_WINDOW]
    if len(_RATE_LIMIT[key]) >= _RATE_MAX:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    _RATE_LIMIT[key].append(now)


def _get_client(api_key: str, db: Session) -> Client:
    client = db.query(Client).filter(Client.api_key == api_key.strip()).first()
    if client is None:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return client


class WidgetMessage(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=128)
    message: str = Field(..., min_length=1, max_length=5000)
    page_url: str | None = None
    customer_email: str | None = None
    customer_name: str | None = None


@router.post("/message", status_code=201)
async def receive_widget_message(
    body: WidgetMessage,
    x_api_key: str = Header(default="", alias="x-api-key"),
    x_forwarded_for: str | None = Header(default=None),
):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing x-api-key header")

    ip = (x_forwarded_for or "unknown").split(",")[0].strip()
    _check_rate_limit(f"{x_api_key}:{ip}")

    db = SessionLocal()
    try:
        client = _get_client(x_api_key, db)

        ext_id = hashlib.sha256(
            f"{client.id}:{body.session_id}:{body.message[:80]}:{datetime.now(timezone.utc).isoformat()}".encode()
        ).hexdigest()[:32]

        msg = IncomingMessage(
            client_id=str(client.id),
            channel="chat_widget",
            external_message_id=ext_id,
            external_thread_id=body.session_id,
            sender_id=body.customer_email,
            sender_name=body.customer_name,
            message_text=body.message,
            timestamp=datetime.now(timezone.utc),
            direction="inbound",
            status="received",
            raw_payload={
                "session_id": body.session_id,
                "page_url": body.page_url,
            },
        )
        result = process_incoming_message(db, msg)
        db.commit()
        return {"status": "received", "message_id": result.get("message_id")}
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Widget message error: %s", exc)
        raise HTTPException(status_code=500, detail="Internal error")
    finally:
        db.close()


@router.get("/replies/{session_id}")
async def poll_widget_replies(
    session_id: str,
    since: str | None = Query(None, description="ISO timestamp; only return replies after this"),
    x_api_key: str = Header(default="", alias="x-api-key"),
):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing x-api-key header")

    since_dt: datetime | None = None
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid 'since' timestamp")

    db = SessionLocal()
    try:
        client = _get_client(x_api_key, db)

        conv = (
            db.query(Conversation)
            .filter(
                Conversation.client_id == client.id,
                Conversation.external_thread_id == session_id,
                Conversation.channel == "chat_widget",
            )
            .first()
        )
        if conv is None:
            return {"replies": []}

        q = db.query(UnifiedMessage).filter(
            UnifiedMessage.client_id == client.id,
            UnifiedMessage.external_thread_id == session_id,
            UnifiedMessage.direction == "outbound",
        )
        if since_dt:
            q = q.filter(UnifiedMessage.timestamp > since_dt)

        messages = q.order_by(UnifiedMessage.timestamp.asc()).limit(20).all()
        return {
            "replies": [
                {
                    "body": m.message_text,
                    "created_at": m.timestamp.isoformat() if m.timestamp else None,
                }
                for m in messages
            ]
        }
    finally:
        db.close()
