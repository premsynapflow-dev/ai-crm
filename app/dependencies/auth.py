from typing import Optional

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth import resolve_current_client
from app.config import get_settings
from app.db.models import Client
from app.db.session import get_db

security = HTTPBearer()
settings = get_settings()


async def get_client_from_api_key(
    request: Request,
    x_api_key: str = Header(default="", alias="x-api-key"),
    db: Session = Depends(get_db)
) -> Optional[Client]:
    """Get client from API key header"""
    if x_api_key and x_api_key.strip():
        return db.query(Client).filter(
            Client.api_key == x_api_key.strip()
        ).first()

    return resolve_current_client(request, db, required=False)


async def require_api_key(
    request: Request,
    x_api_key: str = Header(default="", alias="x-api-key"),
    db: Session = Depends(get_db)
) -> Client:
    """Require a valid API key, or fall back to the signed-in session for the web app."""
    if x_api_key and x_api_key.strip():
        client = db.query(Client).filter(
            Client.api_key == x_api_key.strip()
        ).first()
        if not client:
            raise HTTPException(
                status_code=401,
                detail="Invalid API key"
            )
        return client

    client = resolve_current_client(request, db, required=False)
    if client is None:
        raise HTTPException(
            status_code=401,
            detail="Missing x-api-key header"
        )

    return client


async def get_current_admin_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Validate the simple admin bearer token configured in the environment."""
    token = credentials.credentials.strip()

    if not settings.admin_password or token != settings.admin_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials",
        )

    return {"username": settings.admin_username, "role": "admin"}
