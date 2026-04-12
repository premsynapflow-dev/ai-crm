from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.billing.plan_application import apply_plan_to_client
from app.billing.plans import PLANS
from app.billing.usage import get_usage_summary
from app.db.models import Client, ClientUser, Complaint, Invoice
from app.db.session import get_db
from app.integrations.slack import send_slack_alert
from app.replies.send_reply import ensure_manual_reply_review, send_complaint_reply
from app.services.auto_reply_hardened import HardenedAutoReplyService
from app.services.event_logger import log_event
from app.services.rbi_compliance import RBIComplianceService
from app.services.ticket_state_machine import TicketStateMachine
from app.security.passwords import hash_password, verify_password
from app.security.session import BadSignature, create_session, decode_session
from app.services.timeline import build_ticket_timeline
from app.utils.request_parser import parse_request

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _get_current_client_user(request: Request, db: Session) -> Optional[ClientUser]:
    user_id = request.session.get("client_user_id")
    if not user_id:
        session_token = request.cookies.get("portal_session")
        if session_token:
            try:
                data = decode_session(session_token)
                user_id = data.get("user_id")
                if user_id:
                    request.session["client_user_id"] = str(user_id)
            except BadSignature:
                return None
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
async def portal_login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(ClientUser).filter(ClientUser.email == email).first()
    if not user:
        return templates.TemplateResponse(
            request=request,
            name="portal_login.html",
            context={"error": "Invalid email or password"},
            status_code=401,
        )

    try:
        password_ok = verify_password(password, user.password_hash)
    except Exception:
        password_ok = False

    if not password_ok:
        return templates.TemplateResponse(
            request=request,
            name="portal_login.html",
            context={"error": "Invalid email or password"},
            status_code=401,
        )

    request.session["client_user_id"] = str(user.id)
    response = RedirectResponse(url="/portal", status_code=303)
    response.set_cookie(
        key="portal_session",
        value=create_session(str(user.id)),
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
    )
    return response

@router.get("/portal/logout")
def portal_logout(request: Request):
    request.session.pop("client_user_id", None)
    response = RedirectResponse(url="/portal/login", status_code=303)
    response.delete_cookie("portal_session")
    return response


