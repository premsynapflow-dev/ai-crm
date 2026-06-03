"""Approval chain service — creates and resolves human-in-the-loop approval requests.

Workflow action: "require_approval"
  Config: {approver_role: "manager", timeout_hours: 24,
           on_approve: [...actions], on_reject: [...actions]}

Flow:
  1. Workflow rule triggers "require_approval"
  2. create_approval_request() stores an ApprovalRequest with status="pending"
  3. Agent sees it in /api/v1/approvals and calls approve() or reject()
  4. execute_post_resolution() runs on_approve or on_reject actions
  5. Background worker monitors for expired approvals every 5 minutes
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import ApprovalRequest, Complaint
from app.utils.logging import get_logger

logger = get_logger(__name__)


def create_approval_request(
    db: Session,
    *,
    client_id: str,
    complaint_id: str,
    requested_by: str = "workflow",
    approver_role: str = "manager",
    workflow_execution_id: str | None = None,
    on_approve_actions: list[dict] | None = None,
    on_reject_actions: list[dict] | None = None,
    timeout_hours: int = 24,
    commit: bool = True,
) -> ApprovalRequest:
    expires_at = datetime.now(timezone.utc) + timedelta(hours=timeout_hours)
    req = ApprovalRequest(
        client_id=client_id,
        complaint_id=complaint_id,
        workflow_execution_id=workflow_execution_id,
        requested_by=requested_by,
        approver_role=approver_role,
        status="pending",
        on_approve_actions=on_approve_actions or [],
        on_reject_actions=on_reject_actions or [],
        timeout_hours=timeout_hours,
        expires_at=expires_at,
    )
    db.add(req)
    if commit:
        db.commit()
        db.refresh(req)
    else:
        db.flush()
    return req


def approve(
    db: Session,
    approval_id: str,
    approver_user_id: str,
    notes: str | None = None,
) -> ApprovalRequest | None:
    req = db.query(ApprovalRequest).filter(ApprovalRequest.id == approval_id).first()
    if not req or req.status != "pending":
        return None
    req.status = "approved"
    req.approver_user_id = approver_user_id
    req.notes = notes
    req.resolved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(req)
    _execute_post_resolution(db, req, "approved")
    return req


def reject(
    db: Session,
    approval_id: str,
    approver_user_id: str,
    notes: str | None = None,
) -> ApprovalRequest | None:
    req = db.query(ApprovalRequest).filter(ApprovalRequest.id == approval_id).first()
    if not req or req.status != "pending":
        return None
    req.status = "rejected"
    req.approver_user_id = approver_user_id
    req.notes = notes
    req.resolved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(req)
    _execute_post_resolution(db, req, "rejected")
    return req


def _execute_post_resolution(db: Session, req: ApprovalRequest, outcome: str) -> None:
    """Run on_approve or on_reject actions after a decision is made."""
    actions = req.on_approve_actions if outcome == "approved" else req.on_reject_actions
    if not actions:
        return

    try:
        complaint = db.query(Complaint).filter(Complaint.id == req.complaint_id).first()
        if not complaint:
            return
        for action in actions:
            _run_action(db, complaint, action)
    except Exception as exc:
        logger.exception("Post-approval action failed for request=%s: %s", req.id, exc)


def _run_action(db: Session, complaint: Complaint, action: dict) -> None:
    action_type = action.get("type") or action.get("action", "")
    if action_type == "escalate":
        level = action.get("level", 1)
        complaint.escalation_level = level
        complaint.escalated_at = datetime.now(timezone.utc)
        db.flush()
    elif action_type == "tag":
        pass  # Tag actions are informational for now
    elif action_type == "assign":
        user_id = action.get("user_id")
        if user_id:
            complaint.assigned_user_id = user_id
            db.flush()
    elif action_type == "resolve":
        complaint.resolution_status = "resolved"
        complaint.resolved_at = datetime.now(timezone.utc)
        complaint.status = "RESOLVED"
        db.flush()


def expire_timed_out_approvals(db: Session) -> int:
    """Mark pending approvals as expired if past their expires_at. Returns count expired."""
    now = datetime.now(timezone.utc)
    expired = (
        db.query(ApprovalRequest)
        .filter(
            ApprovalRequest.status == "pending",
            ApprovalRequest.expires_at <= now,
        )
        .all()
    )
    for req in expired:
        req.status = "expired"
        req.resolved_at = now
        logger.info("Approval request %s expired (complaint=%s)", req.id, req.complaint_id)
    if expired:
        db.commit()
    return len(expired)


def list_pending(db: Session, client_id: str, limit: int = 50) -> list[ApprovalRequest]:
    return (
        db.query(ApprovalRequest)
        .filter(
            ApprovalRequest.client_id == client_id,
            ApprovalRequest.status == "pending",
        )
        .order_by(ApprovalRequest.expires_at.asc())
        .limit(limit)
        .all()
    )
