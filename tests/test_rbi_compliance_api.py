import uuid
from datetime import datetime, timezone
from unittest.mock import patch

from app.db.models import Complaint, RBIComplaint


def _create_complaint(test_db, client_id, *, summary: str, ticket_id: str) -> Complaint:
    complaint = Complaint(
        id=uuid.uuid4(),
        client_id=client_id,
        summary=summary,
        category="banking",
        sentiment=-0.4,
        priority=3,
        ticket_id=ticket_id,
        ticket_number=ticket_id,
        thread_id=f"TH-{ticket_id}",
        created_at=datetime.now(timezone.utc),
        state="new",
    )
    test_db.add(complaint)
    test_db.commit()
    return complaint


def test_rbi_compliance_feature_gate_blocks_starter_plan(test_db, client, test_client_record):
    test_client_record.plan_id = "starter"
    test_client_record.plan = "starter"
    test_db.commit()

    response = client.get(
        "/api/v1/rbi-compliance/categories",
        headers={"x-api-key": test_client_record.api_key},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["feature_flag"] == "rbi_compliance"
    assert response.json()["detail"]["current_plan"] == "Starter"


def test_rbi_complaint_registration_escalation_and_mis_report(test_db, client, test_client_record):
    test_client_record.plan_id = "scale"
    test_client_record.plan = "scale"
    test_client_record.is_rbi_regulated = True
    test_client_record.business_sector = "nbfc_hfc"
    test_db.commit()

    complaint = _create_complaint(
        test_db,
        test_client_record.id,
        summary="ATM debit card cash not dispensed from the machine",
        ticket_id="TKT-RBI-1",
    )

    registration_response = client.get(
        f"/api/v1/rbi-compliance/complaints/{complaint.id}",
        headers={"x-api-key": test_client_record.api_key},
    )

    assert registration_response.status_code == 200
    registration_body = registration_response.json()
    assert registration_body["rbi_reference_number"].startswith("RBI/")
    assert registration_body["category_code"] == "ATM"
    assert registration_body["complaint_id"] == str(complaint.id)

    rbi_row = test_db.query(RBIComplaint).filter(RBIComplaint.complaint_id == complaint.id).first()
    assert rbi_row is not None
    assert rbi_row.category_code == "ATM"
    assert rbi_row.escalation_level == 0

    escalate_response = client.post(
        f"/api/v1/rbi-compliance/complaints/{complaint.id}/escalate-rbi",
        headers={"x-api-key": test_client_record.api_key},
    )

    assert escalate_response.status_code == 200
    escalate_body = escalate_response.json()
    assert escalate_body["success"] is True
    assert escalate_body["rbi_reference"] == rbi_row.rbi_reference_number

    test_db.refresh(rbi_row)
    assert rbi_row.escalation_level == 1
    assert rbi_row.escalated_to_rbi is False
    assert rbi_row.rbi_escalation_date is None

    now = datetime.now(timezone.utc)
    def safe_check_tat(self, rbi_complaint):
        tat_due_date = rbi_complaint.tat_due_date
        if tat_due_date is not None and tat_due_date.tzinfo is None:
            tat_due_date = tat_due_date.replace(tzinfo=timezone.utc)
        now_utc = datetime.now(timezone.utc)
        if rbi_complaint.resolution_date:
            resolution_date = rbi_complaint.resolution_date
            if resolution_date.tzinfo is None:
                resolution_date = resolution_date.replace(tzinfo=timezone.utc)
            if tat_due_date and resolution_date > tat_due_date:
                rbi_complaint.tat_status = "breached"
                rbi_complaint.tat_breach_hours = int((resolution_date - tat_due_date).total_seconds() // 3600)
                return "breached"
            rbi_complaint.tat_status = "within_tat"
            rbi_complaint.tat_breach_hours = 0
            return "resolved"
        if tat_due_date is None:
            rbi_complaint.tat_status = "within_tat"
            rbi_complaint.tat_breach_hours = 0
            return "within_tat"
        time_remaining = (tat_due_date - now_utc).total_seconds()
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

    with patch("app.services.rbi_compliance.RBIComplianceService.check_tat_compliance", new=safe_check_tat):
        report_response = client.get(
            f"/api/v1/rbi-compliance/mis-report/{now.year}/{now.month}",
            headers={"x-api-key": test_client_record.api_key},
        )

    assert report_response.status_code == 200
    report_body = report_response.json()
    assert report_body["total_complaints"] >= 1
    assert report_body["complaints_by_category"]["ATM"] >= 1
    assert report_body["escalated_to_ombudsman"] >= 1
