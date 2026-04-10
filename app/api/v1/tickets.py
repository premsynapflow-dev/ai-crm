import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.db.models import Complaint, TicketAssignment, TicketComment, TicketStateTransition
from app.db.session import get_db
from app.dependencies.auth import require_api_key
from app.middleware.feature_gate import ensure_feature_access
from app.services.routing_service import RoutingService
from app.services.ticket_state_machine import TicketStateMachine

router = APIRouter(prefix="/api/v1/tickets", tags=["tickets-v1"])

def _default_actor(client) -> str:
    return (client.name or "").strip() or f"client:{client.id}"


def _default_author_email(client) -> str:
    return f"client-{str(client.id)[:8]}@system.local"


def _parse_ticket_id(ticket_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(ticket_id))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid ticket id") from exc


def _parse_uuid_value(value: str, *, detail: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=detail) from exc


def _serialize_ticket(ticket: Complaint) -> dict[str, Any]:
    return {
        "id": str(ticket.id),
        "ticket_id": ticket.ticket_id,
        "ticket_number": ticket.ticket_number or ticket.ticket_id,
        "summary": ticket.summary,
        "state": ticket.state,
        "state_changed_at": ticket.state_changed_at.isoformat() if ticket.state_changed_at else None,
        "assigned_to": ticket.assigned_to,
        "assigned_user_id": str(ticket.assigned_user_id) if ticket.assigned_user_id else None,
        "assigned_team": ticket.assigned_team,
        "team_id": str(ticket.team_id) if ticket.team_id else None,
        "sla_due_at": ticket.sla_due_at.isoformat() if ticket.sla_due_at else None,
        "sla_status": ticket.sla_status,
        "escalation_level": ticket.escalation_level,
        "escalated_at": ticket.escalated_at.isoformat() if ticket.escalated_at else None,
        "escalated_to": ticket.escalated_to,
        "reopened_count": ticket.reopened_count,
        "last_reopened_at": ticket.last_reopened_at.isoformat() if ticket.last_reopened_at else None,
        "resolution_status": ticket.resolution_status,
        "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None,
    }


def _serialize_transition(transition: TicketStateTransition) -> dict[str, Any]:
    return {
        "id": str(transition.id),
        "from_state": transition.from_state,
        "to_state": transition.to_state,
        "transitioned_by": transition.transitioned_by,
        "transition_reason": transition.transition_reason,
        "metadata": transition.metadata_json or {},
        "created_at": transition.created_at.isoformat() if transition.created_at else None,
    }


def _serialize_comment(comment: TicketComment) -> dict[str, Any]:
    return {
        "id": str(comment.id),
        "author_email": comment.author_email,
        "author_name": comment.author_name,
        "comment_type": comment.comment_type,
        "content": comment.content,
        "is_internal": comment.is_internal,
        "metadata": comment.metadata_json or {},
        "created_at": comment.created_at.isoformat() if comment.created_at else None,
    }


def _get_ticket_or_404(db: Session, complaint_id: uuid.UUID, client_id) -> Complaint:
    ticket = db.query(Complaint).filter(
        and_(Complaint.id == complaint_id, Complaint.client_id == client_id)
    ).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


class StateTransitionRequest(BaseModel):
    to_state: str
    reason: Optional[str] = None
    actor: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CommentCreateRequest(BaseModel):
    content: str = Field(..., min_length=1)
    is_internal: bool = False
    author_email: Optional[str] = None
    author_name: Optional[str] = None
    comment_type: str = "note"
    metadata: dict[str, Any] = Field(default_factory=dict)


class AssignmentRequest(BaseModel):
    assigned_to: str = Field(..., min_length=1)
    team_id: Optional[str] = None
    assigned_by: Optional[str] = None
    assignment_reason: Optional[str] = None
    transition_to_assigned: bool = True


@router.get("/{ticket_id}")
def get_ticket(
    ticket_id: str,
    db: Session = Depends(get_db),
    current_client=Depends(require_api_key),
):
    ensure_feature_access(current_client, "ticketing_state_machine")
    ticket = _get_ticket_or_404(db, _parse_ticket_id(ticket_id), current_client.id)
    return _serialize_ticket(ticket)


@router.post("/{ticket_id}/transition")
def transition_ticket_state(
    ticket_id: str,
    request: StateTransitionRequest,
    db: Session = Depends(get_db),
    current_client=Depends(require_api_key),
):
    ensure_feature_access(current_client, "ticketing_state_machine")
    ticket = _get_ticket_or_404(db, _parse_ticket_id(ticket_id), current_client.id)

    actor = request.actor or _default_actor(current_client)
    state_machine = TicketStateMachine(db)
    success, error = state_machine.transition(
        ticket,
        request.to_state,
        actor,
        request.reason,
        request.metadata,
        commit=False,
    )

    if not success:
        raise HTTPException(status_code=400, detail=error)

    if request.reason:
        db.add(
            TicketComment(
                complaint_id=ticket.id,
                author_email=_default_author_email(current_client),
                author_name=current_client.name,
                comment_type="status_change",
                content=request.reason,
                is_internal=True,
                metadata_json={"state": ticket.state, **request.metadata},
            )
        )

    db.commit()
    db.refresh(ticket)
    return {
        "success": True,
        "ticket_id": str(ticket.id),
        "new_state": ticket.state,
        "ticket": _serialize_ticket(ticket),
    }


