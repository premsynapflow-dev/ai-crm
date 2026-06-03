"""Approval chain API — Layer 6: human-in-the-loop workflow decisions."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.models import ApprovalRequest, Client, Complaint
from app.db.session import get_db
from app.dependencies.auth import require_api_key
from app.services.approval_service import approve, create_approval_request, list_pending, reject
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/approvals", tags=["approvals"])


class ApprovalDecision(BaseModel):
    approver_user_id: str
    notes: str | None = None


class CreateApprovalRequest(BaseModel):
    complaint_id: UUID
    approver_role: str = "manager"
    timeout_hours: int = 24
    on_approve_actions: list[dict] = []
    on_reject_actions: list[dict] = []


@router.get("")
def get_pending_approvals(
    db: Session = Depends(get_db),
    current_client: Client = Depends(require_api_key),
):
    """List all pending approval requests for this client, ordered by expiry (soonest first)."""
    requests = list_pending(db, str(current_client.id))
    return {
        "approvals": [
            {
                "id": str(r.id),
                "complaint_id": str(r.complaint_id),
                "approver_role": r.approver_role,
                "requested_by": r.requested_by,
                "status": r.status,
                "on_approve_actions": r.on_approve_actions,
                "on_reject_actions": r.on_reject_actions,
                "timeout_hours": r.timeout_hours,
                "expires_at": r.expires_at.isoformat() if r.expires_at else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in requests
        ],
        "total": len(requests),
    }


@router.post("/{approval_id}/approve")
def approve_request(
    approval_id: UUID,
    body: ApprovalDecision,
    db: Session = Depends(get_db),
    current_client: Client = Depends(require_api_key),
):
    """Approve a pending approval request and execute its on_approve actions."""
    req = db.query(ApprovalRequest).filter(
        ApprovalRequest.id == approval_id,
        ApprovalRequest.client_id == current_client.id,
    ).first()
    if not req:
        raise HTTPException(status_code=404, detail="Approval request not found")
    if req.status != "pending":
        raise HTTPException(status_code=409, detail=f"Request is already {req.status}")

    updated = approve(db, str(approval_id), body.approver_user_id, body.notes)
    if not updated:
        raise HTTPException(status_code=409, detail="Could not approve request")

    return {"id": str(updated.id), "status": updated.status, "resolved_at": updated.resolved_at.isoformat()}


@router.post("/{approval_id}/reject")
def reject_request(
    approval_id: UUID,
    body: ApprovalDecision,
    db: Session = Depends(get_db),
    current_client: Client = Depends(require_api_key),
):
    """Reject a pending approval request and execute its on_reject actions."""
    req = db.query(ApprovalRequest).filter(
        ApprovalRequest.id == approval_id,
        ApprovalRequest.client_id == current_client.id,
    ).first()
    if not req:
        raise HTTPException(status_code=404, detail="Approval request not found")
    if req.status != "pending":
        raise HTTPException(status_code=409, detail=f"Request is already {req.status}")

    updated = reject(db, str(approval_id), body.approver_user_id, body.notes)
    if not updated:
        raise HTTPException(status_code=409, detail="Could not reject request")

    return {"id": str(updated.id), "status": updated.status, "resolved_at": updated.resolved_at.isoformat()}


@router.post("")
def create_approval(
    body: CreateApprovalRequest,
    db: Session = Depends(get_db),
    current_client: Client = Depends(require_api_key),
):
    """Manually create an approval request for a complaint (for testing / manual workflow)."""
    complaint = db.query(Complaint).filter(
        Complaint.id == body.complaint_id,
        Complaint.client_id == current_client.id,
    ).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    req = create_approval_request(
        db,
        client_id=str(current_client.id),
        complaint_id=str(body.complaint_id),
        requested_by="manual",
        approver_role=body.approver_role,
        on_approve_actions=body.on_approve_actions,
        on_reject_actions=body.on_reject_actions,
        timeout_hours=body.timeout_hours,
    )
    return {
        "id": str(req.id),
        "status": req.status,
        "expires_at": req.expires_at.isoformat() if req.expires_at else None,
    }