@router.get("/portal", response_class=HTMLResponse)
@router.get("/portal/complaints", response_class=HTMLResponse)
def portal_home(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    user = _get_current_client_user(request, db)
    if not user:
        return RedirectResponse(url="/portal/login", status_code=303)

    from app.analytics.customer_pulse import generate_customer_pulse

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
    client = db.query(Client).filter(Client.id == user.client_id).first()
    usage_summary = get_usage_summary(user.client_id)
    invoices = (
        db.query(Invoice)
        .filter(Invoice.client_id == user.client_id)
        .order_by(Invoice.created_at.desc())
        .limit(5)
        .all()
    )
    ai_suggestions = (
        db.query(Complaint)
        .filter(
            Complaint.client_id == user.client_id,
            Complaint.ai_reply.isnot(None),
            Complaint.ai_reply_status.in_(["pending", "agent_review"]),
        )
        .order_by(Complaint.created_at.desc())
        .limit(5)
        .all()
    )
    pulse = generate_customer_pulse(db, user.client_id)
    monthly_limit = usage_summary.get("monthly_limit", 0) or 1
    upgrade_recommended = usage_summary.get("tickets_processed", 0) >= int(monthly_limit * 0.8)
    return templates.TemplateResponse(
        request=request,
        name="portal.html",
        context={
            "complaints": complaints,
            "user": user,
            "client": client,
            "plan": PLANS.get(client.plan_id if client else "free", PLANS["free"]),
            "usage_summary": usage_summary,
            "invoices": invoices,
            "upgrade_recommended": upgrade_recommended,
            "ai_suggestions": ai_suggestions,
            "pulse": pulse,
            "total_complaints": total_complaints,
            "total_leads": total_leads,
            "open_tickets": open_tickets,
            "resolved_tickets": resolved_tickets,
        },
    )


@router.get("/portal/inbox", response_class=HTMLResponse)
def portal_inbox(request: Request, db: Session = Depends(get_db)):
    user = _get_current_client_user(request, db)

    if not user:
        return RedirectResponse(url="/portal/login", status_code=303)

    grouped_tickets = (
        db.query(
            Complaint.ticket_id,
            func.max(Complaint.created_at).label("latest"),
            func.count(Complaint.id).label("messages")
        )
        .filter(Complaint.client_id == user.client_id)
        .group_by(Complaint.ticket_id)
        .order_by(func.max(Complaint.created_at).desc())
        .all()
    )

    tickets = []
    for ticket in grouped_tickets:
        latest_message = (
            db.query(Complaint)
            .filter(
                Complaint.client_id == user.client_id,
                Complaint.ticket_id == ticket.ticket_id,
            )
            .order_by(Complaint.created_at.desc())
            .first()
        )
        tickets.append(
            {
                "ticket_id": ticket.ticket_id,
                "latest": ticket.latest,
                "messages": ticket.messages,
                "last_message": latest_message.summary if latest_message else "-",
                "open_ticket": (latest_message.resolution_status == "open") if latest_message else False,
            }
        )

    return templates.TemplateResponse(
        request=request,
        name="portal_inbox.html",
        context={
            "tickets": tickets,
            "user": user,
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

    from app.analytics.customer_pulse import generate_customer_pulse
    from app.services.analytics import (
        analytics_overview,
        complaint_category_breakdown,
        sentiment_distribution,
        urgency_distribution,
        top_complaint_sources,
    )

    overview = analytics_overview(db, user.client_id)
    categories = complaint_category_breakdown(db, user.client_id)
    sentiment = sentiment_distribution(db, user.client_id)
    urgency = urgency_distribution(db, user.client_id)
    sources = top_complaint_sources(db, user.client_id)
    pulse = generate_customer_pulse(db, user.client_id)

    return templates.TemplateResponse(
        request=request,
        name="portal_analytics.html",
        context={
            "categories": categories,
            "sentiment": sentiment,
            "urgency": urgency,
            "sources": sources,
            "overview": overview,
            "pulse": pulse,
            "user": user,
        },
    )


@router.get("/client/analytics/pulse")
def customer_pulse_endpoint(request: Request, db: Session = Depends(get_db)):
    user = _get_current_client_user(request, db)
    if not user:
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})

    from app.analytics.customer_pulse import generate_customer_pulse

    return generate_customer_pulse(db, user.client_id)


@router.get("/portal/billing", response_class=HTMLResponse)
def portal_billing(request: Request, db: Session = Depends(get_db)):
    user = _get_current_client_user(request, db)
    if not user:
        return RedirectResponse(url="/portal/login", status_code=303)
    client = db.query(Client).filter(Client.id == user.client_id).first()
    invoices = (
        db.query(Invoice)
        .filter(Invoice.client_id == user.client_id)
        .order_by(Invoice.created_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        request=request,
        name="portal_billing.html",
        context={
            "user": user,
            "client": client,
            "plan": PLANS.get(client.plan_id if client else "free", PLANS["free"]),
            "invoices": invoices,
        },
    )


@router.get("/portal/usage", response_class=HTMLResponse)
def portal_usage(request: Request, db: Session = Depends(get_db)):
    user = _get_current_client_user(request, db)
    if not user:
        return RedirectResponse(url="/portal/login", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="portal_usage.html",
        context={
            "user": user,
            "usage_summary": get_usage_summary(user.client_id),
        },
    )


@router.get("/portal/upgrade", response_class=HTMLResponse)
def portal_upgrade(request: Request, db: Session = Depends(get_db)):
    user = _get_current_client_user(request, db)
    if not user:
        return RedirectResponse(url="/portal/login", status_code=303)
    client = db.query(Client).filter(Client.id == user.client_id).first()
    return templates.TemplateResponse(
        request=request,
        name="portal_upgrade.html",
        context={
            "user": user,
            "client": client,
            "plans": PLANS,
        },
    )


@router.post("/portal/upgrade", response_class=HTMLResponse)
def portal_upgrade_submit(request: Request, plan_id: str = Form(...), db: Session = Depends(get_db)):
    user = _get_current_client_user(request, db)
    if not user:
        return RedirectResponse(url="/portal/login", status_code=303)
    client = db.query(Client).filter(Client.id == user.client_id).first()
    if not client or plan_id not in PLANS:
        return RedirectResponse(url="/portal/upgrade", status_code=303)
    apply_plan_to_client(client, plan_id)
    db.commit()
    return RedirectResponse(url="/portal/billing", status_code=303)


@router.get("/portal/invoice/{invoice_id}")
def portal_invoice_download(invoice_id: str, request: Request, db: Session = Depends(get_db)):
    user = _get_current_client_user(request, db)
    if not user:
        return RedirectResponse(url="/portal/login", status_code=303)
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id, Invoice.client_id == user.client_id).first()
    if not invoice:
        return PlainTextResponse("Invoice not found", status_code=404)
    content = (
        f"Invoice Number: {invoice.invoice_number}\n"
        f"Status: {invoice.status}\n"
        f"Subtotal: {invoice.subtotal}\n"
        f"Tax: {invoice.tax}\n"
        f"Total: {invoice.total}\n"
        f"Payment Method: {invoice.payment_method or '-'}\n"
    )
    return PlainTextResponse(content, media_type="text/plain")


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

    from app.services.reply_generator import generate_reply

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
    timeline = build_ticket_timeline(db, user.client_id, ticket_id)
    latest_message = messages[-1] if messages else None
    suggested_reply = ""
    if latest_message and latest_message.ai_reply:
        suggested_reply = latest_message.ai_reply
    elif latest_message:
        suggested_reply = generate_reply(
            latest_message.summary,
            latest_message.intent,
            latest_message.category,
        )

    return templates.TemplateResponse(
        request=request,
        name="portal_ticket.html",
        context={
            "messages": messages,
            "ticket_id": ticket_id,
            "history": timeline,
            "timeline": timeline,
            "suggested_reply": suggested_reply,
            "latest_message": latest_message,
            "user": user,
        },
    )


@router.get("/client/ticket/{ticket_id}/timeline")
def ticket_timeline_endpoint(request: Request, ticket_id: str, db: Session = Depends(get_db)):
    user = _get_current_client_user(request, db)
    if not user:
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    return {"events": build_ticket_timeline(db, user.client_id, ticket_id)}


@router.post("/client/ai/suggest-reply")
async def suggest_ai_reply(
    request: Request,
    db: Session = Depends(get_db),
):
    user = _get_current_client_user(request, db)
    if not user:
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})

    body = await parse_request(request)
    complaint_id = body.get("complaint_id")
    ticket_id = body.get("ticket_id")
    complaint = None

    if complaint_id:
        complaint = db.query(Complaint).filter(
            Complaint.id == complaint_id,
            Complaint.client_id == user.client_id,
        ).first()
    elif ticket_id:
        complaint = (
            db.query(Complaint)
            .filter(
                Complaint.ticket_id == ticket_id,
                Complaint.client_id == user.client_id,
            )
            .order_by(Complaint.created_at.desc())
            .first()
        )

    if not complaint:
        return JSONResponse(status_code=404, content={"error": "Complaint not found"})

    queue_entry = HardenedAutoReplyService(db).generate_and_queue_reply(
        complaint,
        force_human_review=True,
        commit=False,
    )
    if queue_entry is None:
        db.commit()
        return {
            "reply_text": complaint.ai_reply or "",
            "confidence_score": complaint.ai_reply_confidence,
            "status": "skipped",
            "queue_id": None,
        }
    log_event(
        db,
        complaint.client_id,
        "ai_reply_regenerated",
        {
            "ticket_id": complaint.ticket_id,
            "complaint_id": str(complaint.id),
            "summary": complaint.ai_reply,
            "confidence": complaint.ai_reply_confidence,
            "queue_status": queue_entry.status,
        },
    )
    db.commit()
    return {
        "reply_text": complaint.ai_reply,
        "confidence_score": complaint.ai_reply_confidence,
        "status": queue_entry.status,
        "queue_id": str(queue_entry.id),
    }


