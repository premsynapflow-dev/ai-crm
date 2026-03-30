from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Client, Complaint
from app.db.session import get_db

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
settings = get_settings()


def _is_admin_authenticated(request: Request) -> bool:
    return bool(request.session.get("admin"))


@router.get("/legacy-admin/login", response_class=HTMLResponse)
def login_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": ""},
    )


@router.post("/legacy-admin/login", response_class=HTMLResponse)
def login_submit(request: Request, username: str = Form(...), password: str = Form(...)):
    if username == settings.admin_username and password == settings.admin_password:
        request.session["admin"] = True
        return RedirectResponse(url="/legacy-admin/dashboard", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": "Invalid username or password"},
        status_code=401,
    )


@router.get("/legacy-admin/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/legacy-admin/login", status_code=303)


@router.get("/legacy-admin/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    if not _is_admin_authenticated(request):
        return RedirectResponse(url="/legacy-admin/login", status_code=303)

    complaints = db.query(Complaint).order_by(Complaint.created_at.desc()).all()
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"complaints": complaints},
    )


@router.get("/legacy-admin/dashboard/clients", response_class=HTMLResponse)
def clients_dashboard(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    if not _is_admin_authenticated(request):
        return RedirectResponse(url="/legacy-admin/login", status_code=303)

    clients = db.query(Client).order_by(Client.created_at.desc()).all()
    return templates.TemplateResponse(
        request=request,
        name="clients.html",
        context={"clients": clients},
    )


@router.post("/legacy-admin/create-client")
def create_client(name: str, db: Session = Depends(get_db)):
    import secrets

    api_key = secrets.token_hex(24)

    client = Client(
        name=name,
        api_key=api_key,
        plan="basic",
    )

    db.add(client)
    db.commit()

    return {
        "client_name": name,
        "api_key": api_key,
    }
