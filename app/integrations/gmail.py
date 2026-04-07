from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import getaddresses
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from itsdangerous import BadSignature, URLSafeSerializer
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
state_serializer = URLSafeSerializer(settings.secret_key, salt="gmail-oauth")

GOOGLE_OAUTH_SCOPE = "https://www.googleapis.com/auth/gmail.modify https://www.googleapis.com/auth/gmail.send"
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _watch_label_ids() -> list[str]:
    return [item.strip() for item in settings.gmail_watch_label_ids.split(",") if item.strip()]


def _connection_metadata(connection: ChannelConnection) -> dict[str, Any]:
    return dict(connection.metadata_json or {})


def _gmail_headers(message_payload: dict[str, Any]) -> dict[str, str]:
    return {
        header.get("name", ""): header.get("value", "")
        for header in message_payload.get("headers", [])
        if header.get("name")
    }


def _decode_gmail_part(data: str | None) -> str:
    if not data:
        return ""
    padded = data + "=" * (-len(data) % 4)
    try:
        return base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8", errors="replace")
    except Exception:
        return ""


def _extract_gmail_body(payload: dict[str, Any]) -> str:
    mime_type = payload.get("mimeType", "")
    body = payload.get("body", {}) or {}
    if mime_type == "text/plain":
        return _decode_gmail_part(body.get("data"))
    for part in payload.get("parts", []) or []:
        text = _extract_gmail_body(part)
        if text.strip():
            return text
    return _decode_gmail_part(body.get("data"))


def _extract_gmail_attachments(payload: dict[str, Any]) -> list[dict[str, Any]]:
    attachments: list[dict[str, Any]] = []
    for part in payload.get("parts", []) or []:
        filename = part.get("filename")
        body = part.get("body", {}) or {}
        if filename and body.get("attachmentId"):
            attachments.append(
                {
                    "filename": filename,
                    "content_type": part.get("mimeType"),
                    "attachment_id": body.get("attachmentId"),
                    "size": body.get("size", 0),
                }
            )
        attachments.extend(_extract_gmail_attachments(part))
    return attachments


def _parse_sender(headers: dict[str, str]) -> tuple[str, str]:
    from_header = headers.get("From", "")
    sender_addresses = getaddresses([from_header])
    sender_name, sender_email = sender_addresses[0] if sender_addresses else ("", "")
    return sender_name or sender_email, sender_email or sender_name


def _request_error(response: httpx.Response) -> HTTPException:
    try:
        detail = response.json()
    except Exception:
        detail = response.text
    return HTTPException(status_code=502, detail={"message": "Google API request failed", "response": detail})


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type(httpx.HTTPError),
)
def _google_request(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
) -> httpx.Response:
    with httpx.Client(timeout=20.0) as client:
        response = client.request(method, url, headers=headers, params=params, json=json_body, data=data)
        if response.status_code >= 500:
            response.raise_for_status()
        return response


