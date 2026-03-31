from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field, ValidationError

from app.billing.plans import PLANS
from app.company_profile import RBI_REGULATED_SECTORS, is_rbi_regulated_sector
from app.db.models import Client, ClientUser, DemoRequest, WaitlistEntry
from app.db.session import SessionLocal
from app.onboarding.flows import apply_trial_plan, enqueue_welcome_sequence
from app.utils.security import generate_api_key, hash_password
from app.utils.request_parser import parse_request
from app.utils.sanitize import sanitize_phone

router = APIRouter(prefix="/api", tags=["public"])


class SignupRequest(BaseModel):
    company_name: str = Field(..., min_length=2)
    email: str
    password: str = Field(..., min_length=8)
    phone_number: str = Field(..., min_length=10)
    business_sector: str = Field(..., min_length=3)


class WaitlistRequest(BaseModel):
    email: str
    company_name: str | None = None


@router.post("/signup")
async def signup(request: Request):
    try:
        payload = SignupRequest(**(await parse_request(request)))
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc

    db = SessionLocal()
    client = None
    try:
        if payload.business_sector not in RBI_REGULATED_SECTORS:
            raise HTTPException(status_code=400, detail="Invalid business sector")

        phone_number = sanitize_phone(payload.phone_number)
        if not phone_number:
            raise HTTPException(status_code=400, detail="Invalid phone number")

        existing_user = db.query(ClientUser).filter(ClientUser.email == payload.email).first()
        if existing_user:
            raise HTTPException(status_code=409, detail="Account already exists")

        client = Client(
            name=payload.company_name,
            plan="starter",
            plan_id="starter",
            api_key=generate_api_key(32),
            contact_phone=phone_number,
            business_sector=payload.business_sector,
            is_rbi_regulated=is_rbi_regulated_sector(payload.business_sector),
            created_at=datetime.now(timezone.utc),
        )
        apply_trial_plan(client)
        db.add(client)
        db.commit()
        db.refresh(client)

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
        if client is not None:
            try:
                db.delete(client)
                db.commit()
            except Exception:
                db.rollback()
        raise
    finally:
        db.close()


@router.post("/waitlist")
async def waitlist(request: Request):
    try:
        payload = WaitlistRequest(**(await parse_request(request)))
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc

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
