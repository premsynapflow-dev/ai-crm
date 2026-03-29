from typing import Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1.auth import decode_token
from app.config import get_settings
from app.db.models import Client, ClientUser
from app.db.session import SessionLocal, reset_current_client_context, set_current_client_context
from app.security.session import BadSignature, decode_session

settings = get_settings()


def resolve_client_id_from_request(request: Request) -> Optional[str]:
    state_client_id = getattr(request.state, "client_id", None)
    if state_client_id:
        return str(state_client_id)

    db = SessionLocal()
    try:
        api_key = (request.headers.get("x-api-key") or "").strip()
        if api_key:
            client = db.query(Client).filter(Client.api_key == api_key).first()
            if client:
                request.state.client_id = str(client.id)
                return str(client.id)

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
                user_id = session_data.get("user_id")
                user = db.query(ClientUser).filter(ClientUser.id == user_id).first()
                if user:
                    request.state.client_user_id = str(user.id)
                    request.state.client_id = str(user.client_id)
                    return str(user.client_id)

        authorization = request.headers.get("authorization", "")
        if authorization.lower().startswith("bearer "):
            token = authorization.split(" ", 1)[1]
            try:
                payload = decode_token(token, "access", settings.access_token_expire_minutes * 60)
            except Exception:
                payload = None
            if payload:
                user = db.query(ClientUser).filter(ClientUser.id == payload.get("sub")).first()
                if user:
                    request.state.client_user_id = str(user.id)
                    request.state.client_id = str(user.client_id)
                    return str(user.client_id)
    finally:
        db.close()

    return None


class RLSContextMiddleware(BaseHTTPMiddleware):
    """Expose request tenant identity to the DB session layer."""

    async def dispatch(self, request: Request, call_next):
        client_id = resolve_client_id_from_request(request)
        token = set_current_client_context(client_id)
        try:
            response = await call_next(request)
        finally:
            reset_current_client_context(token)
        return response
