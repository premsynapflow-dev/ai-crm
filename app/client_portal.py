from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from passlib.context import CryptContext
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import Client, ClientUser, Complaint
from app.db.session import get_db
from app.integrations.slack import send_slack_alert

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
@router.get("/portal/complaints", response_class=HTMLResponse)
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
    total_complaints = db.query(func.count(Complaint.id)).filter(
        Complaint.client_id == user.client_id
    ).scalar()
    total_leads = db.query(func.count(Complaint.id)).filter(
        Complaint.client_id == user.client_id,
        Complaint.intent == "sales_lead",
    ).scalar()
    open_tickets = db.query(func.count(func.distinct(Complaint.ticket_id))).filter(
        Complaint.client_id == user.client_id,
        Complaint.resolution_status == "open",
    ).scalar()
    resolved_tickets = db.query(func.count(func.distinct(Complaint.ticket_id))).filter(
        Complaint.client_id == user.client_id,
        Complaint.resolution_status == "resolved",
    ).scalar()
    return templates.TemplateResponse(
        request=request,
        name="portal.html",
        context={
            "complaints": complaints,
            "user": user,
            "total_complaints": total_complaints,
            "total_leads": total_leads,
            "open_tickets": open_tickets,
            "resolved_tickets": resolved_tickets,
        },
    )


@router.get("/portal/leads", response_class=HTMLResponse)
def portal_leads(request: Request, db: Session = Depends(get_db)):
    user = _get_current_client_user(request, db)
    if not user:
        return RedirectResponse(url="/portal/login", status_code=303)

    leads = (
        db.query(Complaint)
        .filter(
            Complaint.client_id == user.client_id,
            Complaint.intent == "sales_lead"
        )
        .order_by(Complaint.created_at.desc())
        .all()
    )

    return templates.TemplateResponse(
        request=request,
        name="portal_leads.html",
        context={
            "leads": leads,
            "user": user,
        }
    )


@router.get("/portal/analytics", response_class=HTMLResponse)
def portal_analytics(request: Request, db: Session = Depends(get_db)):
    user = _get_current_client_user(request, db)
    if not user:
        return RedirectResponse(url="/portal/login", status_code=303)

    from app.services.analytics import (
        complaint_category_breakdown,
        sentiment_distribution,
        urgency_distribution,
        top_complaint_sources,
    )

    categories = complaint_category_breakdown(db, user.client_id)
    sentiment = sentiment_distribution(db, user.client_id)
    urgency = urgency_distribution(db, user.client_id)
    sources = top_complaint_sources(db, user.client_id)

    return templates.TemplateResponse(
        request=request,
        name="portal_analytics.html",
        context={
            "categories": categories,
            "sentiment": sentiment,
            "urgency": urgency,
            "sources": sources,
            "user": user,
        },
    )


@router.get("/portal/automation", response_class=HTMLResponse)
def portal_automation(request: Request, db: Session = Depends(get_db)):
    user = _get_current_client_user(request, db)

    if not user:
        return RedirectResponse(url="/portal/login", status_code=303)

    from app.db.models import AutomationRule

    rules = db.query(AutomationRule).filter(
        AutomationRule.client_id == user.client_id
    ).all()

    return templates.TemplateResponse(
        request=request,
        name="portal_automation.html",
        context={
            "rules": rules,
            "user": user,
        },
    )


@router.post("/portal/automation/create")
def create_rule(
    request: Request,
    trigger_type: str = Form(...),
    trigger_value: str = Form(...),
    action_type: str = Form(...),
    db: Session = Depends(get_db)
):
    user = _get_current_client_user(request, db)
    if not user:
        return RedirectResponse(url="/portal/login", status_code=303)

    from app.db.models import AutomationRule

    rule = AutomationRule(
        client_id=user.client_id,
        trigger_type=trigger_type,
        trigger_value=trigger_value,
        action_type=action_type
    )

    db.add(rule)

    db.commit()

    return RedirectResponse(url="/portal/automation", status_code=303)


