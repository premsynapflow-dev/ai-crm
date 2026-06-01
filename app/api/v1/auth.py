import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import ClientUser, PasswordResetOTP
from app.db.session import get_db
from app.integrations.email import send_email
from app.security.passwords import hash_password, verify_password

router = APIRouter(prefix="/api/v1/auth", tags=["api-auth"])
settings = get_settings()
serializer = URLSafeTimedSerializer(settings.jwt_secret_key or settings.secret_key)
OTP_TTL_MINUTES = 10
MAX_OTP_ATTEMPTS = 5


class LoginRequest(BaseModel):
    email: str
    password: str = Field(..., min_length=8)


class RefreshRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    email: str
    otp: str = Field(..., min_length=6, max_length=6)
    new_password: str = Field(..., min_length=8)


def _create_token(data: dict, salt: str):
    return serializer.dumps(data, salt=salt)


def decode_token(token: str, salt: str, max_age: int):
    return serializer.loads(token, salt=salt, max_age=max_age)


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _hash_otp(otp: str) -> str:
    secret = (settings.jwt_secret_key or settings.secret_key).encode("utf-8")
    return hmac.new(secret, otp.encode("utf-8"), hashlib.sha256).hexdigest()


def _otp_matches(otp: str, otp_hash: str) -> bool:
    return hmac.compare_digest(_hash_otp(otp), otp_hash)


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(ClientUser).filter(func.lower(ClientUser.email) == _normalize_email(payload.email)).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    try:
        password_ok = verify_password(payload.password, user.password_hash)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid credentials") from exc
    if not password_ok:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    now = datetime.now(timezone.utc)
    access_token = _create_token({"sub": str(user.id), "type": "access", "iat": now.isoformat()}, "access")
    refresh_token = _create_token({"sub": str(user.id), "type": "refresh", "iat": now.isoformat()}, "refresh")
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * 60,
    }


@router.post("/refresh")
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    try:
        data = decode_token(payload.refresh_token, "refresh", settings.refresh_token_expire_days * 86400)
    except (BadSignature, SignatureExpired):
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user = db.query(ClientUser).filter(ClientUser.id == data.get("sub")).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    access_token = _create_token({"sub": str(user.id), "type": "access"}, "access")
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    if not (settings.resend_api_key or settings.smtp_host):
        raise HTTPException(status_code=503, detail="Email delivery is not configured")

    email = _normalize_email(payload.email)
    user = db.query(ClientUser).filter(func.lower(ClientUser.email) == email).first()
    if not user:
        return {"message": "If that account exists, a password reset OTP has been sent."}

    now = datetime.now(timezone.utc)
    db.query(PasswordResetOTP).filter(
        PasswordResetOTP.user_id == user.id,
        PasswordResetOTP.used_at.is_(None),
    ).update({"used_at": now}, synchronize_session=False)

    otp = _generate_otp()
    reset_otp = PasswordResetOTP(
        user_id=user.id,
        email=email,
        otp_hash=_hash_otp(otp),
        expires_at=now + timedelta(minutes=OTP_TTL_MINUTES),
    )
    db.add(reset_otp)

    try:
        sent = send_email(
            to_email=email,
            subject="Your SynapFlow password reset OTP",
            body=(
                "Use this OTP to reset your SynapFlow password:\n\n"
                f"{otp}\n\n"
                f"This OTP expires in {OTP_TTL_MINUTES} minutes. If you did not request this, you can ignore this email."
            ),
        )
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Unable to send password reset OTP") from exc

    if not sent:
        db.rollback()
        raise HTTPException(status_code=503, detail="Unable to send password reset OTP")

    db.commit()
    return {"message": "If that account exists, a password reset OTP has been sent."}


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    email = _normalize_email(payload.email)
    user = db.query(ClientUser).filter(func.lower(ClientUser.email) == email).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")

    now = datetime.now(timezone.utc)
    reset_otp = (
        db.query(PasswordResetOTP)
        .filter(
            PasswordResetOTP.user_id == user.id,
            PasswordResetOTP.email == email,
            PasswordResetOTP.used_at.is_(None),
            PasswordResetOTP.expires_at > now,
        )
        .order_by(PasswordResetOTP.created_at.desc())
        .first()
    )
    if not reset_otp:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")

    if reset_otp.attempts >= MAX_OTP_ATTEMPTS:
        reset_otp.used_at = now
        db.commit()
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")

    if not _otp_matches(payload.otp.strip(), reset_otp.otp_hash):
        reset_otp.attempts += 1
        db.commit()
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")

    user.password_hash = hash_password(payload.new_password)
    reset_otp.used_at = now
    db.commit()
    return {"message": "Password reset successful"}