@router.post("/client/reply/approve")
def approve_ai_reply(
    request: Request,
    complaint_id: str = Form(...),
    ticket_id: str = Form(...),
    db: Session = Depends(get_db),
):
    user = _get_current_client_user(request, db)
    if not user:
        return RedirectResponse(url="/portal/login", status_code=303)

    complaint = db.query(Complaint).filter(
        Complaint.id == complaint_id,
        Complaint.client_id == user.client_id,
    ).first()
    client = db.query(Client).filter(Client.id == user.client_id).first()
    if not complaint or not client:
        return RedirectResponse(url=f"/portal/ticket/{ticket_id}", status_code=303)

    queue_entry = complaint.reply_queue
    if queue_entry and queue_entry.status == "pending":
        HardenedAutoReplyService(db).approve_reply(
            str(queue_entry.id),
            reviewer_email=user.email,
            commit=False,
        )
    else:
        ensure_manual_reply_review(
            db,
            complaint,
            reviewer_email=user.email,
            reply_text=complaint.ai_reply or "",
        )
        send_complaint_reply(
            db=db,
            complaint=complaint,
            client=client,
            reply_text=complaint.ai_reply,
        )
    db.commit()
    return RedirectResponse(url=f"/portal/ticket/{ticket_id}", status_code=303)


