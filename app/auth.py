from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Client, ClientUser
from app.db.session import get_db
from app.security.session import BadSignature, decode_session

settings = get_settings()


def _normalize_user_id(value: str | UUID | None) -> UUID | str | None:
    if value in (None, ""):
        return None

    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return value


def _display_name_from_email(email: str, fallback: str) -> str:
    local_part = (email or "").split("@", 1)[0].replace(".", " ").replace("_", " ").strip()
    if local_part:
        return " ".join(part.capitalize() for part in local_part.split())
    return fallback


def serialize_client_user(user: ClientUser, client: Client) -> dict[str, str | bool | None]:
    return {
        "id": str(user.id),
        "email": user.email,
        "name": _display_name_from_email(user.email, client.name),
        "company": client.name,
        "company_phone": client.contact_phone,
        "business_sector": client.business_sector,
        "is_rbi_regulated": bool(client.is_rbi_regulated),
        "plan": client.plan_id,
        "plan_id": client.plan_id,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def resolve_current_client_user(
    request: Request,
    db: Session,
    *,
    x_session_token: str | None = None,
    authorization: str | None = None,
    required: bool = True,
) -> ClientUser | None:
    user_id = _normalize_user_id(request.session.get("client_user_id"))
    session_token = x_session_token or request.cookies.get("session_token") or request.cookies.get("portal_session")

    if not user_id and session_token:
        try:
            data = decode_session(session_token)
        except BadSignature as exc:
            if not required:
                return None
            raise HTTPException(status_code=401, detail="Invalid session") from exc

        user_id = _normalize_user_id(data.get("user_id"))
        if user_id:
            request.session["client_user_id"] = str(user_id)

    if not user_id and authorization and authorization.lower().startswith("bearer "):
        from app.api.v1.auth import decode_token

        token = authorization.split(" ", 1)[1]
        try:
            data = decode_token(token, "access", settings.access_token_expire_minutes * 60)
        except Exception as exc:
            if not required:
                return None
            raise HTTPException(status_code=401, detail="Invalid token") from exc

        user_id = _normalize_user_id(data.get("sub"))

    if not user_id:
        if required:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return None

    user = db.query(ClientUser).filter(ClientUser.id == user_id).first()
    if not user:
        request.session.pop("client_user_id", None)
        if required:
            raise HTTPException(status_code=401, detail="User not found")
        return None

    request.state.client_user_id = str(user.id)
    request.state.client_id = str(user.client_id)
    return user


def resolve_current_client(
    request: Request,
    db: Session,
    *,
    x_session_token: str | None = None,
    authorization: str | None = None,
    required: bool = True,
) -> Client | None:
    user = resolve_current_client_user(
        request,
        db,
        x_session_token=x_session_token,
        authorization=authorization,
        required=required,
    )
    if user is None:
        return None

    client = db.query(Client).filter(Client.id == user.client_id).first()
    if not client:
        if required:
            raise HTTPException(status_code=404, detail="Client not found")
        return None

    request.state.client_id = str(client.id)
    return client


def get_current_client_user(
    request: Request,
    db: Session = Depends(get_db),
    x_session_token: str | None = Header(default=None, alias="x-session-token"),
    authorization: str | None = Header(default=None),
) -> ClientUser:
    return resolve_current_client_user(
        request,
        db,
        x_session_token=x_session_token,
        authorization=authorization,
        required=True,
    )


def get_current_client(
    request: Request,
    db: Session = Depends(get_db),
    x_session_token: str | None = Header(default=None, alias="x-session-token"),
    authorization: str | None = Header(default=None),
) -> Client:
    return resolve_current_client(
        request,
        db,
        x_session_token=x_session_token,
        authorization=authorization,
        required=True,
    )
