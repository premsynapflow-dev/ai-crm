import pytz
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import BusinessHours, Complaint, EscalationRule, SLAPolicy


class SLAManager:
    def __init__(self, db: Session):
        self.db = db
        self.default_timezone = get_settings().default_timezone

    def calculate_sla_due_date(
        self, ticket: Complaint, sla_policy: Optional[SLAPolicy] = None
    ) -> Optional[datetime]:
        if not sla_policy:
            sla_policy = self._get_sla_policy(ticket)

        if not sla_policy:
            return None

        base_time = self._as_utc(ticket.created_at or datetime.now(timezone.utc))
        minutes_to_add = (
            sla_policy.first_response_minutes
            if not ticket.first_response_at
            else sla_policy.resolution_minutes
        )

        if sla_policy.business_hours_only:
            return self._calculate_business_hours_deadline(
                ticket.client_id,
                base_time,
                minutes_to_add,
                sla_policy.timezone or self.default_timezone,
            )
        return base_time + timedelta(minutes=minutes_to_add)

    def refresh_ticket_deadline(self, ticket: Complaint, commit: bool = False) -> Optional[datetime]:
        if ticket.resolved_at or ticket.state in {"closed", "spam", "invalid"}:
            ticket.sla_status = "on_track"
            if commit:
                self.db.commit()
                self.db.refresh(ticket)
            else:
                self.db.flush()
            return ticket.sla_due_at

        ticket.sla_due_at = self.calculate_sla_due_date(ticket)
        self.update_sla_status(ticket, commit=False)
        if commit:
            self.db.commit()
            self.db.refresh(ticket)
        else:
            self.db.flush()
        return ticket.sla_due_at

    def _calculate_business_hours_deadline(
        self, client_id: str, start_time: datetime, minutes_to_add: int, timezone: str
    ) -> datetime:
        tz = self._safe_timezone(timezone)
        current = self._as_utc(start_time).astimezone(tz)
        remaining_minutes = minutes_to_add

        business_hours = (
            self.db.query(BusinessHours)
            .filter(and_(BusinessHours.client_id == client_id, BusinessHours.enabled == True))
            .all()
        )

        if not business_hours:
            return start_time + timedelta(minutes=minutes_to_add)

        hours_map: Dict[int, tuple] = {
            bh.day_of_week: (bh.start_time, bh.end_time) for bh in business_hours
        }

        max_iterations = 365
        iteration = 0

        while remaining_minutes > 0 and iteration < max_iterations:
            day_of_week = current.weekday()

            if day_of_week not in hours_map:
                current = (current + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                iteration += 1
                continue

            start_time_obj, end_time_obj = hours_map[day_of_week]
            day_start = current.replace(
                hour=start_time_obj.hour,
                minute=start_time_obj.minute,
                second=0,
                microsecond=0,
            )
            day_end = current.replace(
                hour=end_time_obj.hour,
                minute=end_time_obj.minute,
                second=0,
                microsecond=0,
            )

            if current < day_start:
                current = day_start

            if current >= day_end:
                current = (current + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                iteration += 1
                continue

            available_minutes = int((day_end - current).total_seconds() / 60)

            if available_minutes >= remaining_minutes:
                current = current + timedelta(minutes=remaining_minutes)
                remaining_minutes = 0
            else:
                remaining_minutes -= available_minutes
                current = (current + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

            iteration += 1

        return current.astimezone(pytz.UTC)

    def _get_sla_policy(self, ticket: Complaint) -> Optional[SLAPolicy]:
        priority_level = self._priority_level(ticket.priority)

        return (
            self.db.query(SLAPolicy)
            .filter(
                and_(
                    SLAPolicy.client_id == ticket.client_id,
                    SLAPolicy.priority_level == priority_level,
                    SLAPolicy.enabled == True,
                )
            )
            .first()
        )

    def update_sla_status(self, ticket: Complaint, commit: bool = False) -> str:
        if not ticket.sla_due_at or ticket.resolved_at or ticket.state in {"closed", "spam", "invalid"}:
            ticket.sla_status = "on_track"
            if commit:
                self.db.commit()
            else:
                self.db.flush()
            return "on_track"

        now = datetime.now(timezone.utc)
        time_remaining = (self._as_utc(ticket.sla_due_at) - now).total_seconds()

        if time_remaining < 0:
            ticket.sla_status = "breached"
            self._handle_sla_breach(ticket, commit=False)
            if commit:
                self.db.commit()
            else:
                self.db.flush()
            return "breached"

        sla_policy = self._get_sla_policy(ticket)
        if sla_policy:
            total_minutes = (
                sla_policy.first_response_minutes
                if not ticket.first_response_at
                else sla_policy.resolution_minutes
            )
            threshold_minutes = sla_policy.escalation_threshold_minutes or max(1, int(total_minutes * 0.25))
            at_risk_threshold = threshold_minutes * 60

            if time_remaining < at_risk_threshold:
                ticket.sla_status = "at_risk"
                if commit:
                    self.db.commit()
                else:
                    self.db.flush()
                return "at_risk"

        ticket.sla_status = "on_track"
        if commit:
            self.db.commit()
        else:
            self.db.flush()
        return "on_track"

    def _handle_sla_breach(self, ticket: Complaint, commit: bool = False):
        if ticket.escalation_level and ticket.escalation_level > 0:
            return

        escalation_rule = (
            self.db.query(EscalationRule)
            .filter(
                and_(
                    EscalationRule.client_id == ticket.client_id,
                    EscalationRule.trigger_condition == "sla_breach",
                    EscalationRule.enabled == True,
                )
            )
            .first()
        )

        if escalation_rule:
            self.escalate_ticket(ticket, escalation_rule, commit=commit)

    def escalate_ticket(self, ticket: Complaint, escalation_rule: EscalationRule, commit: bool = True):
        ticket.escalation_level = escalation_rule.escalation_level
        ticket.escalated_at = datetime.now(timezone.utc)
        ticket.escalated_to = escalation_rule.escalate_to_email or escalation_rule.escalate_to_team
        if commit:
            self.db.commit()
        else:
            self.db.flush()

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _safe_timezone(self, timezone_name: str | None):
        try:
            return pytz.timezone(timezone_name or self.default_timezone)
        except pytz.UnknownTimeZoneError:
            return pytz.timezone(self.default_timezone)

    @staticmethod
    def _priority_level(priority: int | None) -> str:
        if priority is None:
            return "medium"
        if priority >= 5:
            return "critical"
        if priority in {3, 4}:
            return "high"
        if priority == 2:
            return "medium"
        return "low"

    def breach_probability(self, ticket: Complaint) -> float:
        """
        Return a 0.0–1.0 score estimating likelihood of SLA breach.

        Factors:
          - time_remaining_ratio: fraction of SLA window remaining
          - urgency_weight: higher urgency = faster degradation
          - unassigned_penalty: +0.30 if no agent assigned
          - escalation_penalty: +0.20 if already escalated
        """
        if not ticket.sla_due_at or ticket.resolved_at:
            return 0.0

        now = datetime.now(timezone.utc)
        sla_due = self._as_utc(ticket.sla_due_at)
        time_remaining = (sla_due - now).total_seconds()
        if time_remaining <= 0:
            return 1.0

        # Estimate total SLA window from priority
        _priority_windows = {1: 72 * 3600, 2: 24 * 3600, 3: 4 * 3600}
        sla_window = _priority_windows.get(ticket.priority, 24 * 3600)
        time_remaining_ratio = max(0.0, min(1.0, time_remaining / sla_window))
        base_risk = 1.0 - time_remaining_ratio

        urgency_weight = 1.0 + (ticket.urgency_score or 0.0) * 0.5
        unassigned_penalty = 0.30 if not ticket.assigned_user_id else 0.0
        escalation_penalty = 0.20 if (ticket.escalation_level or 0) > 0 else 0.0

        return round(min(1.0, (base_risk * urgency_weight) + unassigned_penalty + escalation_penalty), 3)

    def update_approaching_status(self, ticket: Complaint, approaching_threshold_seconds: int = 3600) -> str:
        """Mark ticket sla_status='approaching' if within threshold of breach but not yet breached."""
        if not ticket.sla_due_at or ticket.resolved_at:
            return ticket.sla_status or "on_track"
        now = datetime.now(timezone.utc)
        time_remaining = (self._as_utc(ticket.sla_due_at) - now).total_seconds()
        if 0 < time_remaining <= approaching_threshold_seconds and ticket.sla_status not in ("breached",):
            ticket.sla_status = "approaching"
            self.db.flush()
            return "approaching"
        return ticket.sla_status or "on_track"
