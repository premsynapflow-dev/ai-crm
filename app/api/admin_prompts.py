"""
Admin-only API for managing custom AI prompts
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Client
from app.db.session import get_db

router = APIRouter(prefix="/api/admin/prompts", tags=["admin"])
settings = get_settings()


class PromptConfigUpdate(BaseModel):
    """Template-based prompt configuration"""
    tone: str = Field(..., pattern="^(professional|friendly|empathetic|formal)$")
    focus_areas: list[str] = Field(..., min_items=1, max_items=10)
    classification_rules: dict = Field(default_factory=dict)
    reply_guidelines: dict = Field(default_factory=dict)
    industry: str = Field(
        default="general",
        pattern="^(ecommerce|saas|healthcare|finance|education|general)$",
    )


def verify_admin_password(admin_password: str = Header(alias="X-Admin-Password")):
    """Verify admin password from header"""
    if admin_password != settings.admin_password:
        raise HTTPException(401, "Invalid admin password")
    return True


@router.get("/{client_id}")
def get_client_prompt(
    client_id: str,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_password),
):
    """Get current prompt config for a client"""
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(404, "Client not found")

    return {
        "client_id": str(client.id),
        "client_name": client.name,
        "custom_prompt_enabled": client.custom_prompt_enabled,
        "custom_prompt_config": client.custom_prompt_config,
        "updated_at": client.custom_prompt_updated_at.isoformat() if client.custom_prompt_updated_at else None,
    }


@router.put("/{client_id}")
def update_client_prompt(
    client_id: str,
    config: PromptConfigUpdate,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_password),
):
    """Set or update custom prompt for a client"""
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(404, "Client not found")

    # Update config
    client.custom_prompt_enabled = True
    client.custom_prompt_config = config.dict()
    client.custom_prompt_updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(client)

    return {
        "status": "updated",
        "client_id": str(client.id),
        "client_name": client.name,
        "config": client.custom_prompt_config,
    }


@router.delete("/{client_id}")
def delete_client_prompt(
    client_id: str,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_password),
):
    """Remove custom prompt (revert to default)"""
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(404, "Client not found")

    # Disable custom prompt
    client.custom_prompt_enabled = False
    client.custom_prompt_config = None
    client.custom_prompt_updated_at = datetime.now(timezone.utc)

    db.commit()

    return {
        "status": "deleted",
        "client_id": str(client.id),
        "message": "Custom prompt disabled, using default",
    }


@router.get("")
def list_clients_with_custom_prompts(
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_password),
):
    """List all clients with custom prompts enabled"""
    clients = db.query(Client).filter(Client.custom_prompt_enabled == True).all()

    return {
        "count": len(clients),
        "clients": [
            {
                "client_id": str(c.id),
                "name": c.name,
                "industry": c.custom_prompt_config.get("industry") if c.custom_prompt_config else None,
                "updated_at": c.custom_prompt_updated_at.isoformat() if c.custom_prompt_updated_at else None,
            }
            for c in clients
        ],
    }
