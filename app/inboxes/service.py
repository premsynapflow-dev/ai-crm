from __future__ import annotations

import imaplib
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode
from uuid import UUID

import httpx
from fastapi import HTTPException
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from app.auth import resolve_current_client, resolve_current_client_user
from app.config import get_settings
from app.db.models import Client, ClientUser
from app.inboxes.models import Inbox
from app.utils.crypto import decrypt_secret, encrypt_secret
from app.utils.logging import get_logger
from app.utils.sanitize import sanitize_email

settings = get_settings()
logger = get_logger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/userinfo.email",
]
DEFAULT_SETTINGS_REDIRECT = "/settings?gmail_connected=true"

connect_token_serializer = URLSafeTimedSerializer(settings.secret_key, salt="inboxes-gmail-connect")
oauth_state_serializer = URLSafeTimedSerializer(settings.secret_key, salt="inboxes-gmail-state")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _coerce_uuid(value: str | UUID):
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


def infer_imap_host(email_address: str) -> str | None:
    domain = (email_address.split("@")[-1] if "@" in email_address else "").lower().strip()
    if domain in {"gmail.com", "googlemail.com"}:
        return "imap.gmail.com"
    if domain in {"yahoo.com", "yahoo.co.in", "yahoo.in"}:
        return "imap.mail.yahoo.com"
    if domain in {"outlook.com", "hotmail.com", "live.com"}:
        return "outlook.office365.com"
    return None


def ensure_google_oauth_config() -> str:
    missing: list[str] = []
    if not settings.google_client_id.strip():
        missing.append("GOOGLE_CLIENT_ID")
    if not settings.google_client_secret.strip():
        missing.append("GOOGLE_CLIENT_SECRET")

    redirect_uri = settings.google_oauth_redirect_uri_for("inboxes")
    if not redirect_uri:
        missing.append("GOOGLE_INBOXES_OAUTH_REDIRECT_URI or GOOGLE_OAUTH_REDIRECT_URI or APP_BASE_URL")

    if missing:
        raise HTTPException(status_code=500, detail=f"OAuth not configured. Missing: {', '.join(missing)}")
    return redirect_uri


def create_gmail_connect_url(client: Client, user: ClientUser) -> str:
    ensure_google_oauth_config()
    connect_token = connect_token_serializer.dumps(
        {
            "tenant_id": str(client.id),
            "client_user_id": str(user.id),
            "redirect_path": DEFAULT_SETTINGS_REDIRECT,
        }
    )
    connect_url = f"/auth/gmail/connect?connect_token={connect_token}"
    logger.info("Generated Gmail connect URL for tenant=%s user=%s", client.id, user.id)
    return connect_url


def resolve_gmail_connect_context(
    request,
    db: Session,
    *,
    connect_token: str | None = None,
    authorization: str | None = None,
) -> tuple[Client, ClientUser]:
    if connect_token:
        try:
            payload = connect_token_serializer.loads(connect_token, max_age=600)
        except SignatureExpired as exc:
            raise HTTPException(status_code=400, detail="Expired Gmail connection link") from exc
        except BadSignature as exc:
            raise HTTPException(status_code=400, detail="Invalid Gmail connection link") from exc

        try:
            tenant_id = _coerce_uuid(payload.get("tenant_id"))
            client_user_id = _coerce_uuid(payload.get("client_user_id"))
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Invalid Gmail connection link") from exc

        client = db.query(Client).filter(Client.id == tenant_id).first()
        user = db.query(ClientUser).filter(ClientUser.id == client_user_id).first()
        if client is None or user is None or user.client_id != client.id:
            raise HTTPException(status_code=404, detail="Unable to resolve Gmail connection context")
        return client, user

    client = resolve_current_client(request, db, authorization=authorization, required=True)
    user = resolve_current_client_user(request, db, authorization=authorization, required=True)
    return client, user


def build_google_redirect_url(*, tenant_id: str, redirect_path: str = DEFAULT_SETTINGS_REDIRECT) -> str:
    redirect_uri = ensure_google_oauth_config()
    state = oauth_state_serializer.dumps(
        {
            "tenant_id": tenant_id,
            "redirect_path": redirect_path,
        }
    )
    query = urlencode(
        {
            "client_id": settings.google_client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(GMAIL_SCOPES),
            "access_type": "offline",
            "include_granted_scopes": "true",
            "prompt": "consent",
            "state": state,
        }
    )
    return f"{GOOGLE_AUTH_URL}?{query}"