def _exchange_code_for_tokens(code: str) -> dict[str, Any]:
    redirect_uri = _ensure_google_oauth_config()
    response = _google_request(
        "POST",
        GOOGLE_TOKEN_URL,
        data={
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
    )
    if response.status_code >= 400:
        raise _request_error(response)
    return response.json()


def _ensure_google_oauth_config() -> str:
    missing: list[str] = []
    if not settings.google_client_id.strip():
        missing.append("GOOGLE_CLIENT_ID")
    if not settings.google_client_secret.strip():
        missing.append("GOOGLE_CLIENT_SECRET")

    redirect_uri = settings.google_oauth_redirect_uri_for("integrations")
    if not redirect_uri:
        missing.append("GOOGLE_INTEGRATIONS_OAUTH_REDIRECT_URI or GOOGLE_OAUTH_REDIRECT_URI or APP_BASE_URL")
    if not settings.gmail_pubsub_topic.strip():
        missing.append("GMAIL_PUBSUB_TOPIC")

    if missing:
        raise HTTPException(status_code=500, detail=f"Gmail integration is not configured. Missing: {', '.join(missing)}")
    return redirect_uri


def _refresh_access_token(connection: ChannelConnection, *, force: bool = False) -> str:
    refresh_token = decrypt_secret(connection.refresh_token)
    access_token = decrypt_secret(connection.access_token)
    token_expiry = connection.token_expiry
    if not force and access_token and token_expiry and token_expiry > _utcnow() + timedelta(minutes=2):
        return access_token
    if not refresh_token:
        raise RuntimeError("No Gmail refresh token stored for connection")

    response = _google_request(
        "POST",
        GOOGLE_TOKEN_URL,
        data={
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
    )
    if response.status_code >= 400:
        connection.status = "expired"
        raise _request_error(response)
    payload = response.json()
    new_access_token = payload["access_token"]
    connection.access_token = encrypt_secret(new_access_token)
    connection.token_expiry = _utcnow() + timedelta(seconds=int(payload.get("expires_in", 3600)))
    return new_access_token


def _authorized_headers(connection: ChannelConnection, *, force_refresh: bool = False) -> dict[str, str]:
    token = _refresh_access_token(connection, force=force_refresh)
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _gmail_profile(connection: ChannelConnection) -> dict[str, Any]:
    response = _google_request("GET", f"{GMAIL_API_BASE}/users/me/profile", headers=_authorized_headers(connection))
    if response.status_code == 401:
        response = _google_request("GET", f"{GMAIL_API_BASE}/users/me/profile", headers=_authorized_headers(connection, force_refresh=True))
    if response.status_code >= 400:
        raise _request_error(response)
    return response.json()


def setup_gmail_watch(connection: ChannelConnection) -> dict[str, Any]:
    if not settings.gmail_pubsub_topic:
        raise RuntimeError("GMAIL_PUBSUB_TOPIC must be configured before enabling Gmail watch")
    request_body: dict[str, Any] = {"topicName": settings.gmail_pubsub_topic}
    label_ids = _watch_label_ids()
    if label_ids:
        request_body["labelIds"] = label_ids
        request_body["labelFilterBehavior"] = "INCLUDE"
    response = _google_request(
        "POST",
        f"{GMAIL_API_BASE}/users/me/watch",
        headers=_authorized_headers(connection),
        json_body=request_body,
    )
    if response.status_code == 401:
        response = _google_request(
            "POST",
            f"{GMAIL_API_BASE}/users/me/watch",
            headers=_authorized_headers(connection, force_refresh=True),
            json_body=request_body,
        )
    if response.status_code >= 400:
        raise _request_error(response)
    watch_data = response.json()
    metadata = _connection_metadata(connection)
    metadata["history_id"] = watch_data.get("historyId")
    metadata["watch_response"] = watch_data
    connection.metadata_json = metadata
    return watch_data


def _fetch_gmail_message(connection: ChannelConnection, message_id: str) -> dict[str, Any]:
    response = _google_request(
        "GET",
        f"{GMAIL_API_BASE}/users/me/messages/{message_id}",
        headers=_authorized_headers(connection),
        params={"format": "full"},
    )
    if response.status_code == 401:
        response = _google_request(
            "GET",
            f"{GMAIL_API_BASE}/users/me/messages/{message_id}",
            headers=_authorized_headers(connection, force_refresh=True),
            params={"format": "full"},
        )
    if response.status_code >= 400:
        raise _request_error(response)
    return response.json()


def sync_gmail_history(db: Session, connection: ChannelConnection, history_id: str | None = None) -> list[dict[str, Any]]:
    from app.services.unified_ingestion import IncomingMessage, process_incoming_message

    metadata = _connection_metadata(connection)
    start_history_id = metadata.get("history_id") or history_id
    if not start_history_id:
        logger.info("Skipping Gmail sync for %s because no historyId is stored yet", connection.id)
        return []

    params = {
        "startHistoryId": str(start_history_id),
        "historyTypes": ["messageAdded"],
    }
    response = _google_request(
        "GET",
        f"{GMAIL_API_BASE}/users/me/history",
        headers=_authorized_headers(connection),
        params=params,
    )
    if response.status_code == 401:
        response = _google_request(
            "GET",
            f"{GMAIL_API_BASE}/users/me/history",
            headers=_authorized_headers(connection, force_refresh=True),
            params=params,
        )
    if response.status_code == 404:
        setup_gmail_watch(connection)
        return []
    if response.status_code >= 400:
        raise _request_error(response)

    payload = response.json()
    processed: list[dict[str, Any]] = []
    for history_item in payload.get("history", []) or []:
        for added in history_item.get("messagesAdded", []) or []:
            message_id = added.get("message", {}).get("id")
            if not message_id:
                continue
            gmail_message = _fetch_gmail_message(connection, message_id)
            headers = _gmail_headers(gmail_message.get("payload", {}))
            sender_name, sender_email = _parse_sender(headers)
            normalized = IncomingMessage(
                client_id=connection.client_id,
                channel="gmail",
                external_message_id=gmail_message["id"],
                external_thread_id=gmail_message.get("threadId"),
                sender_id=sender_email,
                sender_name=sender_name,
                message_text="\n\n".join(
                    part
                    for part in [
                        headers.get("Subject", "").strip(),
                        _extract_gmail_body(gmail_message.get("payload", {})).strip(),
                    ]
                    if part
                ).strip(),
                attachments=_extract_gmail_attachments(gmail_message.get("payload", {})),
                timestamp=datetime.fromtimestamp(int(gmail_message.get("internalDate", "0")) / 1000, tz=timezone.utc),
                direction="inbound",
                status="received",
                raw_payload={
                    "connection_id": str(connection.id),
                    "history_id": history_item.get("id"),
                    "gmail_labels": gmail_message.get("labelIds", []),
                    "snippet": gmail_message.get("snippet"),
                    "headers": headers,
                },
            )
            processed.append(process_incoming_message(db, normalized))

    if payload.get("historyId"):
        metadata = _connection_metadata(connection)
        metadata["history_id"] = payload["historyId"]
        connection.metadata_json = metadata
    return processed


def send_gmail_reply(
    *,
    connection: ChannelConnection,
    to_email: str,
    subject: str,
    body: str,
    thread_id: str | None = None,
    references: str | None = None,
) -> dict[str, Any]:
    if not to_email:
        raise RuntimeError("Gmail reply requires a recipient email address")

    message = EmailMessage()
    message["To"] = to_email
    message["Subject"] = subject
    if references:
        message["In-Reply-To"] = references
        message["References"] = references
    message.set_content(body)
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    payload: dict[str, Any] = {"raw": raw_message}
    if thread_id:
        payload["threadId"] = thread_id

    response = _google_request(
        "POST",
        f"{GMAIL_API_BASE}/users/me/messages/send",
        headers=_authorized_headers(connection),
        json_body=payload,
    )
    if response.status_code == 401:
        response = _google_request(
            "POST",
            f"{GMAIL_API_BASE}/users/me/messages/send",
            headers=_authorized_headers(connection, force_refresh=True),
            json_body=payload,
        )
    if response.status_code >= 400:
        raise _request_error(response)
    return response.json()


@router.get("/integrations/gmail/connect")
def connect_gmail(
    client: Client = Depends(get_current_client),
) -> dict[str, Any]:
    redirect_uri = _ensure_google_oauth_config()

    state = state_serializer.dumps({"client_id": str(client.id)})
    auth_url = f"{GOOGLE_AUTH_URL}?{urlencode({'client_id': settings.google_client_id, 'redirect_uri': redirect_uri, 'response_type': 'code', 'scope': GOOGLE_OAUTH_SCOPE, 'access_type': 'offline', 'prompt': 'consent', 'state': state})}"
    return {"auth_url": auth_url}


@router.get("/integrations/gmail/callback")
def gmail_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        state_data = state_serializer.loads(state)
    except BadSignature as exc:
        raise HTTPException(status_code=400, detail="Invalid Gmail OAuth state") from exc

    client = db.query(Client).filter(Client.id == state_data.get("client_id")).first()
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found for Gmail OAuth")

    token_data = _exchange_code_for_tokens(code)
    connection = ChannelConnection(
        client_id=client.id,
        channel_type="gmail",
        account_identifier="pending",
        access_token=encrypt_secret(token_data.get("access_token")),
        refresh_token=encrypt_secret(token_data.get("refresh_token")),
        token_expiry=_utcnow() + timedelta(seconds=int(token_data.get("expires_in", 3600))),
        metadata_json={"oauth_scopes": token_data.get("scope", GOOGLE_OAUTH_SCOPE).split(" ")},
        status="active",
    )
    db.add(connection)
    db.flush()

    profile = _gmail_profile(connection)
    account_identifier = profile.get("emailAddress")
    existing_connection = (
        db.query(ChannelConnection)
        .filter(
            ChannelConnection.client_id == client.id,
            ChannelConnection.channel_type == "gmail",
            ChannelConnection.account_identifier == account_identifier,
            ChannelConnection.id != connection.id,
        )
        .first()
    )
    if existing_connection is not None:
        existing_connection.access_token = connection.access_token
        existing_connection.refresh_token = connection.refresh_token
        existing_connection.token_expiry = connection.token_expiry
        existing_connection.status = "active"
        existing_connection.metadata_json = {
            **(existing_connection.metadata_json or {}),
            **(connection.metadata_json or {}),
        }
        db.delete(connection)
        connection = existing_connection
    connection.account_identifier = account_identifier
    metadata = _connection_metadata(connection)
    metadata["email_address"] = account_identifier
    metadata["messages_total"] = profile.get("messagesTotal")
    metadata["threads_total"] = profile.get("threadsTotal")
    connection.metadata_json = metadata
    setup_gmail_watch(connection)
    db.commit()
    db.refresh(connection)
    return {
        "status": "connected",
        "connection_id": str(connection.id),
        "account_identifier": connection.account_identifier,
        "watch_history_id": connection.metadata_json.get("history_id"),
    }


@router.post("/webhooks/gmail/pubsub")
async def gmail_pubsub_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    envelope = await request.json()
    message = envelope.get("message", {})
    encoded_data = message.get("data")
    if not encoded_data:
        return {"status": "ignored", "reason": "missing_data"}

    decoded = base64.b64decode(encoded_data).decode("utf-8")
    notification = json.loads(decoded)
    email_address = notification.get("emailAddress")
    history_id = notification.get("historyId")
    if not email_address:
        raise HTTPException(status_code=400, detail="Invalid Gmail Pub/Sub notification payload")

    connection = (
        db.query(ChannelConnection)
        .filter(
            ChannelConnection.channel_type == "gmail",
            ChannelConnection.account_identifier == email_address,
            ChannelConnection.status == "active",
        )
        .first()
    )
    if connection is None:
        logger.warning("No Gmail connection found for notification recipient %s", email_address)
        return {"status": "ignored", "reason": "connection_not_found"}

    processed = sync_gmail_history(db, connection)
    if history_id:
        metadata = _connection_metadata(connection)
        metadata["history_id"] = history_id
        connection.metadata_json = metadata
    db.commit()
    return {"status": "processed", "count": len(processed)}
