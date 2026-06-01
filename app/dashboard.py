from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Client
from app.db.session import get_db
from app.dependencies.auth import get_current_admin_user

router = APIRouter()
settings = get_settings()


# ---------------------------------------------------------------------------
# Legacy admin — GET routes redirect to Next.js, POST routes return JSON
# ---------------------------------------------------------------------------

@router.get("/legacy-admin/login")
def login_page():
    return RedirectResponse(url="/login", status_code=302)


@router.post("/legacy-admin/login")
def login_submit(request: Request, username: str = Form(...), password: str = Form(...)):
    if username == settings.admin_username and password == settings.admin_password:
        request.session["admin"] = True
        return RedirectResponse(url="/dashboard", status_code=303)
    return JSONResponse(
        status_code=401,
        content={"error": "Invalid username or password"},
    )


@router.get("/legacy-admin/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


@router.get("/legacy-admin/dashboard")
def dashboard():
    return RedirectResponse(url="/dashboard", status_code=302)


@router.get("/legacy-admin/dashboard/clients")
def clients_dashboard():
    return RedirectResponse(url="/dashboard", status_code=302)


@router.post("/legacy-admin/create-client")
def create_client(
    name: str,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin_user),
):
    import secrets

    api_key = secrets.token_hex(24)
    client = Client(
        name=name,
        api_key=api_key,
        plan="starter",
        plan_id="starter",
        business_sector="not_rbi_regulated",
        is_rbi_regulated=False,
    )
    db.add(client)
    db.commit()
    return {"client_name": name, "api_key": api_key}