@router.get("/portal/ticket/{ticket_id}", response_class=HTMLResponse)
def portal_ticket(request: Request, ticket_id: str, db: Session = Depends(get_db)):
    user = _get_current_client_user(request, db)

    if not user:
        return RedirectResponse(url="/portal/login", status_code=303)

    from app.services.customer_history import get_customer_history

    messages = (
        db.query(Complaint)
        .filter(
            Complaint.client_id == user.client_id,
            Complaint.ticket_id == ticket_id,
        )
        .order_by(Complaint.created_at)
        .all()
    )

    customer_email = messages[0].customer_email if messages else None
    history = get_customer_history(db, customer_email)

    return templates.TemplateResponse(
        request=request,
        name="portal_ticket.html",
        context={
            "messages": messages,
            "ticket_id": ticket_id,
            "history": history,
            "user": user,
        },
    )


@router.get("/portal/settings", response_class=HTMLResponse)
def portal_settings(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    user = _get_current_client_user(request, db)
    if not user:
        return RedirectResponse(url="/portal/login", status_code=303)

    client = db.query(Client).filter(Client.id == user.client_id).first()
    return templates.TemplateResponse(
        request=request,
        name="portal_settings.html",
        context={
            "user": user,
            "client": client,
            "saved": request.query_params.get("saved") == "1",
            "error": request.query_params.get("error", ""),
        },
    )


@router.post("/portal/settings", response_class=HTMLResponse)
def portal_settings_submit(
    request: Request,
    slack_webhook_url: str = Form(default=""),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    user = _get_current_client_user(request, db)
    if not user:
        return RedirectResponse(url="/portal/login", status_code=303)

    client = db.query(Client).filter(Client.id == user.client_id).first()
    if not client:
        return RedirectResponse(url="/portal/settings?error=Client+not+found", status_code=303)

    # Basic validation - must start with https://hooks.slack.com or be empty
    url = slack_webhook_url.strip()
    if url and not url.startswith("https://hooks.slack.com/"):
        return RedirectResponse(
            url="/portal/settings?error=Invalid+Slack+webhook+URL",
            status_code=303,
        )

    client.slack_webhook_url = url or None
    db.commit()
    return RedirectResponse(url="/portal/settings?saved=1", status_code=303)


@router.post("/portal/settings/test")
def portal_settings_test(
    request: Request,
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Send a test Slack alert to the URL provided in the request body."""
    user = _get_current_client_user(request, db)
    if not user:
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})

    import asyncio
    import json as _json

    body = {}
    try:
        raw = asyncio.run(request.body())
        body = _json.loads(raw)
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid request"})

    url = body.get("slack_webhook_url", "").strip()
    if not url or not url.startswith("https://hooks.slack.com/"):
        return JSONResponse(status_code=400, content={"error": "Invalid URL"})

    try:
        send_slack_alert(
            text=(
                "*Neuronyx test alert*\n"
                "Your Slack integration is working correctly.\n"
                "Sales leads and high-priority complaints will appear here."
            ),
            webhook_url=url,
        )
        return JSONResponse(content={"ok": True})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.post("/portal/lead/{id}/toggle")
def toggle_lead(id: str, request: Request, db: Session = Depends(get_db)):
    user = _get_current_client_user(request, db)
    if not user:
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})

    lead = db.query(Complaint).filter(
        Complaint.id == id,
        Complaint.client_id == user.client_id,
    ).first()
    if not lead:
        return JSONResponse(status_code=404, content={"error": "Lead not found"})

    if lead.follow_up_status == "pending":
        lead.follow_up_status = "completed"
    else:
        lead.follow_up_status = "pending"

    db.commit()

    return {"status": "ok"}


@router.post("/portal/complaint/{id}/resolve")
def resolve_complaint(id: str, request: Request, db: Session = Depends(get_db)):
    user = _get_current_client_user(request, db)
    if not user:
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})

    complaint = db.query(Complaint).filter(
        Complaint.id == id,
        Complaint.client_id == user.client_id,
    ).first()
    if not complaint:
        return JSONResponse(status_code=404, content={"error": "Complaint not found"})

    if complaint.resolution_status == "open":
        complaint.resolution_status = "resolved"
    else:
        complaint.resolution_status = "open"

    db.commit()

    return {"status": "ok"}
