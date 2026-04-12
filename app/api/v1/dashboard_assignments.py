from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_current_client
from app.db.models import Client, Complaint, Team, TeamMember
from app.db.session import get_db

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard-assignments-v1"])


def _display_name_from_email(email: str | None) -> str:
    local_part = (email or "").split("@", 1)[0].replace(".", " ").replace("_", " ").strip()
    if local_part:
        return " ".join(part.capitalize() for part in local_part.split())
    return "SynapFlow User"


def _priority_label(priority: int | None) -> str:
    if priority is None or priority <= 1:
        return "low"
    if priority == 2:
        return "medium"
    if priority in {3, 4}:
        return "high"
    return "critical"


def _status_label(complaint: Complaint) -> str:
    if complaint.resolution_status == "resolved":
        return "resolved"
    if complaint.status == "ESCALATE_HIGH" or complaint.ai_reply_status == "agent_review":
        return "escalated"
    if complaint.ai_reply or complaint.ai_reply_sent_at or complaint.status not in {"PENDING", "NEW", None}:
        return "in-progress"
    return "new"


@router.get("/assignments")
def get_assignment_dashboard(
    db: Session = Depends(get_db),
    client: Client = Depends(get_current_client),
):
    teams = (
        db.query(Team)
        .filter(Team.client_id == client.id)
        .order_by(Team.name.asc())
        .all()
    )

    team_payload = []
    for team in teams:
        members = (
            db.query(TeamMember)
            .filter(
                TeamMember.client_id == client.id,
                TeamMember.team_id == team.id,
            )
            .order_by(TeamMember.role.desc(), TeamMember.updated_at.asc(), TeamMember.created_at.asc())
            .all()
        )
        team_payload.append(
            {
                "id": str(team.id),
                "name": team.name,
                "members": [
                    {
                        "id": str(member.id),
                        "user_id": str(member.user_id),
                        "name": _display_name_from_email(member.user.email if member.user else None),
                        "email": member.user.email if member.user else "",
                        "role": member.role,
                        "active_tasks": int(member.active_tasks or 0),
                        "capacity": int(member.capacity or 0),
                        "is_active": bool(member.is_active),
                    }
                    for member in members
                ],
            }
        )

    tickets = (
        db.query(Complaint)
        .filter(
            Complaint.client_id == client.id,
            Complaint.resolution_status != "resolved",
            Complaint.state.notin_(["spam", "invalid", "closed"]),
        )
        .order_by(Complaint.created_at.desc())
        .limit(250)
        .all()
    )

    ticket_payload = [
        {
            "id": str(ticket.id),
            "subject": ticket.summary,
            "category": ticket.category,
            "priority": _priority_label(ticket.priority),
            "status": _status_label(ticket),
            "assigned_to": ticket.assigned_to,
            "assigned_user_id": str(ticket.assigned_user_id) if ticket.assigned_user_id else None,
            "team_id": str(ticket.team_id) if ticket.team_id else None,
            "team_name": ticket.assigned_team,
            "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
            "ticket_id": ticket.ticket_id,
        }
        for ticket in tickets
    ]

    return {
        "teams": team_payload,
        "tickets": ticket_payload,
    }
