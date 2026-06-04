from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_current_client, get_current_client_user
from app.db.models import Client, ClientUser, RoutingRule, Team, TeamMember
from app.db.session import get_db

router = APIRouter(prefix="/api/v1", tags=["teams-v1"])


def _display_name_from_email(email: str | None) -> str:
    local_part = (email or "").split("@", 1)[0].replace(".", " ").replace("_", " ").strip()
    if local_part:
        return " ".join(part.capitalize() for part in local_part.split())
    return "SynapFlow User"


def _parse_uuid(value: str, *, detail: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=detail) from exc


def _serialize_member(member: TeamMember) -> dict[str, object]:
    user = member.user
    email = user.email if user is not None else ""
    return {
        "id": str(member.id),
        "team_id": str(member.team_id),
        "user_id": str(member.user_id),
        "name": _display_name_from_email(email),
        "email": email,
        "role": member.role,
        "capacity": int(member.capacity or 0),
        "active_tasks": int(member.active_tasks or 0),
        "is_active": bool(member.is_active),
        "created_at": member.created_at.isoformat() if member.created_at else None,
        "updated_at": member.updated_at.isoformat() if member.updated_at else None,
    }


def _serialize_team(team: Team, member_count: int = 0, active_tasks: int = 0) -> dict[str, object]:
    return {
        "id": str(team.id),
        "name": team.name,
        "member_count": int(member_count),
        "active_tasks": int(active_tasks),
        "created_at": team.created_at.isoformat() if team.created_at else None,
        "updated_at": team.updated_at.isoformat() if team.updated_at else None,
    }


def _get_team_or_404(db: Session, client_id, team_id: str) -> Team:
    parsed_team_id = _parse_uuid(team_id, detail="Invalid team id")
    team = (
        db.query(Team)
        .filter(
            Team.id == parsed_team_id,
            Team.client_id == client_id,
        )
        .first()
    )
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


def _get_member_or_404(db: Session, client_id, member_id: str) -> TeamMember:
    parsed_member_id = _parse_uuid(member_id, detail="Invalid team member id")
    member = (
        db.query(TeamMember)
        .filter(
            TeamMember.id == parsed_member_id,
            TeamMember.client_id == client_id,
        )
        .first()
    )
    if member is None:
        raise HTTPException(status_code=404, detail="Team member not found")
    return member


class TeamCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class TeamMemberCreateRequest(BaseModel):
    user_id: str
    role: str = Field(default="agent")
    capacity: int = Field(default=10, ge=0)


class TeamMemberUpdateRequest(BaseModel):
    role: str | None = None
    capacity: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


@router.get("/teams")
def list_teams(
    db: Session = Depends(get_db),
    client: Client = Depends(get_current_client),
):
    rows = (
        db.query(
            Team,
            func.count(TeamMember.id).label("member_count"),
            func.coalesce(func.sum(TeamMember.active_tasks), 0).label("active_tasks"),
        )
        .outerjoin(
            TeamMember,
            (TeamMember.team_id == Team.id) & (TeamMember.client_id == client.id),
        )
        .filter(Team.client_id == client.id)
        .group_by(Team.id)
        .order_by(Team.name.asc())
        .all()
    )
    result = []
    for team, member_count, active_tasks in rows:
        rules = (
            db.query(RoutingRule.category)
            .filter(RoutingRule.team_id == team.id, RoutingRule.client_id == client.id)
            .order_by(RoutingRule.category.asc())
            .all()
        )
        t = _serialize_team(team, member_count, active_tasks)
        t["routing_categories"] = [r.category for r in rules]
        result.append(t)
    return {"items": result}


