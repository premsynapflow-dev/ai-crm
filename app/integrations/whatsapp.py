from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.auth import get_current_client
from app.config import get_settings
from app.db.models import ChannelConnection, Client
from app.db.session import get_db
from app.utils.crypto import decrypt_secret, encrypt_secret
from app.utils.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)
router = APIRouter(tags=["integrations"])


class WhatsAppConnectionRequest(BaseModel):
    account_identifier: str = Field(..., description="Display phone number")
    phone_number_id: str
    business_account_id: str | None = None
    access_token: str
    verify_token: str | None = None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _verify_whatsapp_signature(payload: bytes, signature_header: str | None) -> bool:
    if not settings.whatsapp_app_secret:
        return True
    if not signature_header:
        return False
    prefix = "sha256="
    signature = signature_header[len(prefix):] if signature_header.startswith(prefix) else signature_header
    expected = hmac.new(settings.whatsapp_app_secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def _extract_whatsapp_text(message: dict[str, Any]) -> str:
    message_type = message.get("type")
    if message_type == "text":
        return message.get("text", {}).get("body", "")
    if message_type == "button":
        return message.get("button", {}).get("text", "")
    if message_type == "interactive":
        interactive = message.get("interactive", {})
        return (
            interactive.get("button_reply", {}).get("title")
            or interactive.get("list_reply", {}).get("title")
            or ""
        )
    return ""


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type(httpx.HTTPError),
)
def _graph_request(
    method: str,
    url: str,
    *,
    access_token: str,
    json_body: dict[str, Any] | None = None,
) -> httpx.Response:
    with httpx.Client(timeout=20.0) as client:
        response = client.request(
            method,
            url,
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            json=json_body,
        )
        if response.status_code >= 500:
            response.raise_for_status()
        return response


def send_whatsapp_text_message(
    *,
    connection: ChannelConnection,
    to_phone: str,
    body: str,
) -> dict[str, Any]:
    access_token = decrypt_secret(connection.access_token)
    if not access_token:
        raise RuntimeError("No WhatsApp access token stored for this connection")
    phone_number_id = (connection.metadata_json or {}).get("phone_number_id")
    if not phone_number_id:
        raise RuntimeError("WhatsApp connection is missing phone_number_id")
    response = _graph_request(
        "POST",
        f"https://graph.facebook.com/{settings.whatsapp_default_api_version}/{phone_number_id}/messages",
        access_token=access_token,
        json_body={
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_phone,
            "type": "text",
            "text": {"preview_url": False, "body": body},
        },
    )
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail={"message": "WhatsApp send failed", "response": response.text})
    return response.json()


@router.post("/integrations/whatsapp/connect")
def connect_whatsapp(
    payload: WhatsAppConnectionRequest,
    client: Client = Depends(get_current_client),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    connection = (
        db.query(ChannelConnection)
        .filter(
            ChannelConnection.client_id == client.id,
            ChannelConnection.channel_type == "whatsapp",
            ChannelConnection.account_identifier == payload.account_identifier,
        )
        .first()
    )
    if connection is None:
        connection = ChannelConnection(
            client_id=client.id,
            channel_type="whatsapp",
            account_identifier=payload.account_identifier,
        )
        db.add(connection)

    connection.access_token = encrypt_secret(payload.access_token)
    connection.refresh_token = None
    connection.token_expiry = None
    connection.status = "active"
    connection.metadata_json = {
        "phone_number_id": payload.phone_number_id,
        "business_account_id": payload.business_account_id,
        "verify_token": payload.verify_token or settings.whatsapp_verify_token,
        "connected_at": _utcnow().isoformat(),
    }
    db.commit()
    db.refresh(connection)
    return {
        "status": "connected",
        "connection_id": str(connection.id),
        "account_identifier": connection.account_identifier,
        "phone_number_id": payload.phone_number_id,
    }


@router.get("/webhooks/whatsapp")
def verify_whatsapp_webhook(
    mode: str = Query(default="", alias="hub.mode"),
    challenge: str = Query(default="", alias="hub.challenge"),
    verify_token: str = Query(default="", alias="hub.verify_token"),
) -> Any:
    expected_token = settings.whatsapp_verify_token
    if mode == "subscribe" and verify_token and verify_token == expected_token:
        return int(challenge) if challenge.isdigit() else challenge
    raise HTTPException(status_code=403, detail="WhatsApp webhook verification failed")


@router.post("/webhooks/whatsapp")
async def receive_whatsapp_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    from app.services.unified_ingestion import IncomingMessage, process_incoming_message

    raw_body = await request.body()
    if not _verify_whatsapp_signature(raw_body, request.headers.get("x-hub-signature-256")):
        raise HTTPException(status_code=401, detail="Invalid WhatsApp webhook signature")

    payload = await request.json()
    processed = 0
    for entry in payload.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            value = change.get("value", {}) or {}
            metadata = value.get("metadata", {}) or {}
            phone_number_id = metadata.get("phone_number_id")
            business_account_id = value.get("business_account_id")
            connection = (
                db.query(ChannelConnection)
                .filter(
                    ChannelConnection.channel_type == "whatsapp",
                    ChannelConnection.status == "active",
                )
                .order_by(ChannelConnection.created_at.desc())
                .all()
            )
            matched_connection = next(
                (
                    item
                    for item in connection
                    if (item.metadata_json or {}).get("phone_number_id") == phone_number_id
                    or (business_account_id and (item.metadata_json or {}).get("business_account_id") == business_account_id)
                ),
                None,
            )
            if matched_connection is None:
                logger.warning("No WhatsApp connection found for phone_number_id=%s", phone_number_id)
                continue

            contacts = value.get("contacts", []) or []
            contacts_by_wa_id = {contact.get("wa_id"): contact for contact in contacts if contact.get("wa_id")}
            for message in value.get("messages", []) or []:
                sender_id = message.get("from")
                contact = contacts_by_wa_id.get(sender_id, {})
                incoming = IncomingMessage(
                    client_id=matched_connection.client_id,
                    channel="whatsapp",
                    external_message_id=message.get("id", ""),
                    external_thread_id=sender_id or message.get("context", {}).get("id") or message.get("id", ""),
                    sender_id=sender_id,
                    sender_name=contact.get("profile", {}).get("name") or sender_id or "WhatsApp User",
                    message_text=_extract_whatsapp_text(message),
                    attachments=[],
                    timestamp=datetime.fromtimestamp(int(message.get("timestamp", "0")), tz=timezone.utc),
                    direction="inbound",
                    status="received",
                    raw_payload={
                        "connection_id": str(matched_connection.id),
                        "phone_number_id": phone_number_id,
                        "business_account_id": business_account_id,
                        "message_type": message.get("type"),
                    },
                )
                process_incoming_message(db, incoming)
                processed += 1
    db.commit()
    return {"status": "processed", "count": processed}
