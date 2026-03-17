import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.billing.plans import PLANS
from app.client_portal import hash_password
from app.db.models import Client, ClientUser, DemoRequest, WaitlistEntry
from app.db.session import SessionLocal
from app.onboarding.flows import apply_trial_plan, enqueue_welcome_sequence

router = APIRouter(prefix="/api", tags=["public"])


class SignupRequest(BaseModel):
    company_name: str = Field(..., min_length=2)
    email: str
    password: str = Field(..., min_length=8)


class WaitlistRequest(BaseModel):
    email: str
    company_name: str | None = None


@router.post("/signup")
def signup(payload: SignupRequest):
    db = SessionLocal()
    try:
        existing_user = db.query(ClientUser).filter(ClientUser.email == payload.email).first()
        if existing_user:
            raise HTTPException(status_code=409, detail="Account already exists")

        client = Client(
            name=payload.company_name,
            api_key=secrets.token_hex(24),
            created_at=datetime.now(timezone.utc),
        )
        apply_trial_plan(client)
        db.add(client)
        db.flush()

        user = ClientUser(
            client_id=client.id,
            email=payload.email,
            password_hash=hash_password(payload.password),
        )
        db.add(user)
        db.commit()
        enqueue_welcome_sequence(client, payload.email)
        return {
            "status": "created",
            "plan": PLANS[client.plan_id]["name"],
            "api_key": client.api_key,
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/waitlist")
def waitlist(payload: WaitlistRequest):
    db = SessionLocal()
    try:
        entry = WaitlistEntry(email=payload.email, details={"company_name": payload.company_name})
        db.add(entry)
        db.commit()
        return {"status": "ok"}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.get("/demo")
def demo(email: str | None = None, name: str | None = None, company: str | None = None):
    if email:
        db = SessionLocal()
        try:
            db.add(DemoRequest(email=email, name=name, company=company))
            db.commit()
        finally:
            db.close()
    return {"booking_url": "https://calendar.google.com/", "status": "ok"}
