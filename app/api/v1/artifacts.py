"""Artifact Engine API — /api/v1/artifacts."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.db.models import Artifact, Client
from app.db.session import get_db
from app.dependencies.auth import require_api_key
from app.services.artifact_service import ArtifactService
from app.utils.logging import get_logger

router = APIRouter(prefix="/api/v1/artifacts", tags=["artifacts"])
logger = get_logger(__name__)


# ------------------------------------------------------------------
# Serialization
# ------------------------------------------------------------------

def _serialize(item: Artifact) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "client_id": str(item.client_id),
        "artifact_type": item.artifact_type,
        "period_start": item.period_start.isoformat() if item.period_start else None,
        "period_end": item.period_end.isoformat() if item.period_end else None,
        "title": item.title,
        "summary": item.summary,
        "sections_json": item.sections_json,
        "edited_body": item.edited_body,
        "status": item.status,
        "reviewed_by": item.reviewed_by,
        "reviewed_at": item.reviewed_at.isoformat() if item.reviewed_at else None,
        "rejection_reason": item.rejection_reason,
        "delivered_at": item.delivered_at.isoformat() if item.delivered_at else None,
        "delivery_channel": item.delivery_channel,
        "recipient": item.recipient,
        "opened_at": item.opened_at.isoformat() if item.opened_at else None,
        "acted_at": item.acted_at.isoformat() if item.acted_at else None,
        "model_used": item.model_used,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


# ------------------------------------------------------------------
# Request models
# ------------------------------------------------------------------

class GenerateRequest(BaseModel):
    days: int = Field(default=7, ge=1, le=90)
    recipient: Optional[str] = Field(default=None)


class ApproveRequest(BaseModel):
    edited_body: Optional[str] = Field(default=None)
    reviewer_email: Optional[str] = Field(default=None)


class RejectRequest(BaseModel):
    reason: str = Field(..., min_length=1)
    reviewer_email: Optional[str] = Field(default=None)


class DeliverRequest(BaseModel):
    recipient: Optional[str] = Field(default=None)


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------

@router.get("")
def list_artifacts(
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    client: Client = Depends(require_api_key),
):
    q = db.query(Artifact).filter(Artifact.client_id == client.id)
    if status:
        q = q.filter(Artifact.status == status)
    items = q.order_by(desc(Artifact.created_at)).limit(limit).all()
    return {"items": [_serialize(a) for a in items]}


@router.get("/{artifact_id}")
def get_artifact(
    artifact_id: str,
    db: Session = Depends(get_db),
    client: Client = Depends(require_api_key),
):
    artifact = _fetch(db, artifact_id, client.id)
    return _serialize(artifact)


@router.post("/generate")
def generate_artifact(
    request: GenerateRequest,
    db: Session = Depends(get_db),
    client: Client = Depends(require_api_key),
):
    svc = ArtifactService(db)
    artifact = svc.generate_weekly_digest(
        client,
        recipient=request.recipient,
        commit=True,
    )
    return _serialize(artifact)


@router.post("/{artifact_id}/approve")
def approve_artifact(
    artifact_id: str,
    request: ApproveRequest,
    db: Session = Depends(get_db),
    client: Client = Depends(require_api_key),
):
    artifact = _fetch(db, artifact_id, client.id)
    if artifact.status not in ("draft", "in_review"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot approve artifact with status '{artifact.status}'",
        )
    reviewer = (request.reviewer_email or f"client-{str(client.id)[:8]}@system").strip()
    svc = ArtifactService(db)
    artifact = svc.approve(
        str(artifact.id),
        reviewer_email=reviewer,
        edited_body=request.edited_body,
        commit=True,
    )
    return _serialize(artifact)


@router.post("/{artifact_id}/reject")
def reject_artifact(
    artifact_id: str,
    request: RejectRequest,
    db: Session = Depends(get_db),
    client: Client = Depends(require_api_key),
):
    artifact = _fetch(db, artifact_id, client.id)
    reviewer = (request.reviewer_email or f"client-{str(client.id)[:8]}@system").strip()
    svc = ArtifactService(db)
    artifact = svc.reject(
        str(artifact.id),
        reviewer_email=reviewer,
        reason=request.reason,
        commit=True,
    )
    return _serialize(artifact)


@router.post("/{artifact_id}/deliver")
def deliver_artifact(
    artifact_id: str,
    request: DeliverRequest = DeliverRequest(),
    db: Session = Depends(get_db),
    client: Client = Depends(require_api_key),
):
    artifact = _fetch(db, artifact_id, client.id)
    if artifact.status != "approved":
        raise HTTPException(
            status_code=400,
            detail=f"Artifact must be approved before delivery (status: '{artifact.status}')",
        )
    svc = ArtifactService(db)
    artifact = svc.deliver(artifact, recipient=request.recipient, commit=True)
    return _serialize(artifact)


@router.get("/{artifact_id}/event")
def record_event(
    artifact_id: str,
    type: str = Query(..., description="opened | acted"),
    db: Session = Depends(get_db),
):
    """Unauthenticated engagement endpoint — called via email link click."""
    if type not in ("opened", "acted"):
        raise HTTPException(status_code=400, detail="type must be 'opened' or 'acted'")
    try:
        parsed_id = str(uuid.UUID(artifact_id))
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="Invalid artifact id")

    artifact = db.query(Artifact).filter(Artifact.id == uuid.UUID(parsed_id)).first()
    if artifact:
        svc = ArtifactService(db)
        svc.record_event(parsed_id, type, commit=True)
        logger.info("Artifact %s event: %s", parsed_id, type)

    # Redirect to a confirmation page rather than returning JSON — this is a link click
    from app.config import get_settings
    base = get_settings().app_base_url.rstrip("/")
    return RedirectResponse(url=f"{base}/app/artifacts?event={type}", status_code=302)


# ------------------------------------------------------------------
# Internal helper
# ------------------------------------------------------------------

def _fetch(db: Session, artifact_id: str, client_id: Any) -> Artifact:
    try:
        parsed = uuid.UUID(artifact_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="Invalid artifact id")
    artifact = db.query(Artifact).filter(
        Artifact.id == parsed,
        Artifact.client_id == client_id,
    ).first()
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return artifact
