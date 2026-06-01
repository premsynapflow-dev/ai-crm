import time
import threading
from uuid import UUID

from typing import Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1.auth import decode_token
from app.config import get_settings
from app.db.models import Client, ClientUser
from app.db.session import SessionLocal, reset_current_client_context, set_current_client_context
from app.security.session import BadSignature, decode_session

settings = get_settings()

# Paths that don't carry tenant identity — skip DB lookup entirely
_SKIP_PREFIXES = ("/_next/", "/public/", "/favicon.ico", "/health", "/metrics", "/static/")

# TTL cache: avoid a DB round-trip on every request for the same API key / user ID
# Entries expire after 5 minutes so key rotation and user changes take effect promptly
_CACHE_TTL = 300
_api_key_cache: dict[str, tuple[str, float]] = {}   # api_key  → (client_id_str, expires_at)
_user_id_cache: dict[str, tuple[str, float]] = {}   # user_id_str → (client_id_str, expires_at)
_cache_lock = threading.Lock()


def _cache_get(store: dict, key: str) -> str | None:
    with _cache_lock:
        entry = store.get(key)
    if entry and entry[1] > time.monotonic():
        return entry[0]
    if entry:
        with _cache_lock:
            store.pop(key, None)
    return None


def _cache_set(store: dict, key: str, value: str) -> None:
    with _cache_lock:
        store[key] = (value, time.monotonic() + _CACHE_TTL)


def _normalize_user_id(value: str | UUID | None) -> UUID | str | None:
    if value in (None, ""):
        return None

    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return value


def resolve_client_id_from_request(request: Request) -> Optional[str]:
    # Fast path: already resolved earlier in this request
    state_client_id = getattr(request.state, "client_id", None)
    if state_client_id:
        return str(state_client_id)

    # --- API key ---
    api_key = (request.headers.get("x-api-key") or "").strip()
    if api_key:
        cached = _cache_get(_api_key_cache, api_key)
        if cached:
            request.state.client_id = cached
            return cached
        db = SessionLocal()
        try:
            client = db.query(Client).filter(Client.api_key == api_key).first()
            if client:
                client_id_str = str(client.id)
                _cache_set(_api_key_cache, api_key, client_id_str)
                request.state.client_id = client_id_str
                return client_id_str
        finally:
            db.close()
        return None

    # --- Session cookie / x-session-token ---
    session_token = (
        request.headers.get("x-session-token")
        or request.cookies.get("session_token")
        or request.cookies.get("portal_session")
    )
    if session_token:
        try:
            session_data = decode_session(session_token)
        except BadSignature:
            session_data = None
        if session_data:
            user_id = _normalize_user_id(session_data.get("user_id"))
            user_id_str = str(user_id) if user_id else None
            if user_id_str:
                cached = _cache_get(_user_id_cache, user_id_str)
                if cached:
                    request.state.client_user_id = user_id_str
                    request.state.client_id = cached
                    return cached
                db = SessionLocal()
                try:
                    user = db.query(ClientUser).filter(ClientUser.id == user_id).first()
                    if user:
                        client_id_str = str(user.client_id)
                        _cache_set(_user_id_cache, user_id_str, client_id_str)
                        request.state.client_user_id = str(user.id)
                        request.state.client_id = client_id_str
                        return client_id_str
                finally:
                    db.close()

    # --- Bearer JWT ---
    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1]
        try:
            payload = decode_token(token, "access", settings.access_token_expire_minutes * 60)
        except Exception:
            payload = None
        if payload:
            user_id = _normalize_user_id(payload.get("sub"))
            user_id_str = str(user_id) if user_id else None
            if user_id_str:
                cached = _cache_get(_user_id_cache, user_id_str)
                if cached:
                    request.state.client_user_id = user_id_str
                    request.state.client_id = cached
                    return cached
                db = SessionLocal()
                try:
                    user = db.query(ClientUser).filter(ClientUser.id == user_id).first()
                    if user:
                        client_id_str = str(user.client_id)
                        _cache_set(_user_id_cache, user_id_str, client_id_str)
                        request.state.client_user_id = str(user.id)
                        request.state.client_id = client_id_str
                        return client_id_str
                finally:
                    db.close()

    return None


class RLSContextMiddleware(BaseHTTPMiddleware):
    """Expose request tenant identity to the DB session layer."""

    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith(_SKIP_PREFIXES):
            return await call_next(request)

        client_id = resolve_client_id_from_request(request)
        token = set_current_client_context(client_id)
        try:
            response = await call_next(request)
        finally:
            reset_current_client_context(token)
        return response
