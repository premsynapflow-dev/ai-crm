from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db.models import Client, Complaint
from app.db.session import get_db

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    complaints = db.query(Complaint).order_by(Complaint.created_at.desc()).all()
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"complaints": complaints},
    )


@router.get("/dashboard/clients", response_class=HTMLResponse)
def clients_dashboard(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    clients = db.query(Client).order_by(Client.created_at.desc()).all()
    return templates.TemplateResponse(
        request=request,
        name="clients.html",
        context={"clients": clients},
    )