def load_oauth_state(state: str) -> dict[str, str]:
    try:
        payload = oauth_state_serializer.loads(state, max_age=900)
    except SignatureExpired as exc:
        raise HTTPException(status_code=400, detail="Expired Gmail OAuth state") from exc
    except BadSignature as exc:
        raise HTTPException(status_code=400, detail="Invalid Gmail OAuth state") from exc

    tenant_id = str(payload.get("tenant_id") or "").strip()
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Invalid Gmail OAuth state")
    redirect_path = str(payload.get("redirect_path") or DEFAULT_SETTINGS_REDIRECT)
    return {"tenant_id": str(_coerce_uuid(tenant_id)), "redirect_path": redirect_path}


def exchange_google_code(code: str) -> dict[str, Any]:
    redirect_uri = ensure_google_oauth_config()
    with httpx.Client(timeout=20.0) as client:
        response = client.post(
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
        logger.error("Gmail OAuth token exchange failed status=%s response=%s", response.status_code, response.text[:500])
        raise HTTPException(status_code=502, detail="Unable to exchange Gmail OAuth code")
    logger.info("Gmail OAuth token exchange succeeded")
    return response.json()


def fetch_google_user_email(access_token: str) -> str:
    with httpx.Client(timeout=20.0) as client:
        response = client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if response.status_code >= 400:
        logger.error("Gmail OAuth userinfo fetch failed status=%s response=%s", response.status_code, response.text[:500])
        raise HTTPException(status_code=502, detail="Unable to fetch Gmail account email")

    email_address = sanitize_email(response.json().get("email"))
    if not email_address:
        raise HTTPException(status_code=502, detail="Google OAuth did not return a valid email address")
    logger.info("Gmail OAuth userinfo resolved email=%s", email_address)
    return email_address


def serialize_inbox(inbox: Inbox) -> dict[str, Any]:
    return {
        "id": str(inbox.id),
        "email": inbox.email_address,
        "provider": inbox.provider_type,
        "status": "active" if inbox.is_active else "inactive",
        "created_at": inbox.created_at,
    }


def list_inboxes(db: Session, *, tenant_id) -> list[dict[str, Any]]:
    rows = (
        db.query(Inbox)
        .filter(Inbox.tenant_id == tenant_id)
        .order_by(Inbox.created_at.desc())
        .all()
    )
    return [serialize_inbox(row) for row in rows]


def upsert_gmail_inbox(
    db: Session,
    *,
    tenant_id,
    email_address: str,
    access_token: str,
    refresh_token: str | None,
    token_expiry: datetime | None,
) -> Inbox:
    tenant_id = _coerce_uuid(tenant_id)
    existing = (
        db.query(Inbox)
        .filter(
            Inbox.tenant_id == tenant_id,
            Inbox.email_address == email_address,
        )
        .first()
    )

    encrypted_access_token = encrypt_secret(access_token)
    encrypted_refresh_token = encrypt_secret(refresh_token) if refresh_token else None

    if existing is None:
        existing = Inbox(
            tenant_id=tenant_id,
            email_address=email_address,
        )
        db.add(existing)

    existing.provider_type = "gmail"
    existing.access_token = encrypted_access_token
    existing.refresh_token = encrypted_refresh_token or existing.refresh_token
    existing.token_expiry = token_expiry
    existing.imap_host = None
    existing.imap_port = None
    existing.imap_username = None
    existing.imap_password = None
    existing.is_active = True
    db.commit()
    db.refresh(existing)
    logger.info("Upserted Gmail inbox tenant=%s email=%s", tenant_id, email_address)
    return existing


def test_imap_connection(*, imap_host: str, imap_port: int, username: str, password: str, use_ssl: bool = True) -> None:
    mailbox: Any | None = None
    try:
        logger.info("Testing IMAP connection host=%s port=%s ssl=%s user=%s", imap_host, imap_port, use_ssl, username)
        if use_ssl:
            mailbox = imaplib.IMAP4_SSL(imap_host, imap_port)
        else:
            mailbox = imaplib.IMAP4(imap_host, imap_port)
            try:
                mailbox.starttls()
            except Exception:
                pass

        mailbox.login(username, password)
        status, _ = mailbox.select("INBOX", readonly=True)
        if status != "OK":
            raise HTTPException(status_code=400, detail="IMAP connection succeeded but the inbox could not be opened")
        logger.info("IMAP connection succeeded for host=%s user=%s", imap_host, username)
    except HTTPException:
        raise
    except imaplib.IMAP4.error as exc:
        logger.warning("IMAP connection failed for host=%s user=%s", imap_host, username)
        raise HTTPException(status_code=400, detail="Unable to connect to the IMAP server with the provided credentials") from exc
    except Exception as exc:
        logger.warning("IMAP connection error for host=%s user=%s", imap_host, username)
        raise HTTPException(status_code=400, detail=f"Unable to connect to the IMAP server: {exc}") from exc
    finally:
        if mailbox is not None:
            try:
                mailbox.logout()
            except Exception:
                pass


def upsert_imap_inbox(
    db: Session,
    *,
    tenant_id,
    email_address: str,
    imap_host: str,
    imap_port: int,
    use_ssl: bool,
    username: str,
    password: str,
) -> Inbox:
    tenant_id = _coerce_uuid(tenant_id)
    existing = (
        db.query(Inbox)
        .filter(
            Inbox.tenant_id == tenant_id,
            Inbox.email_address == email_address,
        )
        .first()
    )

    if existing is None:
        existing = Inbox(
            tenant_id=tenant_id,
            email_address=email_address,
        )
        db.add(existing)

    existing.provider_type = "imap"
    existing.access_token = None
    existing.refresh_token = None
    existing.token_expiry = None
    existing.imap_host = imap_host
    existing.imap_port = imap_port
    existing.imap_username = username
    existing.imap_password = encrypt_secret(password)
    existing.imap_use_ssl = use_ssl
    existing.is_active = True
    db.commit()
    db.refresh(existing)
    return existing


def fetch_imap_messages(inbox: Inbox, *, max_results: int = 20) -> list["IncomingMessage"]:
    from app.services.unified_ingestion import IncomingMessage
    from app.integrations.email import _extract_attachments, _extract_text_part, _parse_email_timestamp

    if not inbox.imap_host or not inbox.imap_password:
        return []
    username = inbox.imap_username or inbox.email_address
    password = decrypt_secret(inbox.imap_password)
    if not username or not password:
        return []

    mailbox: Any | None = None
    messages: list[IncomingMessage] = []
    try:
        if inbox.imap_use_ssl:
            mailbox = imaplib.IMAP4_SSL(inbox.imap_host, int(inbox.imap_port or 993))
        else:
            mailbox = imaplib.IMAP4(inbox.imap_host, int(inbox.imap_port or 993))
            try:
                mailbox.starttls()
            except Exception:
                pass

        mailbox.login(username, password)
        mailbox.select("INBOX")

        status_code, data = mailbox.uid("search", None, "UNSEEN")
        if status_code != "OK" or not data or not data[0]:
            status_code, data = mailbox.uid("search", None, "ALL")
        if status_code != "OK" or not data or not data[0]:
            return []

        uids = data[0].split()
        if max_results and len(uids) > max_results:
            uids = uids[-max_results:]

        for uid in uids:
            uid_value = uid.decode("utf-8", errors="ignore") if isinstance(uid, bytes) else str(uid)
            fetch_status, message_data = mailbox.uid("fetch", uid, "(RFC822)")
            if fetch_status != "OK" or not message_data:
                continue
            raw_bytes = message_data[0][1]
            parsed = BytesParser(policy=policy.default).parsebytes(raw_bytes)

            sender_addresses = getaddresses([parsed.get("From", "")])
            sender_name, sender_email = sender_addresses[0] if sender_addresses else ("", "")
            subject = str(parsed.get("Subject", "") or "").strip()
            body = _extract_text_part(parsed)
            snippet = (body[:200] if body else "").strip()
            message_text = "\n\n".join(part for part in [subject, body] if part).strip()
            external_message_id = f"imap:{inbox.id}:{uid_value}"
            external_thread_id = str(parsed.get("Message-ID", "") or external_message_id)

            messages.append(
                IncomingMessage(
                    client_id=inbox.tenant_id,
                    channel="email",
                    external_message_id=external_message_id,
                    external_thread_id=external_thread_id,
                    sender_id=sender_email or sender_name,
                    sender_name=sender_name or sender_email or "IMAP Sender",
                    message_text=message_text,
                    attachments=_extract_attachments(parsed),
                    timestamp=_parse_email_timestamp(parsed.get("Date")),
                    direction="inbound",
                    status="received",
                    raw_payload={
                        "headers": dict(parsed.items()),
                        "snippet": snippet,
                        "imap_uid": uid_value,
                        "inbox_id": str(inbox.id),
                        "account_identifier": inbox.email_address,
                    },
                )
            )
    finally:
        if mailbox is not None:
            try:
                mailbox.logout()
            except Exception:
                logger.debug("IMAP logout failed for inbox %s", inbox.id)
    if messages:
        logger.info("Fetched %s IMAP messages for inbox=%s", len(messages), inbox.id)
    return messages


def normalize_email_address(email_address: str) -> str:
    normalized = sanitize_email(email_address)
    if not normalized:
        raise HTTPException(status_code=400, detail="A valid email address is required")
    return normalized


def build_gmail_token_expiry(token_payload: dict[str, Any]) -> datetime | None:
    expires_in = token_payload.get("expires_in")
    if expires_in in (None, ""):
        return None
    try:
        return _utcnow() + timedelta(seconds=int(expires_in))
    except (TypeError, ValueError):
        return None
