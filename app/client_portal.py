from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.billing.plan_application import apply_plan_to_client
from app.billing.plans import PLANS
from app.db.models import Client, ClientUser, Complaint, Invoice
from app.db.session import get_db
from app.integrations.slack import send_slack_alert
from app.replies.send_reply import ensure_manual_reply_review, send_complaint_reply
from app.services.auto_reply_hardened import HardenedAutoReplyService
from app.services.event_logger import log_event
from app.services.rbi_compliance import RBIComplianceService
from app.services.ticket_state_machine import TicketStateMachine
from app.security.passwords import verify_password
from app.security.session import BadSignature, create_session, decode_session
from app.services.timeline import build_ticket_timeline
from app.utils.request_parser import parse_request

router = APIRouter()


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


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@router.get("/portal/login")
def portal_login_page():
    return RedirectResponse(url="/login", status_code=302)


@router.post("/portal/login")
async def portal_login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(ClientUser).filter(ClientUser.email == email).first()
    if not user:
        return JSONResponse(
            status_code=401,
            content={"error": "Invalid email or password"},
        )

    try:
        password_ok = verify_password(password, user.password_hash)
    except Exception:
        password_ok = False

    if not password_ok:
        return JSONResponse(
            status_code=401,
            content={"error": "Invalid email or password"},
        )

    request.session["client_user_id"] = str(user.id)
    response = RedirectResponse(url="/app/complaints", status_code=303)
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
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("portal_session")
    return response


# ---------------------------------------------------------------------------
# Portal GET pages — redirect to Next.js equivalents
# ---------------------------------------------------------------------------

@router.get("/portal")
@router.get("/portal/complaints")
def portal_home():
    return RedirectResponse(url="/app/complaints", status_code=302)


@router.get("/portal/inbox")
def portal_inbox():
    return RedirectResponse(url="/app/complaints", status_code=302)


@router.get("/portal/leads")
def portal_leads():
    return RedirectResponse(url="/app/complaints?intent=sales_lead", status_code=302)


@router.get("/portal/analytics")
def portal_analytics():
    return RedirectResponse(url="/app/analytics", status_code=302)


@router.get("/portal/billing")
def portal_billing():
    return RedirectResponse(url="/app/billing", status_code=302)


@router.get("/portal/usage")
def portal_usage():
    return RedirectResponse(url="/app/billing", status_code=302)


@router.get("/portal/upgrade")
def portal_upgrade():
    return RedirectResponse(url="/app/billing", status_code=302)


@router.get("/portal/automation")
def portal_automation():
    return RedirectResponse(url="/app/settings/automations", status_code=302)


@router.get("/portal/ticket/{ticket_id}")
def portal_ticket(ticket_id: str):
    return RedirectResponse(url=f"/app/complaints?ticket_id={ticket_id}", status_code=302)


@router.get("/portal/settings")
def portal_settings():
    return RedirectResponse(url="/app/settings", status_code=302)


# ---------------------------------------------------------------------------
# Portal POST actions — keep business logic, update redirect destinations
# ---------------------------------------------------------------------------

@router.post("/portal/upgrade")
def portal_upgrade_submit(
    request: Request,
    plan_id: str = Form(...),
    db: Session = Depends(get_db),
):
    user = _get_current_client_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    client = db.query(Client).filter(Client.id == user.client_id).first()
    if not client or plan_id not in PLANS:
        return RedirectResponse(url="/app/billing", status_code=303)
    apply_plan_to_client(client, plan_id)
    db.commit()
    return RedirectResponse(url="/app/billing", status_code=303)


@router.get("/portal/invoice/{invoice_id}")
def portal_invoice_download(invoice_id: str, request: Request, db: Session = Depends(get_db)):
    user = _get_current_client_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    invoice = db.query(Invoice).filter(
        Invoice.id == invoice_id,
        Invoice.client_id == user.client_id,
    ).first()
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


@router.post("/portal/automation/create")
def create_rule(
    request: Request,
    trigger_type: str = Form(...),
    trigger_value: str = Form(...),
    action_type: str = Form(...),
    db: Session = Depends(get_db),
):
    user = _get_current_client_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    from app.db.models import AutomationRule

    rule = AutomationRule(
        client_id=user.client_id,
        trigger_type=trigger_type,
        trigger_value=trigger_value,
        action_type=action_type,
    )
    db.add(rule)
    db.commit()
    return RedirectResponse(url="/app/settings/automations", status_code=303)


@router.post("/portal/settings")
def portal_settings_submit(
    request: Request,
    slack_webhook_url: str = Form(default=""),
    db: Session = Depends(get_db),
):
    user = _get_current_client_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    client = db.query(Client).filter(Client.id == user.client_id).first()
    if not client:
        return RedirectResponse(url="/app/settings?error=Client+not+found", status_code=303)

    url = slack_webhook_url.strip()
    if url and not url.startswith("https://hooks.slack.com/"):
        return RedirectResponse(
            url="/app/settings?error=Invalid+Slack+webhook+URL",
            status_code=303,
        )

    client.slack_webhook_url = url or None
    db.commit()
    return RedirectResponse(url="/app/settings?saved=1", status_code=303)


# ---------------------------------------------------------------------------
# JSON endpoints — no template dependency, kept as-is
# ---------------------------------------------------------------------------

@router.get("/client/analytics/pulse")
def customer_pulse_endpoint(request: Request, db: Session = Depends(get_db)):
    user = _get_current_client_user(request, db)
    if not user:
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})

    from app.analytics.customer_pulse import generate_customer_pulse

    return generate_customer_pulse(db, user.client_id)


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
        return RedirectResponse(url="/login", status_code=303)

    complaint = db.query(Complaint).filter(
        Complaint.id == complaint_id,
        Complaint.client_id == user.client_id,
    ).first()
    client = db.query(Client).filter(Client.id == user.client_id).first()
    if not complaint or not client:
        return RedirectResponse(url=f"/app/complaints?ticket_id={ticket_id}", status_code=303)

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
    return RedirectResponse(url=f"/app/complaints?ticket_id={ticket_id}", status_code=303)


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
        return RedirectResponse(url="/login", status_code=303)

    complaint = db.query(Complaint).filter(
        Complaint.id == complaint_id,
        Complaint.client_id == user.client_id,
    ).first()
    client = db.query(Client).filter(Client.id == user.client_id).first()
    if not complaint or not client:
        return RedirectResponse(url=f"/app/complaints?ticket_id={ticket_id}", status_code=303)

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
    return RedirectResponse(url=f"/app/complaints?ticket_id={ticket_id}", status_code=303)


@router.post("/client/reply/escalate")
def escalate_ai_reply(
    request: Request,
    complaint_id: str = Form(...),
    ticket_id: str = Form(...),
    db: Session = Depends(get_db),
):
    user = _get_current_client_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

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

    return RedirectResponse(url=f"/app/complaints?ticket_id={ticket_id}", status_code=303)


@router.post("/portal/settings/test")
async def portal_settings_test(
    request: Request,
    db: Session = Depends(get_db),
) -> JSONResponse:
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

    lead.follow_up_status = "completed" if lead.follow_up_status == "pending" else "pending"
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
