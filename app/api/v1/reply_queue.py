import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, desc
from sqlalchemy.orm import Session

from app.db.models import AIReplyQueue
from app.db.session import get_db
from app.dependencies.auth import require_api_key
from app.middleware.feature_gate import ensure_feature_access
from app.services.auto_reply_hardened import HardenedAutoReplyService

router = APIRouter(prefix="/api/v1/reply-queue", tags=["reply-queue-v1"])


def _parse_queue_id(queue_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(queue_id))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid queue id") from exc


def _serialize_queue_item(item: AIReplyQueue) -> dict[str, Any]:
    complaint = item.complaint
    return {
        "id": str(item.id),
        "ticket_id": str(item.complaint_id),
        "ticket_number": complaint.ticket_number if complaint else None,
        "ticket_summary": complaint.summary if complaint else None,
        "generated_reply": item.generated_reply,
        "edited_reply": item.edited_reply,
        "confidence_score": item.confidence_score,
        "generation_strategy": item.generation_strategy,
        "generation_metadata": item.generation_metadata or {},
        "status": item.status,
        "reviewed_by": item.reviewed_by,
        "reviewed_at": item.reviewed_at.isoformat() if item.reviewed_at else None,
        "rejection_reason": item.rejection_reason,
        "hallucination_check_passed": item.hallucination_check_passed,
        "toxicity_score": item.toxicity_score,
        "factual_consistency_score": item.factual_consistency_score,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "expires_at": item.expires_at.isoformat() if item.expires_at else None,
    }


class ReplyApprovalRequest(BaseModel):
    edited_reply: Optional[str] = Field(default=None)
    reviewer_email: Optional[str] = Field(default=None)


class ReplyRejectionRequest(BaseModel):
    reason: str = Field(..., min_length=1)
    reviewer_email: Optional[str] = Field(default=None)


@router.get("")
def get_pending_replies(
    status: str = Query(default="pending"),
    db: Session = Depends(get_db),
    current_client=Depends(require_api_key),
):
    ensure_feature_access(current_client, "auto_reply_approval_queue", db=db)
    query = db.query(AIReplyQueue).filter(
        and_(
            AIReplyQueue.client_id == current_client.id,
            AIReplyQueue.status == status,
        )
    )
    if status == "pending":
        query = query.filter(
            (AIReplyQueue.expires_at.is_(None)) | (AIReplyQueue.expires_at > datetime.now(timezone.utc))
        )
    items = query.order_by(desc(AIReplyQueue.created_at)).limit(50).all()
    return {"items": [_serialize_queue_item(item) for item in items]}


@router.post("/{queue_id}/approve")
def approve_reply(
    queue_id: str,
    request: ReplyApprovalRequest,
    db: Session = Depends(get_db),
    current_client=Depends(require_api_key),
):
    ensure_feature_access(current_client, "auto_reply_approval_queue", db=db)
    parsed_id = _parse_queue_id(queue_id)
    item = db.query(AIReplyQueue).filter(AIReplyQueue.id == parsed_id, AIReplyQueue.client_id == current_client.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Queue item not found")
    if item.status != "pending":
        raise HTTPException(status_code=400, detail="Queue item is not pending approval")

    reviewer_email = (request.reviewer_email or f"client-{str(current_client.id)[:8]}@system.local").strip()
    success = HardenedAutoReplyService(db).approve_reply(
        str(item.id),
        reviewer_email=reviewer_email,
        edited_reply=request.edited_reply,
        commit=True,
    )
    if not success:
        raise HTTPException(status_code=502, detail="Queue item was reviewed, but the reply could not be delivered")
    db.refresh(item)
    return {"success": True, "item": _serialize_queue_item(item)}


@router.post("/{queue_id}/reject")
def reject_reply(
    queue_id: str,
    request: ReplyRejectionRequest,
    db: Session = Depends(get_db),
    current_client=Depends(require_api_key),
):
    ensure_feature_access(current_client, "auto_reply_approval_queue", db=db)
    parsed_id = _parse_queue_id(queue_id)
    item = db.query(AIReplyQueue).filter(AIReplyQueue.id == parsed_id, AIReplyQueue.client_id == current_client.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Queue item not found")

    reviewer_email = (request.reviewer_email or f"client-{str(current_client.id)[:8]}@system.local").strip()
    success = HardenedAutoReplyService(db).reject_reply(
        str(item.id),
        reviewer_email=reviewer_email,
        reason=request.reason,
        commit=True,
    )
    if not success:
        raise HTTPException(status_code=400, detail="Queue item could not be rejected")
    db.refresh(item)
    return {"success": True, "item": _serialize_queue_item(item)}
