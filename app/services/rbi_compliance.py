from datetime import datetime, timedelta, timezone
import uuid
from typing import Any

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Complaint, Escalation, RBIComplaint, RBIComplaintCategory, RBIEscalationLog, RBIMISReport, RBITATRule
from app.services.audit_logs import append_audit_log, list_entity_audit_logs, serialize_audit_log
from app.services.rbi_taxonomy_classifier import RBITaxonomyClassifier


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RBIComplianceService:
    INTERNAL_OMBUDSMAN = "Internal Ombudsman"

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    def _resolve_category(self, category_code: str | None, subcategory_code: str | None) -> RBIComplaintCategory | None:
        if not category_code:
            return None
        query = self.db.query(RBIComplaintCategory).filter(
            RBIComplaintCategory.category_code == category_code,
            RBIComplaintCategory.is_active == True,
        )
        if subcategory_code:
            query = query.filter(RBIComplaintCategory.subcategory_code == subcategory_code)
        return query.first()

    def _get_tat_days_for_client_category(self, client_id: uuid.UUID, category_code: str | None) -> int | None:
        """
        Fetch TAT days from rbi_tat_rules table for a specific client and category.
        Returns None if no rule exists (will use fallback).
        """
        if not category_code:
            return None
        rule = self.db.query(RBITATRule).filter(
            RBITATRule.client_id == client_id,
            RBITATRule.category_code == category_code,
            RBITATRule.is_active == True,
        ).first()
        return rule.tat_days if rule else None

    def _resolve_tat_due_at(self, complaint: Complaint, category: RBIComplaintCategory | None, client_id: uuid.UUID | None = None) -> datetime:
        """
        Resolve TAT due date with priority:
        1. Client-specific rule (rbi_tat_rules)
        2. Category default (rbi_complaint_categories.tat_days)
        3. System default (config.rbi_tat_default_days)
        """
        if complaint.tat_due_at:
            return complaint.tat_due_at
        
        # Try to fetch client-specific TAT rule
        tat_days = None
        if client_id:
            category_code = complaint.rbi_category_code or category.category_code if category else None
            tat_days = self._get_tat_days_for_client_category(client_id, category_code)
        
        # Fallback to category default
        if tat_days is None:
            tat_days = category.tat_days if category else self.settings.rbi_tat_default_days
        
        created_at = complaint.created_at or _utcnow()
        return created_at + timedelta(days=tat_days)

    def _calculate_tat_state(self, complaint: Complaint, tat_due_at: datetime | None) -> tuple[str, datetime | None, int]:
        if tat_due_at is None:
            return "not_applicable", None, 0

        if complaint.resolved_at:
            if complaint.resolved_at > tat_due_at:
                delta = complaint.resolved_at - tat_due_at
                return "breached", complaint.tat_breached_at or tat_due_at, int(delta.total_seconds() // 3600)
            return "resolved", complaint.tat_breached_at, 0

        now = _utcnow()
        if now > tat_due_at:
            delta = now - tat_due_at
            return "breached", complaint.tat_breached_at or tat_due_at, int(delta.total_seconds() // 3600)
        if (tat_due_at - now).total_seconds() < 86400 * 5:
            return "approaching_breach", complaint.tat_breached_at, 0
        return "within_tat", complaint.tat_breached_at, 0

    def _sync_ticket_compliance_fields(
        self,
        complaint: Complaint,
        *,
        category_code: str | None,
        tat_due_at: datetime | None,
        tat_status: str,
        tat_breached_at: datetime | None,
    ) -> None:
        complaint.rbi_category_code = category_code or complaint.rbi_category_code
        complaint.tat_due_at = tat_due_at
        complaint.tat_status = tat_status
        complaint.tat_breached_at = tat_breached_at

    def _ticket_snapshot(self, complaint: Complaint) -> dict[str, Any]:
        return {
            "ticket_id": complaint.ticket_id,
            "status": complaint.status,
            "resolution_status": complaint.resolution_status,
            "escalation_level": complaint.escalation_level,
            "escalated_to": complaint.escalated_to,
            "rbi_category_code": complaint.rbi_category_code,
            "tat_due_at": complaint.tat_due_at,
            "tat_status": complaint.tat_status,
            "tat_breached_at": complaint.tat_breached_at,
        }

    def register_rbi_complaint(
        self,
        complaint: Complaint,
        category_code: str | None = None,
        subcategory_code: str | None = None,
        commit: bool = True,
    ) -> RBIComplaint:
        existing = self.db.query(RBIComplaint).filter(RBIComplaint.complaint_id == complaint.id).first()
        if existing:
            self.sync_from_complaint(complaint, commit=commit)
            return existing

        resolved_category_code = category_code or complaint.rbi_category_code
        resolved_subcategory_code = subcategory_code
        if not resolved_category_code or not resolved_subcategory_code:
            resolved_category_code, resolved_subcategory_code, _ = RBITaxonomyClassifier(self.db).classify(
                complaint.summary or ""
            )

        category = self._resolve_category(resolved_category_code, resolved_subcategory_code)
        tat_due_date = self._resolve_tat_due_at(complaint, category, client_id=complaint.client_id)
        tat_status, tat_breached_at, tat_breach_hours = self._calculate_tat_state(complaint, tat_due_date)
        rbi_reference = self._generate_rbi_reference(complaint.client_id)

        self._sync_ticket_compliance_fields(
            complaint,
            category_code=resolved_category_code,
            tat_due_at=tat_due_date,
            tat_status=tat_status,
            tat_breached_at=tat_breached_at,
        )

        rbi_complaint = RBIComplaint(
            complaint_id=complaint.id,
            client_id=complaint.client_id,
            rbi_category_id=category.id if category else None,
            category_code=resolved_category_code,
            subcategory_code=resolved_subcategory_code,
            rbi_reference_number=rbi_reference,
            tat_due_date=tat_due_date,
            tat_status=tat_status,
            tat_breach_hours=tat_breach_hours,
            resolution_date=complaint.resolved_at,
            resolution_summary=complaint.ai_reply if complaint.resolution_status == "resolved" else None,
            customer_satisfied=(complaint.satisfaction_score or complaint.customer_satisfaction_score or 0) >= 4
            if (complaint.satisfaction_score or complaint.customer_satisfaction_score) is not None
            else None,
            audit_log=[
                {
                    "timestamp": _utcnow().isoformat(),
                    "event": "complaint_registered",
                    "details": {
                        "category": resolved_category_code,
                        "subcategory": resolved_subcategory_code,
                        "tat_due_at": tat_due_date.isoformat() if tat_due_date else None,
                    },
                }
            ],
        )
        self.db.add(rbi_complaint)
        self.check_tat_compliance(rbi_complaint)
        append_audit_log(
            self.db,
            entity_type="ticket",
            entity_id=complaint.id,
            action="rbi_compliance_registered",
            performed_by="system",
            old_value=None,
            new_value={
                "rbi_category_code": complaint.rbi_category_code,
                "tat_due_at": complaint.tat_due_at,
                "tat_status": complaint.tat_status,
            },
        )

        if commit:
            self.db.commit()
            self.db.refresh(rbi_complaint)
        else:
            self.db.flush()
        return rbi_complaint

    def sync_from_complaint(self, complaint: Complaint, commit: bool = True) -> RBIComplaint | None:
        rbi_complaint = self.db.query(RBIComplaint).filter(RBIComplaint.complaint_id == complaint.id).first()
        if rbi_complaint is None:
            return None

        if complaint.rbi_category_code and complaint.rbi_category_code != rbi_complaint.category_code:
            rbi_complaint.category_code = complaint.rbi_category_code
        rbi_complaint.resolution_date = complaint.resolved_at
        if complaint.resolution_status == "resolved" and complaint.ai_reply:
            rbi_complaint.resolution_summary = complaint.ai_reply
        satisfaction_score = complaint.satisfaction_score or complaint.customer_satisfaction_score
        if satisfaction_score is not None:
            rbi_complaint.customer_satisfied = satisfaction_score >= 4
        previous_status = complaint.tat_status
        current_status = self.check_tat_compliance(rbi_complaint)
        self._append_audit_event(
            rbi_complaint,
            "complaint_synced",
            {
                "resolution_status": complaint.resolution_status,
                "state": complaint.state,
                "escalation_level": complaint.escalation_level,
            },
        )
        if current_status != previous_status:
            self._append_audit_event(
                rbi_complaint,
                "tat_status_updated",
                {
                    "from_status": previous_status,
                    "to_status": current_status,
                },
            )

        if complaint.escalation_level and complaint.escalation_level > rbi_complaint.escalation_level:
            self.escalate_level(
                rbi_complaint,
                to_level=min(3, int(complaint.escalation_level)),
                escalated_by="system",
                reason="Complaint escalation synced",
                commit=False,
            )

        if commit:
            self.db.commit()
            self.db.refresh(rbi_complaint)
        else:
            self.db.flush()
        return rbi_complaint

    def check_tat_compliance(self, rbi_complaint: RBIComplaint) -> str:
        complaint = rbi_complaint.complaint or self.db.query(Complaint).filter(Complaint.id == rbi_complaint.complaint_id).first()
        if complaint is None:
            return rbi_complaint.tat_status

        tat_due_at = complaint.tat_due_at or rbi_complaint.tat_due_date or self._resolve_tat_due_at(
            complaint,
            self._resolve_category(rbi_complaint.category_code, rbi_complaint.subcategory_code),
            client_id=rbi_complaint.client_id,
        )
        previous_status = rbi_complaint.tat_status
        tat_status, tat_breached_at, tat_breach_hours = self._calculate_tat_state(complaint, tat_due_at)

        self._sync_ticket_compliance_fields(
            complaint,
            category_code=rbi_complaint.category_code,
            tat_due_at=tat_due_at,
            tat_status=tat_status,
            tat_breached_at=tat_breached_at,
        )
        rbi_complaint.tat_due_date = tat_due_at
        rbi_complaint.tat_status = tat_status
        rbi_complaint.tat_breach_hours = tat_breach_hours
        rbi_complaint.resolution_date = complaint.resolved_at

        if previous_status != "breached" and tat_status == "breached":
            self._append_audit_event(
                rbi_complaint,
                "tat_breached",
                {
                    "ticket_id": complaint.ticket_id,
                    "tat_due_at": tat_due_at.isoformat() if tat_due_at else None,
                },
            )
            append_audit_log(
                self.db,
                entity_type="ticket",
                entity_id=complaint.id,
                action="tat_breached",
                performed_by="system",
                old_value={"tat_status": previous_status},
                new_value={
                    "tat_status": tat_status,
                    "tat_due_at": tat_due_at,
                    "tat_breached_at": tat_breached_at,
                },
            )
        return tat_status

    def escalate_level(
        self,
        rbi_complaint: RBIComplaint,
        to_level: int,
        escalated_by: str,
        reason: str,
        metadata: dict[str, Any] | None = None,
        commit: bool = True,
    ) -> RBIComplaint:
        from_level = int(rbi_complaint.escalation_level or 0)
        if to_level <= from_level:
            return rbi_complaint

        rbi_complaint.escalation_level = to_level
        if to_level >= 3:
            rbi_complaint.escalated_to_rbi = True
            rbi_complaint.rbi_escalation_date = _utcnow()

        self._append_audit_event(
            rbi_complaint,
            "escalated",
            {
                "from_level": from_level,
                "to_level": to_level,
                "reason": reason,
                "escalated_by": escalated_by,
                **(metadata or {}),
            },
        )
        self.db.add(
            RBIEscalationLog(
                rbi_complaint_id=rbi_complaint.id,
                from_level=from_level,
                to_level=to_level,
                escalation_reason=reason,
                escalated_by=escalated_by,
                metadata_json=metadata or {},
            )
        )

        if commit:
            self.db.commit()
            self.db.refresh(rbi_complaint)
        else:
            self.db.flush()
        return rbi_complaint

    def escalate_to_rbi(self, rbi_complaint: RBIComplaint, escalated_by: str, commit: bool = True) -> RBIComplaint:
        complaint = rbi_complaint.complaint or self.db.query(Complaint).filter(Complaint.id == rbi_complaint.complaint_id).first()
        if complaint is not None:
            self.escalate_to_internal_ombudsman(
                complaint,
                reason="Escalated to Internal Ombudsman",
                escalated_by=escalated_by,
                commit=False,
            )
        self._append_audit_event(
            rbi_complaint,
            "internal_ombudsman_escalation_requested",
            {"escalated_by": escalated_by},
        )
        if commit:
            self.db.commit()
            self.db.refresh(rbi_complaint)
        else:
            self.db.flush()
        return rbi_complaint

    def escalate_to_internal_ombudsman(
        self,
        complaint: Complaint,
        *,
        reason: str,
        escalated_by: str,
        commit: bool = True,
    ) -> tuple[Escalation, bool]:
        existing = (
            self.db.query(Escalation)
            .filter(
                Escalation.ticket_id == complaint.id,
                Escalation.escalated_to == self.INTERNAL_OMBUDSMAN,
            )
            .order_by(Escalation.created_at.desc())
            .first()
        )
        if existing is not None:
            return existing, False

        old_snapshot = self._ticket_snapshot(complaint)
        complaint.escalation_level = max(int(complaint.escalation_level or 0), 1)
        complaint.escalated_at = complaint.escalated_at or _utcnow()
        complaint.escalated_to = self.INTERNAL_OMBUDSMAN

        escalation = Escalation(
            ticket_id=complaint.id,
            level=complaint.escalation_level,
            escalated_to=self.INTERNAL_OMBUDSMAN,
            reason=reason,
        )
        self.db.add(escalation)

        rbi_complaint = complaint.rbi_complaint or self.db.query(RBIComplaint).filter(RBIComplaint.complaint_id == complaint.id).first()
        if rbi_complaint is not None and complaint.escalation_level > rbi_complaint.escalation_level:
            self.escalate_level(
                rbi_complaint,
                to_level=complaint.escalation_level,
                escalated_by=escalated_by,
                reason=reason,
                metadata={"target": "internal_ombudsman"},
                commit=False,
            )

        append_audit_log(
            self.db,
            entity_type="ticket",
            entity_id=complaint.id,
            action="escalation_triggered",
            performed_by=escalated_by,
            old_value=old_snapshot,
            new_value=self._ticket_snapshot(complaint),
        )

        if commit:
            self.db.commit()
            self.db.refresh(escalation)
        else:
            self.db.flush()
        return escalation, True

    def process_tat_monitor(self, limit: int = 500) -> tuple[int, int]:
        records = (
            self.db.query(RBIComplaint)
            .filter(RBIComplaint.resolution_date.is_(None))
            .order_by(RBIComplaint.tat_due_date.asc())
            .limit(limit)
            .all()
        )

        updated = 0
        escalated = 0
        for rbi_complaint in records:
            complaint = rbi_complaint.complaint or self.db.query(Complaint).filter(Complaint.id == rbi_complaint.complaint_id).first()
            previous_status = complaint.tat_status if complaint is not None else rbi_complaint.tat_status
            new_status = self.check_tat_compliance(rbi_complaint)
            if new_status != previous_status:
                updated += 1
            if complaint is not None and new_status == "breached" and complaint.resolution_status != "resolved":
                _, created = self.escalate_to_internal_ombudsman(
                    complaint,
                    reason="TAT breached and auto-escalated",
                    escalated_by="system",
                    commit=False,
                )
                if created:
                    escalated += 1
        return updated, escalated

    def generate_monthly_mis_report(self, client_id, month: datetime, commit: bool = True) -> dict[str, Any]:
        month_start = month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if month_start.month == 12:
            next_month = month_start.replace(year=month_start.year + 1, month=1)
        else:
            next_month = month_start.replace(month=month_start.month + 1)
        month_end = next_month - timedelta(seconds=1)

        complaints = (
            self.db.query(Complaint)
            .filter(
                Complaint.client_id == client_id,
                Complaint.created_at >= month_start,
                Complaint.created_at <= month_end,
                Complaint.rbi_category_code.isnot(None),
            )
            .all()
        )

        total = len(complaints)
        resolved_within_tat = 0
        tat_breach_count = 0
        pending_complaints = 0
        category_counts: dict[str, int] = {}
        total_resolution_days = 0.0
        resolution_count = 0

        for complaint in complaints:
            category_key = complaint.rbi_category_code or "OTHER"
            category_counts[category_key] = category_counts.get(category_key, 0) + 1
            if complaint.resolution_status == "resolved" and complaint.resolved_at:
                if complaint.tat_due_at and complaint.resolved_at <= complaint.tat_due_at:
                    resolved_within_tat += 1
                total_resolution_days += max(
                    0.0,
                    (complaint.resolved_at - complaint.created_at).total_seconds() / 86400,
                )
                resolution_count += 1
            else:
                pending_complaints += 1
            if complaint.tat_status == "breached":
                tat_breach_count += 1

        escalations_count = (
            self.db.query(func.count(Escalation.id))
            .join(Complaint, Complaint.id == Escalation.ticket_id)
            .filter(
                Complaint.client_id == client_id,
                Escalation.created_at >= month_start,
                Escalation.created_at <= month_end,
            )
            .scalar()
            or 0
        )

        report_data = {
            "total_complaints": total,
            "resolved_within_tat": resolved_within_tat,
            "tat_breach_count": tat_breach_count,
            "breached_complaints": tat_breach_count,
            "pending_complaints": pending_complaints,
            "complaints_by_category": category_counts,
            "category_distribution": category_counts,
            "escalations_count": escalations_count,
            "escalated_to_regional": 0,
            "escalated_to_nodal": 0,
            "escalated_to_ombudsman": escalations_count,
            "avg_resolution_days": round(total_resolution_days / resolution_count, 2) if resolution_count else None,
            "satisfaction_rate": None,
        }

        report = (
            self.db.query(RBIMISReport)
            .filter(
                RBIMISReport.client_id == client_id,
                RBIMISReport.report_month == month_start.date(),
            )
            .first()
        )
        if report is None:
            report = RBIMISReport(client_id=client_id, report_month=month_start.date())
            self.db.add(report)

        report.total_complaints = total
        report.complaints_by_category = category_counts
        report.resolved_within_tat = resolved_within_tat
        report.tat_breach_count = tat_breach_count
        report.avg_resolution_days = report_data["avg_resolution_days"]
        report.pending_complaints = pending_complaints
        report.escalated_to_regional = 0
        report.escalated_to_nodal = 0
        report.escalated_to_ombudsman = escalations_count
        report.satisfaction_rate = None
        report.report_data = report_data

        if commit:
            self.db.commit()
            self.db.refresh(report)
        else:
            self.db.flush()
        return report_data

    def get_escalation_history(self, complaint: Complaint) -> list[dict[str, Any]]:
        escalations = (
            self.db.query(Escalation)
            .filter(Escalation.ticket_id == complaint.id)
            .order_by(Escalation.created_at.desc(), Escalation.id.desc())
            .all()
        )
        return [
            {
                "id": str(item.id),
                "level": item.level,
                "escalated_to": item.escalated_to,
                "reason": item.reason,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in escalations
        ]

    def get_audit_trail(self, complaint: Complaint) -> list[dict[str, Any]]:
        immutable_entries = [
            serialize_audit_log(item)
            for item in list_entity_audit_logs(
                self.db,
                entity_type="ticket",
                entity_id=complaint.id,
            )
        ]
        legacy_entries = []
        if complaint.rbi_complaint and complaint.rbi_complaint.audit_log:
            for entry in complaint.rbi_complaint.audit_log:
                legacy_entries.append(
                    {
                        "id": None,
                        "entity_type": "ticket",
                        "entity_id": str(complaint.id),
                        "action": entry.get("event"),
                        "performed_by": None,
                        "old_value": {},
                        "new_value": entry.get("details") or {},
                        "timestamp": entry.get("timestamp"),
                    }
                )
        combined = immutable_entries + legacy_entries
        combined.sort(key=lambda item: item.get("timestamp") or "", reverse=True)
        return combined

    def _append_audit_event(self, rbi_complaint: RBIComplaint, event: str, details: dict[str, Any]) -> None:
        audit_log = list(rbi_complaint.audit_log or [])
        audit_log.append({"timestamp": _utcnow().isoformat(), "event": event, "details": details})
        rbi_complaint.audit_log = audit_log

    def _generate_rbi_reference(self, client_id) -> str:
        now = _utcnow()
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        next_day = day_start + timedelta(days=1)
        count = (
            self.db.query(func.count(RBIComplaint.id))
            .filter(
                RBIComplaint.client_id == client_id,
                RBIComplaint.created_at >= day_start,
                RBIComplaint.created_at < next_day,
            )
            .scalar()
            or 0
        )
        return f"RBI/{now.year}/{now.strftime('%m%d')}/{count + 1:05d}"

    @staticmethod
    def parse_queue_id(value) -> uuid.UUID:
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))
