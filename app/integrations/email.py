from __future__ import annotations

import base64
import email
import imaplib
import smtplib
import uuid
from datetime import datetime, timezone
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import getaddresses, parsedate_to_datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.auth import get_current_client
from app.config import get_settings
from app.db.models import ChannelConnection, Client
from app.db.session import get_db
from app.utils.crypto import decrypt_secret, encrypt_secret
from app.utils.logging import get_logger
from app.utils.webhook_security import verify_webhook_signature

settings = get_settings()
logger = get_logger(__name__)
router = APIRouter(tags=["integrations"])


class EmailConnectionRequest(BaseModel):
    mode: str = Field(default="forwarding", pattern="^(forwarding|imap)$")
    account_identifier: str | None = None
    display_name: str | None = None
    imap_host: str | None = None
    imap_port: int = 993
    imap_username: str | None = None
    imap_password: str | None = None
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None


class ForwardedEmailRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    raw_email: str


def send_email(
    to_email: str,
    subject: str,
    body: str,
    *,
    from_email: str | None = None,
    reply_to: str | None = None,
    in_reply_to: str | None = None,
    references: str | None = None,
) -> bool:
    if not settings.smtp_host:
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_email or settings.smtp_from
    msg["To"] = to_email
    if reply_to:
        msg["Reply-To"] = reply_to
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    if references:
        msg["References"] = references
    msg.set_content(body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.starttls()
        if settings.smtp_user and settings.smtp_password:
            server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(msg)
    return True


def forwarding_address_for_client(client: Client) -> str:
    safe_slug = "".join(ch.lower() for ch in client.name if ch.isalnum())[:24] or str(client.id).split("-", 1)[0]
    return f"{safe_slug}-{str(client.id)[:8]}@{settings.inbound_email_domain}"


def _parse_email_timestamp(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _extract_text_part(message: email.message.Message) -> str:
    if message.is_multipart():
        parts: list[str] = []
        for part in message.walk():
            if part.get_content_maintype() == "multipart":
                continue
            if part.get_content_disposition() == "attachment":
                continue
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True) or b""
                charset = part.get_content_charset() or "utf-8"
                parts.append(payload.decode(charset, errors="replace"))
        if parts:
            return "\n".join(part.strip() for part in parts if part.strip()).strip()
    payload = message.get_payload(decode=True) or b""
    charset = message.get_content_charset() or "utf-8"
    return payload.decode(charset, errors="replace").strip()


def _extract_attachments(message: email.message.Message) -> list[dict[str, Any]]:
    attachments: list[dict[str, Any]] = []
    for part in message.walk():
        if part.get_content_disposition() != "attachment":
            continue
        filename = part.get_filename()
        payload = part.get_payload(decode=True) or b""
        attachments.append(
            {
                "filename": filename,
                "content_type": part.get_content_type(),
                "size": len(payload),
            }
        )
    return attachments


def _extract_connection_recipient(message: email.message.Message) -> str | None:
    candidates = []
    for header_name in ("Delivered-To", "X-Original-To", "Original-Recipient", "To", "Cc"):
        header_value = message.get(header_name)
        if header_value:
            candidates.extend(address for _, address in getaddresses([header_value]) if address)
    for candidate in candidates:
        if candidate.lower().endswith(f"@{settings.inbound_email_domain}".lower()):
            return candidate.lower()
    return None


def _parse_raw_email(raw_email: str) -> tuple[email.message.Message, bytes]:
    try:
        if "\n" not in raw_email and len(raw_email) % 4 == 0:
            raw_bytes = base64.b64decode(raw_email, validate=True)
        else:
            raw_bytes = raw_email.encode("utf-8")
    except Exception:
        raw_bytes = raw_email.encode("utf-8")
    return BytesParser(policy=policy.default).parsebytes(raw_bytes), raw_bytes


@router.post("/integrations/email/connect")
def connect_email_integration(
    payload: EmailConnectionRequest,
    client: Client = Depends(get_current_client),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    mode = payload.mode.strip().lower()
    if mode == "forwarding":
        account_identifier = payload.account_identifier or forwarding_address_for_client(client)
        metadata = {
            "mode": "forwarding",
            "display_name": payload.display_name or client.name,
        }
        access_token = None
        refresh_token = None
        token_expiry = None
    else:
        if not all([payload.imap_host, payload.imap_username, payload.imap_password]):
            raise HTTPException(status_code=400, detail="IMAP host, username, and password are required")
        account_identifier = payload.account_identifier or payload.imap_username
        metadata = {
            "mode": "imap",
            "display_name": payload.display_name or client.name,
            "imap_host": payload.imap_host,
            "imap_port": payload.imap_port,
            "imap_username": payload.imap_username,
            "smtp_host": payload.smtp_host,
            "smtp_port": payload.smtp_port,
            "smtp_username": payload.smtp_username,
        }
        access_token = encrypt_secret(payload.imap_password)
        refresh_token = encrypt_secret(payload.smtp_password)
        token_expiry = None

    connection = (
        db.query(ChannelConnection)
        .filter(
            ChannelConnection.client_id == client.id,
            ChannelConnection.channel_type == "email",
            ChannelConnection.account_identifier == account_identifier,
        )
        .first()
    )
    if connection is None:
        connection = ChannelConnection(
            client_id=client.id,
            channel_type="email",
            account_identifier=account_identifier,
        )
        db.add(connection)

    connection.access_token = access_token
    connection.refresh_token = refresh_token
    connection.token_expiry = token_expiry
    connection.status = "active"
    connection.metadata_json = metadata
    db.commit()
    db.refresh(connection)
    return {
        "connection_id": str(connection.id),
        "channel_type": connection.channel_type,
        "account_identifier": connection.account_identifier,
        "status": connection.status,
        "metadata": connection.metadata_json,
    }


@router.get("/integrations/list")
def list_integrations(
    client: Client = Depends(get_current_client),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    connections = (
        db.query(ChannelConnection)
        .filter(ChannelConnection.client_id == client.id)
        .order_by(ChannelConnection.channel_type.asc(), ChannelConnection.created_at.desc())
        .all()
    )
    return [
        {
            "id": str(connection.id),
            "channel": connection.channel_type,
            "status": connection.status,
            "account_identifier": connection.account_identifier,
            "created_at": connection.created_at.isoformat() if connection.created_at else None,
            "metadata": connection.metadata_json or {},
        }
        for connection in connections
    ]


@router.post("/webhooks/email/forwarded")
async def receive_forwarded_email(
    payload: ForwardedEmailRequest,
    request: Request,
    db: Session = Depends(get_db),
    x_synapflow_signature: str = Header(default="", alias="x-synapflow-signature"),
) -> dict[str, Any]:
    from app.services.unified_ingestion import IncomingMessage, process_incoming_message

    raw_message, raw_bytes = _parse_raw_email(payload.raw_email)

    if settings.inbound_email_webhook_secret:
        if not x_synapflow_signature or not verify_webhook_signature(raw_bytes, x_synapflow_signature, settings.inbound_email_webhook_secret):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid forwarded email signature")

    recipient = _extract_connection_recipient(raw_message)
    if not recipient:
        raise HTTPException(status_code=400, detail="Unable to resolve inbound forwarding address")

    connection = (
        db.query(ChannelConnection)
        .filter(
            ChannelConnection.channel_type == "email",
            ChannelConnection.account_identifier == recipient,
            ChannelConnection.status == "active",
        )
        .first()
    )
    if connection is None:
        raise HTTPException(status_code=404, detail="No active email connection found for forwarded address")

    sender_addresses = getaddresses([raw_message.get("From", "")])
    sender_name, sender_email = sender_addresses[0] if sender_addresses else ("", "")
    subject = str(raw_message.get("Subject", "") or "").strip()
    body = _extract_text_part(raw_message)
    message_text = "\n\n".join(part for part in [subject, body] if part).strip()
    external_message_id = str(raw_message.get("Message-ID", "") or f"email-forwarded-{uuid.uuid4()}")
    external_thread_id = str(raw_message.get("In-Reply-To", "") or raw_message.get("References", "") or external_message_id)

    normalized = IncomingMessage(
        client_id=connection.client_id,
        channel="email",
        external_message_id=external_message_id,
        external_thread_id=external_thread_id,
        sender_id=sender_email or sender_name or recipient,
        sender_name=sender_name or sender_email or "Email Sender",
        message_text=message_text,
        attachments=_extract_attachments(raw_message),
        timestamp=_parse_email_timestamp(raw_message.get("Date")),
        direction="inbound",
        status="received",
        raw_payload={
            "headers": dict(raw_message.items()),
            "connection_id": str(connection.id),
            "account_identifier": connection.account_identifier,
            "recipient": recipient,
            "request_path": str(request.url.path),
        },
    )
    result = process_incoming_message(db, normalized)
    db.commit()
    return result


def poll_imap_connection(connection: ChannelConnection) -> list[IncomingMessage]:
    from app.services.unified_ingestion import IncomingMessage

    metadata = connection.metadata_json or {}
    if metadata.get("mode") != "imap":
        return []
    imap_host = metadata.get("imap_host")
    imap_port = int(metadata.get("imap_port") or 993)
    username = metadata.get("imap_username") or connection.account_identifier
    password = decrypt_secret(connection.access_token)
    if not all([imap_host, username, password]):
        return []

    messages: list[IncomingMessage] = []
    mailbox = imaplib.IMAP4_SSL(imap_host, imap_port)
    try:
        mailbox.login(username, password)
        mailbox.select("INBOX")
        status_code, data = mailbox.search(None, "UNSEEN")
        if status_code != "OK":
            return []
        for num in data[0].split():
            fetch_status, message_data = mailbox.fetch(num, "(RFC822)")
            if fetch_status != "OK":
                continue
            raw_bytes = message_data[0][1]
            parsed = BytesParser(policy=policy.default).parsebytes(raw_bytes)
            sender_addresses = getaddresses([parsed.get("From", "")])
            sender_name, sender_email = sender_addresses[0] if sender_addresses else ("", "")
            subject = str(parsed.get("Subject", "") or "").strip()
            body = _extract_text_part(parsed)
            external_message_id = str(parsed.get("Message-ID", "") or f"email-imap-{uuid.uuid4()}")
            external_thread_id = str(parsed.get("In-Reply-To", "") or parsed.get("References", "") or external_message_id)
            messages.append(
                IncomingMessage(
                    client_id=connection.client_id,
                    channel="email",
                    external_message_id=external_message_id,
                    external_thread_id=external_thread_id,
                    sender_id=sender_email or sender_name,
                    sender_name=sender_name or sender_email or "Email Sender",
                    message_text="\n\n".join(part for part in [subject, body] if part).strip(),
                    attachments=_extract_attachments(parsed),
                    timestamp=_parse_email_timestamp(parsed.get("Date")),
                    direction="inbound",
                    status="received",
                    raw_payload={
                        "headers": dict(parsed.items()),
                        "connection_id": str(connection.id),
                        "account_identifier": connection.account_identifier,
                        "mode": "imap",
                    },
                )
            )
    finally:
        try:
            mailbox.logout()
        except Exception:
            logger.debug("IMAP logout failed for connection %s", connection.id)
    return messages
