from __future__ import annotations

import imaplib
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
from app.utils.crypto import encrypt_secret
from app.utils.sanitize import sanitize_email

settings = get_settings()

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
]
DEFAULT_SETTINGS_REDIRECT = "/settings"

connect_token_serializer = URLSafeTimedSerializer(settings.secret_key, salt="inboxes-gmail-connect")
oauth_state_serializer = URLSafeTimedSerializer(settings.secret_key, salt="inboxes-gmail-state")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _coerce_uuid(value: str | UUID):
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


def ensure_google_oauth_config() -> None:
    if not settings.google_client_id or not settings.google_client_secret or not settings.google_oauth_redirect_uri:
        raise HTTPException(status_code=500, detail="Google OAuth is not configured")


def create_gmail_connect_url(client: Client, user: ClientUser) -> str:
    ensure_google_oauth_config()
    connect_token = connect_token_serializer.dumps(
        {
            "tenant_id": str(client.id),
            "client_user_id": str(user.id),
            "redirect_path": DEFAULT_SETTINGS_REDIRECT,
        }
    )
    return f"/auth/gmail/connect?connect_token={connect_token}"


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
    ensure_google_oauth_config()
    state = oauth_state_serializer.dumps(
        {
            "tenant_id": tenant_id,
            "redirect_path": redirect_path,
        }
    )
    query = urlencode(
        {
            "client_id": settings.google_client_id,
            "redirect_uri": settings.google_oauth_redirect_uri,
            "response_type": "code",
            "scope": " ".join(GMAIL_SCOPES),
            "access_type": "offline",
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
    ensure_google_oauth_config()
    with httpx.Client(timeout=20.0) as client:
        response = client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_oauth_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="Unable to exchange Gmail OAuth code")
    return response.json()


def fetch_google_user_email(access_token: str) -> str:
    with httpx.Client(timeout=20.0) as client:
        response = client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="Unable to fetch Gmail account email")

    email_address = sanitize_email(response.json().get("email"))
    if not email_address:
        raise HTTPException(status_code=502, detail="Google OAuth did not return a valid email address")
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
    return existing


def test_imap_connection(*, imap_host: str, imap_port: int, username: str, password: str) -> None:
    mailbox: Any | None = None
    try:
        if imap_port == 993:
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
    except HTTPException:
        raise
    except imaplib.IMAP4.error as exc:
        raise HTTPException(status_code=400, detail="Unable to connect to the IMAP server with the provided credentials") from exc
    except Exception as exc:
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
    existing.is_active = True
    db.commit()
    db.refresh(existing)
    return existing


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
