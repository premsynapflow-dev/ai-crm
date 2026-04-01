"""
Multi-level escalation engine for SynapFlow compliance system.

Handles:
- Automatic escalation based on time thresholds
- Multi-level escalation (L1 → L2 → Internal Ombudsman)
- Fallback to Internal Ombudsman at 30 days
- Audit trail and notifications
- Duplicate prevention
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from enum import Enum

from sqlalchemy import and_, desc
from sqlalchemy.orm import Session

from app.db.models import (
    Complaint,
    Conversation,
    Escalation,
    EscalationLevelDefinition,
    EscalationRule,
    RBIComplaint,
    AuditLog,
)
from app.services.audit_logs import append_audit_log
from app.config import get_settings


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EscalationTriggerReason(str, Enum):
    SLA_BREACH = "sla_breach"
    SLA_APPROACHING = "sla_approaching"
    TAT_BREACH = "tat_breach"
    TAT_APPROACHING = "tat_approaching"
    TIME_THRESHOLD = "time_threshold"
    MANUAL = "manual"
    RBI_ESCALATION_POLICY = "rbi_escalation_policy"


class EscalationStatus(str, Enum):
    PENDING = "pending"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    FAILED = "failed"


class EscalationEngine:
    """
    Manages multi-level escalation workflow.
    
    Escalation Flow:
    L1 (Regional Manager) → 24 hours if no resolution
    L2 (Ombudsman Staff)  → 48 hours if no resolution
    IO (Internal Ombudsman) → 30 days (fallback)
    """

    INTERNAL_OMBUDSMAN = "system@io"
    DEFAULT_ESCALATION_HOURS = 30 * 24  # 30 days fallback

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    def get_or_create_escalation_levels(self, client_id: uuid.UUID) -> dict[str, EscalationLevelDefinition]:
        """
        Ensure standard escalation levels exist for client.
        Creates L1, L2, IO if missing.
        """
        levels = {}

        # L1 - Regional Manager (24 hours)
        l1 = self.db.query(EscalationLevelDefinition).filter(
            EscalationLevelDefinition.client_id == client_id,
            EscalationLevelDefinition.level_code == "L1",
        ).first()

        if not l1:
            l1 = EscalationLevelDefinition(
                client_id=client_id,
                level_code="L1",
                level_number=1,
                trigger_after_hours=24,
                escalate_to_role="regional_manager@rbi",
                description="Level 1: Regional Manager",
                is_active=True,
            )
            self.db.add(l1)

        levels["L1"] = l1

        # L2 - Ombudsman Staff (48 hours)
        l2 = self.db.query(EscalationLevelDefinition).filter(
            EscalationLevelDefinition.client_id == client_id,
            EscalationLevelDefinition.level_code == "L2",
        ).first()

        if not l2:
            l2 = EscalationLevelDefinition(
                client_id=client_id,
                level_code="L2",
                level_number=2,
                trigger_after_hours=48,
                escalate_to_role="ombudsman_staff@rbi",
                description="Level 2: Ombudsman Staff",
                is_active=True,
            )
            self.db.add(l2)

        levels["L2"] = l2

        # IO - Internal Ombudsman (30 days)
        io = self.db.query(EscalationLevelDefinition).filter(
            EscalationLevelDefinition.client_id == client_id,
            EscalationLevelDefinition.level_code == "IO",
        ).first()

        if not io:
            io = EscalationLevelDefinition(
                client_id=client_id,
                level_code="IO",
                level_number=3,
                trigger_after_hours=self.DEFAULT_ESCALATION_HOURS,
                escalate_to_role=self.INTERNAL_OMBUDSMAN,
                description="Level 3: Internal Ombudsman (Final)",
                is_active=True,
            )
            self.db.add(io)

        levels["IO"] = io
        self.db.flush()
        return levels

    def get_next_escalation_level(
        self,
        client_id: uuid.UUID,
        current_level: int,
    ) -> Optional[EscalationLevelDefinition]:
        """
        Determine next escalation level.
        Returns None if already at max level (IO).
        """
        next_level_number = current_level + 1

        next_level = self.db.query(EscalationLevelDefinition).filter(
            EscalationLevelDefinition.client_id == client_id,
            EscalationLevelDefinition.level_number == next_level_number,
            EscalationLevelDefinition.is_active == True,
        ).order_by(EscalationLevelDefinition.level_number.asc()).first()

        return next_level

    def should_escalate(
        self,
        complaint: Complaint,
        current_escalation_level: int,
        hours_open: float,
    ) -> tuple[bool, Optional[EscalationLevelDefinition], str]:
        """
        Determine if ticket should escalate to next level.

        Returns:
            (should_escalate, next_level, reason)
        """
        # If resolved, no escalation needed
        if complaint.resolution_status == "resolved" or complaint.status in ("RESOLVED", "CLOSED"):
            return False, None, "ticket_resolved"

        # If already at max level (IO), no further escalation
        if current_escalation_level >= 3:
            return False, None, "max_level_reached"

        # Get next escalation level
        next_level = self.get_next_escalation_level(complaint.client_id, current_escalation_level)
        if not next_level:
            return False, None, "no_next_level"

        # Check if threshold met
        if hours_open >= next_level.trigger_after_hours:
            return True, next_level, f"threshold_met_{next_level.level_code}"

        return False, None, "not_ready_for_escalation"

    def has_recent_escalation(
        self,
        ticket_id: uuid.UUID,
        within_minutes: int = 5,
    ) -> bool:
        """
        Check if ticket was escalated recently (prevent duplicates).
        """
        recent_cutoff = _utcnow() - timedelta(minutes=within_minutes)

        escalation = self.db.query(Escalation).filter(
            Escalation.ticket_id == ticket_id,
            Escalation.created_at >= recent_cutoff,
        ).first()

        return escalation is not None

    def calculate_hours_since_creation(self, complaint: Complaint) -> float:
        """Calculate hours since ticket creation."""
        if not complaint.created_at:
            return 0
        return (complaint.created_at.replace(tzinfo=timezone.utc) - _utcnow()).total_seconds() / 3600

    def calculate_next_escalation_eta(
        self,
        complaint: Complaint,
        current_escalation_level: int,
    ) -> Optional[datetime]:
        """
        Calculate expected escalation time.
        """
        next_level = self.get_next_escalation_level(complaint.client_id, current_escalation_level)
        if not next_level:
            return None

        if not complaint.created_at:
            return None

        eta = complaint.created_at.replace(tzinfo=timezone.utc) + timedelta(
            hours=next_level.trigger_after_hours
        )
        return eta

    def escalate(
        self,
        complaint: Complaint,
        reason: EscalationTriggerReason,
        escalated_by: str = "system",
        metadata: Optional[dict[str, Any]] = None,
        commit: bool = True,
    ) -> Escalation:
        """
        Escalate a ticket to the next level.

        Args:
            complaint: The complaint to escalate
            reason: Reason for escalation
            escalated_by: Who triggered the escalation
            metadata: Additional context
            commit: Whether to commit changes

        Returns:
            Created Escalation record
        """
        if metadata is None:
            metadata = {}

        # Prevent duplicate escalations
        if self.has_recent_escalation(complaint.id):
            raise RuntimeError(f"Ticket {complaint.id} was recently escalated. Preventing duplicate.")

        # Determine next level
        current_level = complaint.escalation_level or 0
        next_level = self.get_next_escalation_level(complaint.client_id, current_level)

        if not next_level:
            raise ValueError(f"No next escalation level available for level {current_level}")

        # Create escalation record
        escalation = Escalation(
            ticket_id=complaint.id,
            level=next_level.level_number,
            escalated_to=next_level.escalate_to_role,
            reason=reason.value,
            escalation_level_id=next_level.id,
            metadata_json={
                "previous_level": current_level,
                "current_level": next_level.level_number,
                "reason": reason.value,
                "escalated_by": escalated_by,
                "triggered_at": _utcnow().isoformat(),
                "hours_open": self.calculate_hours_since_creation(complaint),
                **metadata,
            },
            next_escalation_at=self.calculate_next_escalation_eta(complaint, next_level.level_number),
        )

        # Update complaint escalation fields
        old_escalation_level = complaint.escalation_level or 0
        complaint.escalation_level = next_level.level_number
        complaint.escalated_at = _utcnow()
        complaint.escalated_to = next_level.escalate_to_role

        # Update conversation if linked
        if complaint.thread_id:
            conversation = self.db.query(Conversation).filter(
                Conversation.external_thread_id == complaint.thread_id,
                Conversation.client_id == complaint.client_id,
            ).first()

            if conversation:
                conversation.escalation_level = next_level.level_number
                conversation.last_escalated_at = _utcnow()
                conversation.escalation_metadata_json = {
                    "level_code": next_level.level_code,
                    "escalate_to_role": next_level.escalate_to_role,
                    "reason": reason.value,
                }

        # Audit log
        append_audit_log(
            self.db,
            entity_type="complaint",
            entity_id=complaint.id,
            action=f"escalated_to_{next_level.level_code}",
            performed_by=escalated_by,
            old_value={
                "escalation_level": old_escalation_level,
                "escalated_to": complaint.escalated_to,
            },
            new_value={
                "escalation_level": next_level.level_number,
                "escalated_to": next_level.escalate_to_role,
                "reason": reason.value,
            },
        )

        self.db.add(escalation)

        if commit:
            self.db.commit()
            self.db.refresh(escalation)
        else:
            self.db.flush()

        return escalation

    def process_pending_escalations(self, client_id: uuid.UUID, dry_run: bool = False) -> dict[str, Any]:
        """
        Check all open tickets and escalate if thresholds met.

        Returns statistics about escalations performed.
        """
        stats = {
            "checked": 0,
            "escalated": 0,
            "errors": 0,
            "escalations": [],
        }

        # Ensure levels exist
        self.get_or_create_escalation_levels(client_id)

        # Get all open RBI complaints
        complaints = self.db.query(Complaint).filter(
            Complaint.client_id == client_id,
            Complaint.resolution_status != "resolved",
            Complaint.status.notin_(["RESOLVED", "CLOSED"]),
            Complaint.rbi_category_code.isnot(None),
        ).all()

        for complaint in complaints:
            try:
                stats["checked"] += 1
                hours_open = self.calculate_hours_since_creation(complaint)
                current_level = complaint.escalation_level or 0

                should_escalate_bool, next_level, reason_msg = self.should_escalate(
                    complaint,
                    current_level,
                    hours_open,
                )

                if should_escalate_bool and next_level:
                    if not dry_run:
                        escalation = self.escalate(
                            complaint,
                            reason=EscalationTriggerReason.TIME_THRESHOLD,
                            escalated_by="escalation_engine",
                            metadata={
                                "hours_open": hours_open,
                                "threshold": next_level.trigger_after_hours,
                            },
                        )
                        stats["escalations"].append({
                            "ticket_id": str(complaint.id),
                            "from_level": current_level,
                            "to_level": next_level.level_number,
                            "escalated_to": next_level.escalate_to_role,
                        })

                    stats["escalated"] += 1

            except Exception as e:
                stats["errors"] += 1
                stats.get("escalations", []).append({
                    "error": str(e),
                    "ticket_id": str(complaint.id) if complaint else "unknown",
                })

        return stats

    def get_escalation_history(self, ticket_id: uuid.UUID) -> list[dict[str, Any]]:
        """Get full escalation history for a ticket."""
        escalations = self.db.query(Escalation).filter(
            Escalation.ticket_id == ticket_id
        ).order_by(desc(Escalation.created_at)).all()

        result = []
        for esc in escalations:
            result.append({
                "id": str(esc.id),
                "level": esc.level,
                "level_code": esc.escalation_level_id and self.db.query(EscalationLevelDefinition).filter(
                    EscalationLevelDefinition.id == esc.escalation_level_id
                ).first().level_code,
                "escalated_to": esc.escalated_to,
                "reason": esc.reason,
                "metadata": esc.metadata_json,
                "created_at": esc.created_at.isoformat() if esc.created_at else None,
                "next_escalation_at": esc.next_escalation_at.isoformat() if esc.next_escalation_at else None,
            })

        return result

    def get_escalation_status(self, ticket_id: uuid.UUID) -> dict[str, Any]:
        """Get current escalation status and next escalation ETA."""
        complaint = self.db.query(Complaint).filter(Complaint.id == ticket_id).first()

        if not complaint:
            raise ValueError(f"Complaint {ticket_id} not found")

        current_level = complaint.escalation_level or 0
        hours_open = self.calculate_hours_since_creation(complaint)
        next_level = self.get_next_escalation_level(complaint.client_id, current_level)
        next_eta = self.calculate_next_escalation_eta(complaint, current_level)

        return {
            "ticket_id": str(ticket_id),
            "current_level": current_level,
            "current_level_name": self.db.query(EscalationLevelDefinition).filter(
                EscalationLevelDefinition.client_id == complaint.client_id,
                EscalationLevelDefinition.level_number == current_level,
            ).first().level_code if current_level > 0 else "NONE",
            "hours_open": hours_open,
            "is_resolved": complaint.resolution_status == "resolved" or complaint.status in ("RESOLVED", "CLOSED"),
            "next_escalation_level": {
                "level": next_level.level_number,
                "code": next_level.level_code,
                "escalate_to": next_level.escalate_to_role,
                "trigger_after_hours": next_level.trigger_after_hours,
                "eta": next_eta.isoformat() if next_eta else None,
                "hours_remaining": max(0, next_level.trigger_after_hours - hours_open),
            } if next_level else None,
            "escalation_history": self.get_escalation_history(ticket_id),
        }