@router.post("/client/reply/edit")
def edit_ai_reply(
    request: Request,
    complaint_id: str = Form(...),
    ticket_id: str = Form(...),
    reply_text: str = Form(...),
    db: Session = Depends(get_db),
):
    user = _get_current_client_user(request, db)
    if not user:
        return RedirectResponse(url="/portal/login", status_code=303)

    complaint = db.query(Complaint).filter(
        Complaint.id == complaint_id,
        Complaint.client_id == user.client_id,
    ).first()
    client = db.query(Client).filter(Client.id == user.client_id).first()
    if not complaint or not client:
        return RedirectResponse(url=f"/portal/ticket/{ticket_id}", status_code=303)

    complaint.ai_reply = reply_text.strip()
    queue_entry = complaint.reply_queue
    if queue_entry and queue_entry.status == "pending":
        HardenedAutoReplyService(db).approve_reply(
            str(queue_entry.id),
            reviewer_email=user.email,
            edited_reply=complaint.ai_reply,
            commit=False,
        )
    else:
        ensure_manual_reply_review(
            db,
            complaint,
            reviewer_email=user.email,
            reply_text=complaint.ai_reply,
        )
        send_complaint_reply(
            db=db,
            complaint=complaint,
            client=client,
            reply_text=complaint.ai_reply,
        )
    db.commit()
    return RedirectResponse(url=f"/portal/ticket/{ticket_id}", status_code=303)


@router.post("/client/reply/escalate")
def escalate_ai_reply(
    request: Request,
    complaint_id: str = Form(...),
    ticket_id: str = Form(...),
    db: Session = Depends(get_db),
):
    user = _get_current_client_user(request, db)
    if not user:
        return RedirectResponse(url="/portal/login", status_code=303)

    complaint = db.query(Complaint).filter(
        Complaint.id == complaint_id,
        Complaint.client_id == user.client_id,
    ).first()
    if complaint:
        queue_entry = complaint.reply_queue
        if queue_entry and queue_entry.status == "pending":
            HardenedAutoReplyService(db).reject_reply(
                str(queue_entry.id),
                reviewer_email=user.email,
                reason="Escalated to agent via client portal",
                commit=False,
            )
        complaint.ai_reply_status = "agent_review"
        complaint.status = "ESCALATE_HIGH"
        complaint.escalation_level = max(int(complaint.escalation_level or 0), 1)
        TicketStateMachine(db).sync_from_legacy(
            complaint,
            transitioned_by=user.email,
            reason="Manual escalation via client portal",
            metadata={"source": "client_portal"},
            commit=False,
        )
        HardenedAutoReplyService(db).record_feedback(
            complaint,
            escalated_after_reply=True,
            commit=False,
        )
        if complaint.rbi_complaint:
            RBIComplianceService(db).sync_from_complaint(complaint, commit=False)
        log_event(
            db,
            complaint.client_id,
            "agent_escalation",
            {
                "ticket_id": complaint.ticket_id,
                "complaint_id": str(complaint.id),
                "summary": complaint.summary,
            },
        )
        db.commit()

    return RedirectResponse(url=f"/portal/ticket/{ticket_id}", status_code=303)


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
async def portal_settings_test(
    request: Request,
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Send a test Slack alert to the URL provided in the request body."""
    user = _get_current_client_user(request, db)
    if not user:
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})

    try:
        body = await parse_request(request)
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid request"})

    url = body.get("slack_webhook_url", "").strip()
    if not url or not url.startswith("https://hooks.slack.com/"):
        return JSONResponse(status_code=400, content={"error": "Invalid URL"})

    try:
        send_slack_alert(
            text=(
                "*SynapFlow test alert*\n"
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
        complaint.status = "RESOLVED"
        if complaint.resolved_at is None:
            from datetime import datetime, timezone

            complaint.resolved_at = datetime.now(timezone.utc)
    else:
        complaint.resolution_status = "open"
        complaint.status = "IN_PROGRESS"
        complaint.resolved_at = None
        HardenedAutoReplyService(db).record_feedback(
            complaint,
            ticket_reopened=True,
            commit=False,
        )

    TicketStateMachine(db).sync_from_legacy(
        complaint,
        transitioned_by=user.email,
        reason="Resolution toggled via client portal",
        metadata={"source": "client_portal"},
        commit=False,
    )
    if complaint.rbi_complaint:
        RBIComplianceService(db).sync_from_complaint(complaint, commit=False)

    db.commit()

    return {"status": "ok"}