@router.post("/teams", status_code=201)
def create_team(
    payload: TeamCreateRequest,
    db: Session = Depends(get_db),
    client: Client = Depends(get_current_client),
    user: ClientUser = Depends(get_current_client_user),
):
    name = " ".join(payload.name.split()).strip()
    if not name:
        raise HTTPException(status_code=400, detail="Team name is required")

    existing = (
        db.query(Team)
        .filter(
            Team.client_id == client.id,
            func.lower(Team.name) == name.lower(),
        )
        .first()
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Team name already exists")

    team = Team(client_id=client.id, name=name)
    db.add(team)
    db.commit()
    db.refresh(team)
    return {"team": _serialize_team(team)}


@router.get("/teams/{team_id}/members")
def list_team_members(
    team_id: str,
    db: Session = Depends(get_db),
    client: Client = Depends(get_current_client),
):
    team = _get_team_or_404(db, client.id, team_id)
    members = (
        db.query(TeamMember)
        .filter(
            TeamMember.client_id == client.id,
            TeamMember.team_id == team.id,
        )
        .order_by(TeamMember.role.desc(), TeamMember.updated_at.asc(), TeamMember.created_at.asc())
        .all()
    )
    return {
        "team": _serialize_team(team, member_count=len(members), active_tasks=sum(int(item.active_tasks or 0) for item in members)),
        "items": [_serialize_member(member) for member in members],
    }


@router.post("/teams/{team_id}/members", status_code=201)
def add_team_member(
    team_id: str,
    payload: TeamMemberCreateRequest,
    db: Session = Depends(get_db),
    client: Client = Depends(get_current_client),
    user: ClientUser = Depends(get_current_client_user),
):
    team = _get_team_or_404(db, client.id, team_id)
    if payload.role not in {"agent", "manager"}:
        raise HTTPException(status_code=400, detail="Invalid role")

    parsed_user_id = _parse_uuid(payload.user_id, detail="Invalid user id")
    client_user = (
        db.query(ClientUser)
        .filter(
            ClientUser.id == parsed_user_id,
            ClientUser.client_id == client.id,
        )
        .first()
    )
    if client_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    existing = (
        db.query(TeamMember)
        .filter(
            TeamMember.client_id == client.id,
            TeamMember.team_id == team.id,
            TeamMember.user_id == client_user.id,
        )
        .first()
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="User is already a member of this team")

    member = TeamMember(
        client_id=client.id,
        team_id=team.id,
        user_id=client_user.id,
        role=payload.role,
        capacity=payload.capacity,
        active_tasks=0,
        is_active=True,
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return {"member": _serialize_member(member)}


@router.patch("/team-members/{member_id}")
def update_team_member(
    member_id: str,
    payload: TeamMemberUpdateRequest,
    db: Session = Depends(get_db),
    client: Client = Depends(get_current_client),
    user: ClientUser = Depends(get_current_client_user),
):
    member = _get_member_or_404(db, client.id, member_id)
    if payload.role is not None:
        if payload.role not in {"agent", "manager"}:
            raise HTTPException(status_code=400, detail="Invalid role")
        member.role = payload.role
    if payload.capacity is not None:
        member.capacity = payload.capacity
    if payload.is_active is not None:
        member.is_active = payload.is_active

    db.commit()
    db.refresh(member)
    return {"member": _serialize_member(member)}


@router.delete("/teams/{team_id}", status_code=204)
def delete_team(
    team_id: str,
    db: Session = Depends(get_db),
    client: Client = Depends(get_current_client),
    user: ClientUser = Depends(get_current_client_user),
):
    team = _get_team_or_404(db, client.id, team_id)
    db.delete(team)
    db.commit()


@router.delete("/team-members/{member_id}", status_code=204)
def remove_team_member(
    member_id: str,
    db: Session = Depends(get_db),
    client: Client = Depends(get_current_client),
    user: ClientUser = Depends(get_current_client_user),
):
    member = _get_member_or_404(db, client.id, member_id)
    db.delete(member)
    db.commit()


@router.get("/users")
def list_users(
    db: Session = Depends(get_db),
    client: Client = Depends(get_current_client),
):
    users = (
        db.query(ClientUser)
        .filter(ClientUser.client_id == client.id)
        .order_by(ClientUser.created_at.asc())
        .all()
    )
    return {
        "items": [
            {
                "id": str(u.id),
                "email": u.email,
                "name": _display_name_from_email(u.email),
                "role": "agent",
            }
            for u in users
        ]
    }


@router.get("/teams/{team_id}/routing-rules")
def list_routing_rules(
    team_id: str,
    db: Session = Depends(get_db),
    client: Client = Depends(get_current_client),
):
    team = _get_team_or_404(db, client.id, team_id)
    rules = (
        db.query(RoutingRule)
        .filter(RoutingRule.team_id == team.id, RoutingRule.client_id == client.id)
        .order_by(RoutingRule.category.asc())
        .all()
    )
    return {
        "items": [
            {
                "id": str(r.id),
                "category": r.category,
                "team_id": str(r.team_id),
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rules
        ]
    }


class RoutingRuleCreateRequest(BaseModel):
    category: str = Field(..., min_length=1, max_length=100)


@router.post("/teams/{team_id}/routing-rules", status_code=201)
def add_routing_rule(
    team_id: str,
    payload: RoutingRuleCreateRequest,
    db: Session = Depends(get_db),
    client: Client = Depends(get_current_client),
    user: ClientUser = Depends(get_current_client_user),
):
    team = _get_team_or_404(db, client.id, team_id)
    category = " ".join(payload.category.split()).strip()
    if not category:
        raise HTTPException(status_code=400, detail="Category is required")

    existing = (
        db.query(RoutingRule)
        .filter(
            RoutingRule.client_id == client.id,
            func.lower(RoutingRule.category) == category.lower(),
        )
        .first()
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"Category '{category}' is already assigned to a team")

    rule = RoutingRule(client_id=client.id, team_id=team.id, category=category)
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return {
        "id": str(rule.id),
        "category": rule.category,
        "team_id": str(rule.team_id),
        "created_at": rule.created_at.isoformat() if rule.created_at else None,
    }


@router.delete("/routing-rules/{rule_id}", status_code=204)
def delete_routing_rule(
    rule_id: str,
    db: Session = Depends(get_db),
    client: Client = Depends(get_current_client),
    user: ClientUser = Depends(get_current_client_user),
):
    parsed_rule_id = _parse_uuid(rule_id, detail="Invalid rule id")
    rule = (
        db.query(RoutingRule)
        .filter(RoutingRule.id == parsed_rule_id, RoutingRule.client_id == client.id)
        .first()
    )
    if rule is None:
        raise HTTPException(status_code=404, detail="Routing rule not found")
    db.delete(rule)
    db.commit()
