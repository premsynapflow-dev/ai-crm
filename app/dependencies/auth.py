from typing import Optional
from fastapi import Header, HTTPException, Depends
from sqlalchemy.orm import Session

from app.db.models import Client
from app.db.session import get_db


async def get_client_from_api_key(
    x_api_key: str = Header(default="", alias="x-api-key"),
    db: Session = Depends(get_db)
) -> Optional[Client]:
    """Get client from API key header"""
    if not x_api_key or not x_api_key.strip():
        return None
    
    client = db.query(Client).filter(
        Client.api_key == x_api_key.strip()
    ).first()
    
    return client


async def require_api_key(
    x_api_key: str = Header(alias="x-api-key"),
    db: Session = Depends(get_db)
) -> Client:
    """Require valid API key or raise 401"""
    if not x_api_key or not x_api_key.strip():
        raise HTTPException(
            status_code=401,
            detail="Missing x-api-key header"
        )
    
    client = db.query(Client).filter(
        Client.api_key == x_api_key.strip()
    ).first()
    
    if not client:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )
    
    return client
