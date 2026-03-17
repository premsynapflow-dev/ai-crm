from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import ClientUser
from app.db.session import get_db
from app.security.passwords import verify_password

router = APIRouter(prefix="/api/v1/auth", tags=["api-auth"])
settings = get_settings()
serializer = URLSafeTimedSerializer(settings.jwt_secret_key or settings.secret_key)


class LoginRequest(BaseModel):
    email: str
    password: str = Field(..., min_length=8)


class RefreshRequest(BaseModel):
    refresh_token: str


def _create_token(data: dict, salt: str):
    return serializer.dumps(data, salt=salt)


def decode_token(token: str, salt: str, max_age: int):
    return serializer.loads(token, salt=salt, max_age=max_age)


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(ClientUser).filter(ClientUser.email == payload.email).first()
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
