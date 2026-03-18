from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth import serialize_client_user
from app.config import get_settings
from app.db.models import Client, ClientUser
from app.db.session import get_db
from app.security.passwords import verify_password
from app.security.session import create_session

router = APIRouter(prefix="/auth", tags=["session-auth"])
settings = get_settings()


@router.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(ClientUser).filter(ClientUser.email == username).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    try:
        password_ok = verify_password(password, user.password_hash)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid credentials") from exc

    if not password_ok:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    client = db.query(Client).filter(Client.id == user.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    request.session["client_user_id"] = str(user.id)
    response = JSONResponse({"user": serialize_client_user(user, client)})
    response.set_cookie(
        key="session_token",
        value=create_session(str(user.id)),
        httponly=True,
        secure=settings.is_production() or request.url.scheme == "https",
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
    )
    return response


@router.post("/logout")
def logout(request: Request):
    request.session.pop("client_user_id", None)
    response = JSONResponse({"ok": True})
    response.delete_cookie("session_token")
    response.delete_cookie("portal_session")
    return response