@router.get("/{ticket_id}/transitions")
def list_ticket_transitions(
    ticket_id: str,
    db: Session = Depends(get_db),
    current_client=Depends(require_api_key),
):
    ensure_feature_access(current_client, "ticketing_state_machine")
    complaint_id = _parse_ticket_id(ticket_id)
    _get_ticket_or_404(db, complaint_id, current_client.id)
    transitions = (
        db.query(TicketStateTransition)
        .filter(TicketStateTransition.complaint_id == complaint_id)
        .order_by(TicketStateTransition.created_at.desc())
        .all()
    )
    return {"items": [_serialize_transition(item) for item in transitions]}


@router.get("/{ticket_id}/comments")
def list_ticket_comments(
    ticket_id: str,
    include_internal: bool = True,
    db: Session = Depends(get_db),
    current_client=Depends(require_api_key),
):
    ensure_feature_access(current_client, "ticketing_state_machine")
    complaint_id = _parse_ticket_id(ticket_id)
    _get_ticket_or_404(db, complaint_id, current_client.id)
    query = db.query(TicketComment).filter(TicketComment.complaint_id == complaint_id)
    if not include_internal:
        query = query.filter(TicketComment.is_internal == False)
    comments = query.order_by(TicketComment.created_at.desc()).all()
    return {"items": [_serialize_comment(item) for item in comments]}


@router.post("/{ticket_id}/comments")
def create_ticket_comment(
    ticket_id: str,
    request: CommentCreateRequest,
    db: Session = Depends(get_db),
    current_client=Depends(require_api_key),
):
    ensure_feature_access(current_client, "ticketing_state_machine")
    ticket = _get_ticket_or_404(db, _parse_ticket_id(ticket_id), current_client.id)

    comment = TicketComment(
        complaint_id=ticket.id,
        author_email=(request.author_email or _default_author_email(current_client)).strip(),
        author_name=request.author_name or current_client.name,
        comment_type=request.comment_type,
        content=request.content.strip(),
        is_internal=request.is_internal,
        metadata_json=request.metadata,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return {"success": True, "comment": _serialize_comment(comment)}


@router.post("/{ticket_id}/assign")
def assign_ticket(
    ticket_id: str,
    request: AssignmentRequest,
    db: Session = Depends(get_db),
    current_client=Depends(require_api_key),
):
    ensure_feature_access(current_client, "ticketing_state_machine")
    ticket = _get_ticket_or_404(db, _parse_ticket_id(ticket_id), current_client.id)
    actor = request.assigned_by or _default_actor(current_client)
    routing_result = RoutingService(db).assign_ticket_to_user(
        ticket,
        assigned_to=request.assigned_to.strip(),
        assigned_by=actor,
        assignment_reason=request.assignment_reason,
        team_id=_parse_uuid_value(request.team_id, detail="Invalid team id") if request.team_id else None,
        commit=False,
    )

    state_machine = TicketStateMachine(db)
    current_state = (ticket.state or "new").strip().lower()
    if request.transition_to_assigned and current_state in {"new", "reopened"}:
        success, error = state_machine.transition(
            ticket,
            "assigned",
            actor,
            reason=request.assignment_reason or "Ticket assigned",
            metadata={
                "assigned_to": ticket.assigned_to,
                "assigned_user_id": str(ticket.assigned_user_id) if ticket.assigned_user_id else None,
                "team_id": str(ticket.team_id) if ticket.team_id else None,
            },
            commit=False,
        )
        if not success:
            raise HTTPException(status_code=400, detail=error)
    else:
        state_machine.sync_from_legacy(
            ticket,
            transitioned_by=actor,
            reason=request.assignment_reason or "Ticket assignment updated",
            metadata={
                "assigned_to": ticket.assigned_to,
                "assigned_user_id": str(ticket.assigned_user_id) if ticket.assigned_user_id else None,
                "team_id": str(ticket.team_id) if ticket.team_id else None,
            },
            commit=False,
        )

    db.commit()
    db.refresh(ticket)
    assignment = (
        db.query(TicketAssignment)
        .filter(
            TicketAssignment.complaint_id == ticket.id,
            TicketAssignment.unassigned_at.is_(None),
        )
        .order_by(TicketAssignment.assigned_at.desc())
        .first()
    )
    return {
        "success": True,
        "ticket": _serialize_ticket(ticket),
        "assignment": {
            "id": str(assignment.id) if assignment else None,
            "assigned_to": assignment.assigned_to if assignment else routing_result.assigned_user,
            "assigned_by": assignment.assigned_by if assignment else actor,
            "assigned_at": assignment.assigned_at.isoformat() if assignment and assignment.assigned_at else None,
            "assignment_reason": assignment.assignment_reason if assignment else request.assignment_reason,
        },
    }


@router.delete("/{ticket_id}/assignment")
def clear_ticket_assignment(
    ticket_id: str,
    db: Session = Depends(get_db),
    current_client=Depends(require_api_key),
):
    ensure_feature_access(current_client, "ticketing_state_machine")
    ticket = _get_ticket_or_404(db, _parse_ticket_id(ticket_id), current_client.id)
    RoutingService(db).clear_ticket_assignment(
        ticket,
        unassigned_by=_default_actor(current_client),
        reason="Ticket unassigned",
        commit=False,
    )
    TicketStateMachine(db).sync_from_legacy(
        ticket,
        transitioned_by=_default_actor(current_client),
        reason="Ticket unassigned",
        metadata={},
        commit=False,
    )
    db.commit()
    db.refresh(ticket)
    return {"success": True, "ticket": _serialize_ticket(ticket)}
