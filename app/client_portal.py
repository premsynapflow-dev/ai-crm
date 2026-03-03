from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.db.models import ClientUser, Complaint
from app.db.session import get_db

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)


def _get_current_client_user(request: Request, db: Session) -> Optional[ClientUser]:
    user_id = request.session.get("client_user_id")
    if not user_id:
        return None
    return db.query(ClientUser).filter(ClientUser.id == user_id).first()


@router.get("/portal/login", response_class=HTMLResponse)
def portal_login_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="portal_login.html",
        context={"error": ""},
    )


@router.post("/portal/login", response_class=HTMLResponse)
def portal_login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(ClientUser).filter(ClientUser.email == email).first()
    if user and verify_password(password, user.password_hash):
        request.session["client_user_id"] = str(user.id)
        return RedirectResponse(url="/portal", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="portal_login.html",
        context={"error": "Invalid email or password"},
        status_code=401,
    )


@router.get("/portal/logout")
def portal_logout(request: Request):
    request.session.pop("client_user_id", None)
    return RedirectResponse(url="/portal/login", status_code=303)


@router.get("/portal", response_class=HTMLResponse)
def portal_home(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    user = _get_current_client_user(request, db)
    if not user:
        return RedirectResponse(url="/portal/login", status_code=303)

    complaints = (
        db.query(Complaint)
        .filter(Complaint.client_id == user.client_id)
        .order_by(Complaint.created_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        request=request,
        name="portal.html",
        context={"complaints": complaints, "user": user},
    )
