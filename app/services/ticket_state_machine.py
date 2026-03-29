import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from app.db.models import Complaint, TicketStateTransition

logger = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TicketState(str, Enum):
    NEW = "new"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    PENDING_CUSTOMER = "pending_customer"
    PENDING_INTERNAL = "pending_internal"
    RESOLVED = "resolved"
    CLOSED = "closed"
    SPAM = "spam"
    INVALID = "invalid"
    REOPENED = "reopened"


class TicketStateMachine:
    VALID_TRANSITIONS: Dict[TicketState, list[TicketState]] = {
        TicketState.NEW: [TicketState.ASSIGNED, TicketState.SPAM, TicketState.INVALID, TicketState.IN_PROGRESS],
        TicketState.ASSIGNED: [TicketState.IN_PROGRESS, TicketState.SPAM, TicketState.INVALID],
        TicketState.IN_PROGRESS: [TicketState.PENDING_CUSTOMER, TicketState.PENDING_INTERNAL, TicketState.RESOLVED],
        TicketState.PENDING_CUSTOMER: [TicketState.IN_PROGRESS, TicketState.RESOLVED, TicketState.CLOSED],
        TicketState.PENDING_INTERNAL: [TicketState.IN_PROGRESS, TicketState.RESOLVED],
        TicketState.RESOLVED: [TicketState.CLOSED, TicketState.REOPENED],
        TicketState.CLOSED: [TicketState.REOPENED],
        TicketState.SPAM: [],
        TicketState.INVALID: [],
        TicketState.REOPENED: [TicketState.ASSIGNED, TicketState.IN_PROGRESS],
    }

    SLA_PAUSED_STATES = {
        TicketState.PENDING_CUSTOMER,
        TicketState.SPAM,
        TicketState.INVALID,
        TicketState.CLOSED,
    }

    LEGACY_STATUS_BY_STATE = {
        TicketState.NEW: "PENDING",
        TicketState.ASSIGNED: "IN_PROGRESS",
        TicketState.IN_PROGRESS: "IN_PROGRESS",
        TicketState.PENDING_CUSTOMER: "REPLIED",
        TicketState.PENDING_INTERNAL: "ESCALATE_HIGH",
        TicketState.RESOLVED: "RESOLVED",
        TicketState.CLOSED: "RESOLVED",
        TicketState.SPAM: "SPAM",
        TicketState.INVALID: "INVALID",
        TicketState.REOPENED: "IN_PROGRESS",
    }

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _normalize_value(value: str | None) -> str:
        return (value or "").strip().lower()

    @classmethod
    def _parse_state(cls, value: str | None) -> TicketState:
        normalized = cls._normalize_value(value)
        if not normalized:
            return TicketState.NEW
        return TicketState(normalized)

    @classmethod
    def default_actor(cls, actor: str | None = None) -> str:
        cleaned = (actor or "").strip()
        return cleaned or "system"

    def derive_state_from_legacy(self, ticket: Complaint, preserve_existing: bool = False) -> TicketState:
        explicit = self._normalize_value(ticket.state)
        if preserve_existing and explicit in TicketState._value2member_map_:
            return TicketState(explicit)

        if ticket.resolution_status == "resolved" or ticket.resolved_at:
            return TicketState.RESOLVED

        status = (ticket.status or "").strip().upper()
        if status in {"SPAM"}:
            return TicketState.SPAM
        if status in {"INVALID"}:
            return TicketState.INVALID
        if status in {"RESOLVED", "CLOSED"}:
            return TicketState.RESOLVED
        if status in {"ESCALATE_HIGH", "PROCESSING", "PROCESSED", "IN_PROGRESS", "REPLIED", "SENT"}:
            return TicketState.IN_PROGRESS
        if ticket.assigned_to or ticket.assigned_team:
            return TicketState.ASSIGNED
        if explicit in TicketState._value2member_map_:
            return TicketState(explicit)
        return TicketState.NEW

    def can_transition(self, from_state: str, to_state: str) -> Tuple[bool, Optional[str]]:
        if not self._normalize_value(to_state):
            return False, "Invalid state: blank value"
        try:
            from_enum = self._parse_state(from_state)
            to_enum = self._parse_state(to_state)
        except ValueError as e:
            return False, f"Invalid state: {e}"

        if to_enum in self.VALID_TRANSITIONS.get(from_enum, []):
            return True, None

        return False, f"Cannot transition from {from_state} to {to_state}"

    def transition(
        self,
        ticket: Complaint,
        to_state: str,
        transitioned_by: str,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        commit: bool = True,
    ) -> Tuple[bool, Optional[str]]:
        current_state = self.derive_state_from_legacy(ticket, preserve_existing=True).value
        to_state_norm = self._normalize_value(to_state)

        can_transition, error = self.can_transition(current_state, to_state_norm)
        if not can_transition:
            logger.warning(f"Invalid transition for ticket {ticket.id}: {current_state} -> {to_state_norm}")
            return False, error

        self._record_transition(
            ticket=ticket,
            from_state=current_state,
            to_state=to_state_norm,
            transitioned_by=transitioned_by,
            reason=reason,
            metadata=metadata,
        )

        self._ensure_ticket_number(ticket)
        ticket.state = to_state_norm
        ticket.state_changed_at = utcnow()

        self._handle_state_side_effects(ticket, to_state_norm, sync_legacy=True)
        self._refresh_sla_tracking(ticket)

        if commit:
            self.db.commit()
            self.db.refresh(ticket)
        else:
            self.db.flush()
        logger.info(f"Ticket {ticket.id}: {current_state} -> {to_state_norm} by {transitioned_by}")
        return True, None

    def sync_from_legacy(
        self,
        ticket: Complaint,
        transitioned_by: str = "system",
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        commit: bool = True,
    ) -> Tuple[bool, str]:
        actor = self.default_actor(transitioned_by)
        current_state = self.derive_state_from_legacy(ticket, preserve_existing=True).value
        target_state = self.derive_state_from_legacy(ticket, preserve_existing=False).value

        self._ensure_ticket_number(ticket)
        if current_state == target_state:
            ticket.state = target_state
            if not ticket.state_changed_at:
                ticket.state_changed_at = utcnow()
            self._handle_state_side_effects(ticket, target_state, sync_legacy=False)
            self._refresh_sla_tracking(ticket)
            if commit:
                self.db.commit()
                self.db.refresh(ticket)
            else:
                self.db.flush()
            return False, target_state

        can_transition, _ = self.can_transition(current_state, target_state)
        if can_transition:
            self._record_transition(
                ticket=ticket,
                from_state=current_state,
                to_state=target_state,
                transitioned_by=actor,
                reason=reason or "Legacy status sync",
                metadata=metadata,
            )
            ticket.state = target_state
            ticket.state_changed_at = utcnow()
            self._handle_state_side_effects(ticket, target_state, sync_legacy=False)
            self._refresh_sla_tracking(ticket)
            if commit:
                self.db.commit()
                self.db.refresh(ticket)
            else:
                self.db.flush()
            logger.info("Ticket %s synced from legacy fields: %s -> %s", ticket.id, current_state, target_state)
            return True, target_state

        self._record_transition(
            ticket=ticket,
            from_state=current_state,
            to_state=target_state,
            transitioned_by=actor,
            reason=reason or "Legacy status sync",
            metadata=metadata,
        )
        ticket.state = target_state
        ticket.state_changed_at = utcnow()
        self._handle_state_side_effects(ticket, target_state, sync_legacy=False)
        self._refresh_sla_tracking(ticket)
        if commit:
            self.db.commit()
            self.db.refresh(ticket)
        else:
            self.db.flush()
        logger.info("Ticket %s synced from legacy fields: %s -> %s", ticket.id, current_state, target_state)
        return True, target_state

    def ensure_ticket_number(self, ticket: Complaint, commit: bool = False) -> str | None:
        self._ensure_ticket_number(ticket)
        if commit:
            self.db.commit()
            self.db.refresh(ticket)
        else:
            self.db.flush()
        return ticket.ticket_number

    def _ensure_ticket_number(self, ticket: Complaint) -> None:
        if ticket.ticket_number or not ticket.ticket_id:
            return

        candidate = ticket.ticket_id
        conflict_query = self.db.query(Complaint.id).filter(Complaint.ticket_number == candidate)
        if ticket.id is not None:
            conflict_query = conflict_query.filter(Complaint.id != ticket.id)

        if conflict_query.first():
            ticket_id_suffix = str(ticket.id).split("-", 1)[0] if ticket.id else utcnow().strftime("%H%M%S")
            candidate = f"{ticket.ticket_id}-{ticket_id_suffix}"

        ticket.ticket_number = candidate[:50]

    def _record_transition(
        self,
        ticket: Complaint,
        from_state: str | None,
        to_state: str,
        transitioned_by: str,
        reason: Optional[str],
        metadata: Optional[Dict[str, Any]],
    ) -> None:
        transition_record = TicketStateTransition(
            complaint_id=ticket.id,
            from_state=from_state,
            to_state=to_state,
            transitioned_by=self.default_actor(transitioned_by),
            transition_reason=reason,
            metadata_json=metadata or {},
        )
        self.db.add(transition_record)

    def _handle_state_side_effects(self, ticket: Complaint, new_state: str, sync_legacy: bool) -> None:
        if new_state == TicketState.RESOLVED.value:
            ticket.resolved_at = ticket.resolved_at or utcnow()
            if sync_legacy or not ticket.resolution_status:
                ticket.resolution_status = "resolved"
            if ticket.first_response_at and ticket.created_at:
                ticket.response_time_seconds = ticket.response_time_seconds or int(
                    (ticket.first_response_at - ticket.created_at).total_seconds()
                )

        elif new_state == TicketState.REOPENED.value:
            ticket.reopened_count = (ticket.reopened_count or 0) + 1
            ticket.last_reopened_at = utcnow()
            ticket.resolved_at = None
            if sync_legacy or ticket.resolution_status == "resolved":
                ticket.resolution_status = "open"

        elif new_state == TicketState.CLOSED.value:
            if not ticket.resolved_at:
                ticket.resolved_at = utcnow()
            if sync_legacy or not ticket.resolution_status:
                ticket.resolution_status = "resolved"
        elif sync_legacy:
            ticket.resolution_status = "open"
            ticket.resolved_at = None
        elif ticket.resolution_status != "resolved":
            ticket.resolved_at = None

        if sync_legacy:
            legacy_status = self.LEGACY_STATUS_BY_STATE.get(TicketState(new_state))
            if legacy_status:
                ticket.status = legacy_status

    def _refresh_sla_tracking(self, ticket: Complaint) -> None:
        from app.services.sla_manager import SLAManager

        SLAManager(self.db).refresh_ticket_deadline(ticket, commit=False)
