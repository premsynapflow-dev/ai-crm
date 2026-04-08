from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi import HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth import get_current_client, get_current_client_user
from app.db.models import Client, ClientUser
from app.db.session import get_db
from app.inboxes import service as inbox_service
from app.inboxes.schemas import ConnectImapRequest, GmailConnectUrlResponse, InboxSummary
from app.utils.logging import get_logger

router = APIRouter(tags=["inboxes"])
logger = get_logger(__name__)


@router.get("/inboxes", response_model=list[InboxSummary])
def get_inboxes(
    client: Client = Depends(get_current_client),
    db: Session = Depends(get_db),
):
    return inbox_service.list_inboxes(db, tenant_id=client.id)


@router.get("/inboxes/gmail/connect-url", response_model=GmailConnectUrlResponse)
def get_gmail_connect_url(
    client: Client = Depends(get_current_client),
    user: ClientUser = Depends(get_current_client_user),
):
    connect_url = inbox_service.create_gmail_connect_url(client, user)
    logger.info("Gmail connect URL requested tenant=%s user=%s", client.id, user.id)
    return {"connect_url": connect_url, "url": connect_url}


@router.get("/auth/gmail/connect")
def connect_gmail(
    request: Request,
    connect_token: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    client, _user = inbox_service.resolve_gmail_connect_context(
        request,
        db,
        connect_token=connect_token,
        authorization=authorization,
    )
    redirect_url = inbox_service.build_google_redirect_url(tenant_id=str(client.id))
    return RedirectResponse(url=redirect_url, status_code=307)


@router.get("/auth/gmail/callback")
def gmail_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
):
    logger.info("Gmail OAuth callback received")
    if not code.strip():
        logger.warning("Gmail OAuth callback missing code")
        return RedirectResponse(url="/settings?gmail_error=true", status_code=307)
    try:
        oauth_state = inbox_service.load_oauth_state(state)
        token_payload = inbox_service.exchange_google_code(code)
        access_token = str(token_payload.get("access_token") or "").strip()
        if not access_token:
            raise HTTPException(status_code=502, detail="Google OAuth token response did not include an access token")
        email_address = inbox_service.fetch_google_user_email(access_token)
        inbox_service.upsert_gmail_inbox(
            db,
            tenant_id=oauth_state["tenant_id"],
            email_address=email_address,
            access_token=access_token,
            refresh_token=token_payload.get("refresh_token"),
            token_expiry=inbox_service.build_gmail_token_expiry(token_payload),
        )
        logger.info("Gmail inbox stored for tenant=%s email=%s", oauth_state["tenant_id"], email_address)
        return RedirectResponse(url=oauth_state["redirect_path"], status_code=307)
    except Exception as exc:
        logger.error("Gmail OAuth callback failed: %s", exc)
        return RedirectResponse(url="/settings?gmail_error=true", status_code=307)


def _connect_imap(
    payload: ConnectImapRequest,
    *,
    client: Client,
    db: Session,
) -> dict[str, Any]:
    email_address = inbox_service.normalize_email_address(payload.email)
    imap_host = (payload.imap_host or payload.host or "").strip()
    if not imap_host:
        inferred = inbox_service.infer_imap_host(email_address)
        if inferred:
            imap_host = inferred
        else:
            raise HTTPException(status_code=400, detail="IMAP host is required")

    imap_port = payload.port or payload.imap_port or 993
    use_ssl = payload.use_ssl if payload.use_ssl is not None else payload.imap_use_ssl
    username = (payload.username or email_address).strip()

    try:
        inbox_service.test_imap_connection(
            imap_host=imap_host,
            imap_port=imap_port,
            username=username,
            password=payload.password,
            use_ssl=bool(use_ssl),
        )
    except TypeError as exc:
        if "unexpected keyword argument 'use_ssl'" not in str(exc):
            raise
        inbox_service.test_imap_connection(
            imap_host=imap_host,
            imap_port=imap_port,
            username=username,
            password=payload.password,
        )
    inbox = inbox_service.upsert_imap_inbox(
        db,
        tenant_id=client.id,
        email_address=email_address,
        imap_host=imap_host,
        imap_port=imap_port,
        use_ssl=bool(use_ssl),
        username=username,
        password=payload.password,
    )
    return inbox_service.serialize_inbox(inbox)


@router.post("/inboxes/connect-imap", response_model=InboxSummary)
def connect_imap(
    payload: ConnectImapRequest,
    client: Client = Depends(get_current_client),
    db: Session = Depends(get_db),
):
    return _connect_imap(payload, client=client, db=db)


@router.post("/inboxes/imap/connect", response_model=InboxSummary)
def connect_imap_alias(
    payload: ConnectImapRequest,
    client: Client = Depends(get_current_client),
    db: Session = Depends(get_db),
):
    return _connect_imap(payload, client=client, db=db)
