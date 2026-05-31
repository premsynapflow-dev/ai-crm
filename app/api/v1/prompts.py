"""
Client-facing API for managing custom AI prompt configuration.
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import get_current_client, get_current_client_user
from app.db.models import Client, ClientUser
from app.db.session import get_db

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


class ClientPromptConfigUpdate(BaseModel):
    enabled: bool = True
    tone: str = Field(default="professional", pattern="^(professional|friendly|empathetic|formal)$")
    industry: str = Field(
        default="general",
        pattern="^(ecommerce|saas|healthcare|finance|education|general)$",
    )
    focus_areas: list[str] = Field(default_factory=list, max_length=10)
    reply_guidelines: str = Field(default="", max_length=2000)


@router.get("/prompts")
def get_prompts_config(
    client: Client = Depends(get_current_client),
    _: ClientUser = Depends(get_current_client_user),
):
    """Get current custom prompt config for the authenticated client."""
    config = client.custom_prompt_config or {}
    return {
        "custom_prompt_enabled": bool(client.custom_prompt_enabled),
        "tone": config.get("tone", "professional"),
        "industry": config.get("industry", "general"),
        "focus_areas": config.get("focus_areas", []),
        "reply_guidelines": config.get("reply_guidelines", ""),
        "updated_at": client.custom_prompt_updated_at.isoformat() if client.custom_prompt_updated_at else None,
    }


@router.put("/prompts")
def update_prompts_config(
    payload: ClientPromptConfigUpdate,
    db: Session = Depends(get_db),
    client: Client = Depends(get_current_client),
    _: ClientUser = Depends(get_current_client_user),
):
    """Update custom prompt config for the authenticated client."""
    db_client = db.query(Client).filter(Client.id == client.id).first()
    if not db_client:
        raise HTTPException(404, "Client not found")

    existing = db_client.custom_prompt_config or {}
    db_client.custom_prompt_enabled = payload.enabled
    db_client.custom_prompt_config = {
        **existing,
        "tone": payload.tone,
        "industry": payload.industry,
        "focus_areas": payload.focus_areas,
        "reply_guidelines": payload.reply_guidelines,
    }
    db_client.custom_prompt_updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(db_client)

    config = db_client.custom_prompt_config or {}
    return {
        "status": "updated",
        "custom_prompt_enabled": bool(db_client.custom_prompt_enabled),
        "tone": config.get("tone", "professional"),
        "industry": config.get("industry", "general"),
        "focus_areas": config.get("focus_areas", []),
        "reply_guidelines": config.get("reply_guidelines", ""),
        "updated_at": db_client.custom_prompt_updated_at.isoformat() if db_client.custom_prompt_updated_at else None,
    }
