from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.db.models import ClientUser, Complaint, RoutingRule, Team, TeamMember, TicketAssignment
from app.services.assignment import assign_team
from app.utils.logging import get_logger

logger = get_logger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _is_high_priority(priority: Any) -> bool:
    if isinstance(priority, str):
        return priority.strip().lower() in {"high", "critical", "urgent", "p1", "p0"}

    try:
        return int(priority or 0) >= 3
    except (TypeError, ValueError):
        return False


@dataclass
class RoutingResult:
    team_id: uuid.UUID | None
    team_name: str | None
    assigned_user_id: uuid.UUID | None
    assigned_user: str | None
    member_role: str | None = None
    active_tasks: int | None = None
    capacity: int | None = None
    used_legacy_fallback: bool = False


class RoutingService:
    def __init__(self, db: Session):
        self.db = db

    def route_ticket(
        self,
        complaint: Complaint,
        classification_result: dict[str, Any] | None,
        *,
        commit: bool = False,
        routed_by: str = "system:routing",
        force_rebalance: bool = False,
    ) -> RoutingResult:
        classification_result = classification_result or {}
        category = str(classification_result.get("category") or complaint.category or "").strip().lower() or "support"
        priority = classification_result.get("priority", complaint.priority)
        intent = str(classification_result.get("intent") or complaint.intent or "").strip()
        existing_team = None
        if complaint.team_id is not None:
            existing_team = (
                self.db.query(Team)
                .filter(
                    Team.id == complaint.team_id,
                    Team.client_id == complaint.client_id,
                )
                .first()
            )

        if (
            not force_rebalance
            and existing_team is not None
            and complaint.assigned_user_id is not None
            and complaint.assigned_to
        ):
            return RoutingResult(
                team_id=complaint.team_id,
                team_name=complaint.assigned_team,
                assigned_user_id=complaint.assigned_user_id,
                assigned_user=complaint.assigned_to,
            )

        team = existing_team or self._resolve_team(complaint.client_id, category, intent)
        if team is not None:
            logger.info(
                "Routing ticket %s for client %s category=%s to team %s (%s)",
                complaint.id,
                complaint.client_id,
                category,
                team.name,
                team.id,
            )
            member = self.select_assignee(team.id, priority)
            if member is not None:
                result = self._apply_member_assignment(
                    complaint,
                    team=team,
                    member=member,
                    routed_by=routed_by,
                    reason=f"Automatic routing for category '{category}'",
                )
                if commit:
                    self.db.commit()
                    self.db.refresh(complaint)
                else:
                    self.db.flush()
                return result

            logger.info(
                "Routing ticket %s found team %s but no active member; falling back to legacy assignment",
                complaint.id,
                team.id,
            )
            fallback_result = self._apply_legacy_assignment(
                complaint,
                team=team,
                team_name=team.name,
                routed_by=routed_by,
                reason=f"Automatic routing fallback for category '{category}'",
            )
            if commit:
                self.db.commit()
                self.db.refresh(complaint)
            else:
                self.db.flush()
            return fallback_result

        logger.warning(
            "Routing ticket %s for client %s has no configured team for category=%s; using legacy fallback",
            complaint.id,
            complaint.client_id,
            category,
        )
        fallback_result = self._apply_legacy_assignment(
            complaint,
            team=None,
            team_name=assign_team(category, intent),
            routed_by=routed_by,
            reason=f"Legacy routing fallback for category '{category}'",
        )
        if commit:
            self.db.commit()
            self.db.refresh(complaint)
        else:
            self.db.flush()
        return fallback_result

    def select_assignee(self, team_id: uuid.UUID, priority: Any) -> TeamMember | None:
        is_high_priority = _is_high_priority(priority)
        base_query = (
            self.db.query(TeamMember)
            .options(joinedload(TeamMember.user))
            .filter(
                TeamMember.team_id == team_id,
                TeamMember.is_active == True,
            )
        )

        if is_high_priority:
            manager = (
                base_query.filter(
                    TeamMember.role == "manager",
                    TeamMember.active_tasks < TeamMember.capacity,
                )
                .order_by(TeamMember.active_tasks.asc(), TeamMember.updated_at.asc())
                .first()
            )
            if manager is not None:
                return manager

            high_capacity_agent = (
                base_query.filter(
                    TeamMember.role == "agent",
                    TeamMember.active_tasks < TeamMember.capacity,
                )
                .order_by(TeamMember.capacity.desc(), TeamMember.active_tasks.asc(), TeamMember.updated_at.asc())
                .first()
            )
            if high_capacity_agent is not None:
                return high_capacity_agent

        least_loaded_agent = (
            base_query.filter(
                TeamMember.role == "agent",
                TeamMember.active_tasks < TeamMember.capacity,
            )
            .order_by(TeamMember.active_tasks.asc(), TeamMember.updated_at.asc())
            .first()
        )
        if least_loaded_agent is not None:
            return least_loaded_agent

        manager_fallback = (
            base_query.filter(TeamMember.role == "manager")
            .order_by(TeamMember.active_tasks.asc(), TeamMember.updated_at.asc())
            .first()
        )
        if manager_fallback is not None:
            return manager_fallback

        return base_query.order_by(TeamMember.active_tasks.asc(), TeamMember.updated_at.asc()).first()

    def sync_workload_for_resolution_change(
        self,
        complaint: Complaint,
        *,
        was_resolved: bool,
        is_resolved: bool,
        commit: bool = False,
    ) -> None:
        if complaint.assigned_user_id is None:
            return

        member = self._get_member(complaint.client_id, complaint.team_id, complaint.assigned_user_id)
        if member is None:
            return

        if not was_resolved and is_resolved:
            self._decrement_workload(member)
            logger.info(
                "Released workload for ticket %s from user %s on resolution (%s/%s)",
                complaint.id,
                member.user_id,
                member.active_tasks,
                member.capacity,
            )
        elif was_resolved and not is_resolved:
            self._increment_workload(member)
            logger.info(
                "Restored workload for reopened ticket %s to user %s (%s/%s)",
                complaint.id,
                member.user_id,
                member.active_tasks,
                member.capacity,
            )

        if commit:
            self.db.commit()
        else:
            self.db.flush()

    def assign_ticket_to_user(
        self,
        complaint: Complaint,
        *,
        assigned_to: str,
        assigned_by: str,
        assignment_reason: str | None = None,
        team_id: uuid.UUID | None = None,
        commit: bool = False,
    ) -> RoutingResult:
        user_value = str(assigned_to or "").strip()
        if not user_value:
            raise ValueError("assigned_to is required")

        user = self._find_user(complaint.client_id, user_value)
        previous_member = self._get_member(complaint.client_id, complaint.team_id, complaint.assigned_user_id)
        if user is None:
            previous_user_id = complaint.assigned_user_id
            previous_assigned_to = complaint.assigned_to
            complaint.assigned_user_id = None
            complaint.assigned_to = user_value
            if (
                complaint.resolution_status != "resolved"
                and previous_member is not None
                and (previous_user_id is not None or previous_assigned_to != complaint.assigned_to)
            ):
                self._decrement_workload(previous_member)
            self._sync_assignment_history(
                complaint=complaint,
                assigned_to=complaint.assigned_to,
                assigned_by=assigned_by,
                assignment_reason=assignment_reason or "Manual ticket assignment",
            )
            result = RoutingResult(
                team_id=complaint.team_id,
                team_name=complaint.assigned_team,
                assigned_user_id=None,
                assigned_user=complaint.assigned_to,
                used_legacy_fallback=True,
            )
            if commit:
                self.db.commit()
            else:
                self.db.flush()
            return result

        member = self._find_member_for_user(complaint.client_id, user.id, preferred_team_id=team_id or complaint.team_id)
        if member is not None and member.team is None:
            member = (
                self.db.query(TeamMember)
                .options(joinedload(TeamMember.team), joinedload(TeamMember.user))
                .filter(TeamMember.id == member.id)
                .first()
                or member
            )

        if member is not None and member.team is not None:
            result = self._apply_member_assignment(
                complaint,
                team=member.team,
                member=member,
                routed_by=assigned_by,
                reason=assignment_reason or "Manual ticket assignment",
            )
        else:
            previous_user_id = complaint.assigned_user_id
            previous_assigned_to = complaint.assigned_to
            complaint.assigned_user_id = user.id
            complaint.assigned_to = user.email
            if (
                complaint.resolution_status != "resolved"
                and previous_member is not None
                and (previous_user_id != user.id or previous_assigned_to != user.email)
            ):
                self._decrement_workload(previous_member)
            self._sync_assignment_history(
                complaint=complaint,
                assigned_to=complaint.assigned_to,
                assigned_by=assigned_by,
                assignment_reason=assignment_reason or "Manual ticket assignment",
            )
            result = RoutingResult(
                team_id=complaint.team_id,
                team_name=complaint.assigned_team,
                assigned_user_id=user.id,
                assigned_user=user.email,
                used_legacy_fallback=True,
            )

        if commit:
            self.db.commit()
        else:
            self.db.flush()
        return result

    def clear_ticket_assignment(
        self,
        complaint: Complaint,
        *,
        unassigned_by: str,
        reason: str | None = None,
        commit: bool = False,
    ) -> None:
        if complaint.resolution_status != "resolved":
            member = self._get_member(complaint.client_id, complaint.team_id, complaint.assigned_user_id)
            if member is not None:
                self._decrement_workload(member)

        active_assignments = (
            self.db.query(TicketAssignment)
            .filter(
                TicketAssignment.complaint_id == complaint.id,
                TicketAssignment.unassigned_at.is_(None),
            )
            .all()
        )
        for active in active_assignments:
            active.unassigned_at = _utcnow()
            if not active.assignment_reason and reason:
                active.assignment_reason = reason

        complaint.assigned_user_id = None
        complaint.assigned_to = None

        logger.info("Cleared assignment for ticket %s by %s", complaint.id, unassigned_by)
        if commit:
            self.db.commit()
        else:
            self.db.flush()

    def _resolve_team(self, client_id: uuid.UUID, category: str, intent: str) -> Team | None:
        direct_rule = (
            self.db.query(RoutingRule)
            .options(joinedload(RoutingRule.team))
            .filter(
                RoutingRule.client_id == client_id,
                func.lower(RoutingRule.category) == category.lower(),
            )
            .first()
        )
        if direct_rule is not None:
            return direct_rule.team

        support_team = self._find_team_by_name(client_id, "support")
        if support_team is not None:
            return support_team

        legacy_team_name = assign_team(category, intent)
        if legacy_team_name:
            team = self._find_team_by_name(client_id, legacy_team_name)
            if team is not None:
                return team

        return (
            self.db.query(Team)
            .filter(Team.client_id == client_id)
            .order_by(Team.created_at.asc())
            .first()
        )

    def _find_team_by_name(self, client_id: uuid.UUID, name: str | None) -> Team | None:
        normalized_name = str(name or "").strip().lower()
        if not normalized_name:
            return None

        return (
            self.db.query(Team)
            .filter(
                Team.client_id == client_id,
                func.lower(Team.name) == normalized_name,
            )
            .order_by(Team.created_at.asc())
            .first()
        )

    def _apply_member_assignment(
        self,
        complaint: Complaint,
        *,
        team: Team,
        member: TeamMember,
        routed_by: str,
        reason: str,
    ) -> RoutingResult:
        if member.user is None:
            member = (
                self.db.query(TeamMember)
                .options(joinedload(TeamMember.user))
                .filter(TeamMember.id == member.id)
                .first()
                or member
            )

        previous_member = self._get_member(complaint.client_id, complaint.team_id, complaint.assigned_user_id)
        assignment_changed = complaint.team_id != team.id or complaint.assigned_user_id != member.user_id

        complaint.team_id = team.id
        complaint.assigned_team = team.name
        complaint.assigned_user_id = member.user_id
        complaint.assigned_to = member.user.email if member.user is not None else complaint.assigned_to

        if assignment_changed and complaint.resolution_status != "resolved":
            if previous_member is not None and previous_member.id != member.id:
                self._decrement_workload(previous_member)
            self._increment_workload(member)

        if assignment_changed:
            self._sync_assignment_history(
                complaint=complaint,
                assigned_to=complaint.assigned_to,
                assigned_by=routed_by,
                assignment_reason=reason,
            )

        logger.info(
            "Selected assignee for ticket %s: team=%s user=%s role=%s workload=%s/%s",
            complaint.id,
            team.name,
            complaint.assigned_to,
            member.role,
            member.active_tasks,
            member.capacity,
        )
        return RoutingResult(
            team_id=team.id,
            team_name=team.name,
            assigned_user_id=member.user_id,
            assigned_user=complaint.assigned_to,
            member_role=member.role,
            active_tasks=member.active_tasks,
            capacity=member.capacity,
        )

    def _apply_legacy_assignment(
        self,
        complaint: Complaint,
        *,
        team: Team | None,
        team_name: str | None,
        routed_by: str,
        reason: str,
    ) -> RoutingResult:
        fallback_user = self._select_fallback_user(complaint.client_id, complaint.assigned_user_id)
        previous_team_id = complaint.team_id
        previous_user_id = complaint.assigned_user_id
        previous_assigned_to = complaint.assigned_to
        previous_member = self._get_member(complaint.client_id, complaint.team_id, complaint.assigned_user_id)
        complaint.team_id = team.id if team is not None else complaint.team_id
        complaint.assigned_team = str(team_name or complaint.assigned_team or "support")
        complaint.assigned_user_id = fallback_user.id if fallback_user is not None else complaint.assigned_user_id
        complaint.assigned_to = (
            fallback_user.email
            if fallback_user is not None
            else complaint.assigned_to or complaint.assigned_team
        )
        assignment_changed = (
            previous_team_id != complaint.team_id
            or previous_user_id != complaint.assigned_user_id
            or previous_assigned_to != complaint.assigned_to
        )

        if (
            assignment_changed
            and complaint.resolution_status != "resolved"
            and previous_member is not None
            and (
                previous_member.team_id != complaint.team_id
                or previous_member.user_id != complaint.assigned_user_id
            )
        ):
            self._decrement_workload(previous_member)

        if assignment_changed and complaint.assigned_to:
            self._sync_assignment_history(
                complaint=complaint,
                assigned_to=complaint.assigned_to,
                assigned_by=routed_by,
                assignment_reason=reason,
            )

        logger.info(
            "Legacy routing fallback for ticket %s: team=%s assignee=%s",
            complaint.id,
            complaint.assigned_team,
            complaint.assigned_to,
        )
        return RoutingResult(
            team_id=complaint.team_id,
            team_name=complaint.assigned_team,
            assigned_user_id=complaint.assigned_user_id,
            assigned_user=complaint.assigned_to,
            used_legacy_fallback=True,
        )

    def _select_fallback_user(
        self,
        client_id: uuid.UUID,
        preferred_user_id: uuid.UUID | None = None,
    ) -> ClientUser | None:
        if preferred_user_id is not None:
            preferred_user = (
                self.db.query(ClientUser)
                .filter(
                    ClientUser.id == preferred_user_id,
                    ClientUser.client_id == client_id,
                )
                .first()
            )
            if preferred_user is not None:
                return preferred_user

        return (
            self.db.query(ClientUser)
            .filter(ClientUser.client_id == client_id)
            .order_by(ClientUser.created_at.asc(), ClientUser.email.asc())
            .first()
        )

    def _find_user(self, client_id: uuid.UUID, value: str) -> ClientUser | None:
        query = self.db.query(ClientUser).filter(ClientUser.client_id == client_id)
        try:
            user_id = uuid.UUID(value)
        except (TypeError, ValueError):
            user_id = None

        if user_id is not None:
            return query.filter(ClientUser.id == user_id).first()

        return query.filter(func.lower(ClientUser.email) == value.lower()).first()

    def _find_member_for_user(
        self,
        client_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        preferred_team_id: uuid.UUID | None = None,
    ) -> TeamMember | None:
        query = (
            self.db.query(TeamMember)
            .options(joinedload(TeamMember.team), joinedload(TeamMember.user))
            .filter(
                TeamMember.client_id == client_id,
                TeamMember.user_id == user_id,
                TeamMember.is_active == True,
            )
        )
        if preferred_team_id is not None:
            preferred_member = query.filter(TeamMember.team_id == preferred_team_id).first()
            if preferred_member is not None:
                return preferred_member

        return query.order_by(TeamMember.updated_at.asc()).first()

    def _get_member(
        self,
        client_id: uuid.UUID,
        team_id: uuid.UUID | None,
        user_id: uuid.UUID | None,
    ) -> TeamMember | None:
        if user_id is None:
            return None

        query = (
            self.db.query(TeamMember)
            .options(joinedload(TeamMember.user))
            .filter(
                TeamMember.client_id == client_id,
                TeamMember.user_id == user_id,
            )
        )
        if team_id is not None:
            query = query.filter(TeamMember.team_id == team_id)

        return query.order_by(TeamMember.updated_at.asc()).first()

    def _increment_workload(self, member: TeamMember) -> None:
        member.active_tasks = int(member.active_tasks or 0) + 1
        member.updated_at = _utcnow()

    def _decrement_workload(self, member: TeamMember) -> None:
        member.active_tasks = max(int(member.active_tasks or 0) - 1, 0)
        member.updated_at = _utcnow()

    def _sync_assignment_history(
        self,
        *,
        complaint: Complaint,
        assigned_to: str | None,
        assigned_by: str,
        assignment_reason: str | None,
    ) -> None:
        if not assigned_to:
            return

        active_assignments = (
            self.db.query(TicketAssignment)
            .filter(
                TicketAssignment.complaint_id == complaint.id,
                TicketAssignment.unassigned_at.is_(None),
            )
            .all()
        )
        if any(active.assigned_to == assigned_to for active in active_assignments):
            return

        for active in active_assignments:
            active.unassigned_at = _utcnow()

        self.db.add(
            TicketAssignment(
                complaint_id=complaint.id,
                assigned_to=assigned_to,
                assigned_by=assigned_by,
                assignment_reason=assignment_reason,
            )
        )
