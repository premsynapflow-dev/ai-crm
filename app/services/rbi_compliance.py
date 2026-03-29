from datetime import datetime, timedelta, timezone
import uuid
from typing import Any

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Complaint, RBIComplaint, RBIComplaintCategory, RBIEscalationLog, RBIMISReport
from app.services.rbi_taxonomy_classifier import RBITaxonomyClassifier


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RBIComplianceService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

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

        resolved_category_code = category_code
        resolved_subcategory_code = subcategory_code
        if not resolved_category_code or not resolved_subcategory_code:
            resolved_category_code, resolved_subcategory_code, _ = RBITaxonomyClassifier(self.db).classify(
                complaint.summary or ""
            )

        category = (
            self.db.query(RBIComplaintCategory)
            .filter(
                and_(
                    RBIComplaintCategory.category_code == resolved_category_code,
                    RBIComplaintCategory.subcategory_code == resolved_subcategory_code,
                    RBIComplaintCategory.is_active == True,
                )
            )
            .first()
        )

        tat_days = category.tat_days if category else self.settings.rbi_tat_default_days
        tat_due_date = _utcnow() + timedelta(days=tat_days)
        rbi_reference = self._generate_rbi_reference(complaint.client_id)

        rbi_complaint = RBIComplaint(
            complaint_id=complaint.id,
            client_id=complaint.client_id,
            rbi_category_id=category.id if category else None,
            category_code=resolved_category_code,
            subcategory_code=resolved_subcategory_code,
            rbi_reference_number=rbi_reference,
            tat_due_date=tat_due_date,
            tat_status="within_tat",
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
                    },
                }
            ],
        )
        self.db.add(rbi_complaint)
        self.check_tat_compliance(rbi_complaint)

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

        rbi_complaint.resolution_date = complaint.resolved_at
        if complaint.resolution_status == "resolved" and complaint.ai_reply:
            rbi_complaint.resolution_summary = complaint.ai_reply
        satisfaction_score = complaint.satisfaction_score or complaint.customer_satisfaction_score
        if satisfaction_score is not None:
            rbi_complaint.customer_satisfied = satisfaction_score >= 4
        self.check_tat_compliance(rbi_complaint)
        self._append_audit_event(
            rbi_complaint,
            "complaint_synced",
            {
                "resolution_status": complaint.resolution_status,
                "state": complaint.state,
                "escalation_level": complaint.escalation_level,
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
        if rbi_complaint.resolution_date:
            if rbi_complaint.tat_due_date and rbi_complaint.resolution_date > rbi_complaint.tat_due_date:
                delta = rbi_complaint.resolution_date - rbi_complaint.tat_due_date
                rbi_complaint.tat_status = "breached"
                rbi_complaint.tat_breach_hours = int(delta.total_seconds() // 3600)
                return "breached"
            rbi_complaint.tat_status = "within_tat"
            rbi_complaint.tat_breach_hours = 0
            return "resolved"

        now = _utcnow()
        time_remaining = (rbi_complaint.tat_due_date - now).total_seconds()
        if time_remaining < 0:
            rbi_complaint.tat_status = "breached"
            rbi_complaint.tat_breach_hours = int(abs(time_remaining) // 3600)
            return "breached"
        if time_remaining < 86400 * 5:
            rbi_complaint.tat_status = "approaching_breach"
            rbi_complaint.tat_breach_hours = 0
            return "approaching_breach"

        rbi_complaint.tat_status = "within_tat"
        rbi_complaint.tat_breach_hours = 0
        return "within_tat"

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
        return self.escalate_level(
            rbi_complaint,
            to_level=3,
            escalated_by=escalated_by,
            reason="Escalated to RBI Ombudsman",
            metadata={"target": "rbi_ombudsman"},
            commit=commit,
        )

    def generate_monthly_mis_report(self, client_id, month: datetime, commit: bool = True) -> dict[str, Any]:
        month_start = month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if month_start.month == 12:
            next_month = month_start.replace(year=month_start.year + 1, month=1)
        else:
            next_month = month_start.replace(month=month_start.month + 1)
        month_end = next_month - timedelta(seconds=1)

        complaints = (
            self.db.query(RBIComplaint)
            .filter(
                RBIComplaint.client_id == client_id,
                RBIComplaint.created_at >= month_start,
                RBIComplaint.created_at <= month_end,
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
        satisfaction_scores = 0
        satisfaction_count = 0

        for complaint in complaints:
            status = self.check_tat_compliance(complaint)
            category_key = complaint.category_code or "OTHER"
            category_counts[category_key] = category_counts.get(category_key, 0) + 1
            if complaint.resolution_date:
                if status != "breached":
                    resolved_within_tat += 1
                total_resolution_days += max(
                    0.0,
                    (complaint.resolution_date - complaint.created_at).total_seconds() / 86400,
                )
                resolution_count += 1
            else:
                pending_complaints += 1
            if status == "breached":
                tat_breach_count += 1
            if complaint.customer_satisfied is not None:
                satisfaction_scores += 1 if complaint.customer_satisfied else 0
                satisfaction_count += 1

        report_data = {
            "total_complaints": total,
            "resolved_within_tat": resolved_within_tat,
            "tat_breach_count": tat_breach_count,
            "pending_complaints": pending_complaints,
            "complaints_by_category": category_counts,
            "escalated_to_regional": sum(1 for item in complaints if item.escalation_level >= 1),
            "escalated_to_nodal": sum(1 for item in complaints if item.escalation_level >= 2),
            "escalated_to_ombudsman": sum(1 for item in complaints if item.escalation_level >= 3),
            "avg_resolution_days": round(total_resolution_days / resolution_count, 2) if resolution_count else None,
            "satisfaction_rate": round((satisfaction_scores / satisfaction_count) * 100, 2) if satisfaction_count else None,
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
        report.escalated_to_regional = report_data["escalated_to_regional"]
        report.escalated_to_nodal = report_data["escalated_to_nodal"]
        report.escalated_to_ombudsman = report_data["escalated_to_ombudsman"]
        report.satisfaction_rate = report_data["satisfaction_rate"]
        report.report_data = report_data

        if commit:
            self.db.commit()
            self.db.refresh(report)
        else:
            self.db.flush()
        return report_data

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
