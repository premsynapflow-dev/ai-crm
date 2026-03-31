import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models import Complaint, RBIComplaint, RBIComplaintCategory
from app.db.session import get_db
from app.dependencies.auth import require_api_key
from app.middleware.feature_gate import ensure_feature_access
from app.services.rbi_compliance import RBIComplianceService
from app.services.rbi_taxonomy_classifier import RBITaxonomyClassifier

router = APIRouter(prefix="/api/v1/rbi-compliance", tags=["rbi-compliance-v1"])


def _parse_complaint_id(complaint_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(complaint_id))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid complaint id") from exc


def _ensure_rbi_workspace(current_client) -> None:
    if not getattr(current_client, "is_rbi_regulated", False):
        raise HTTPException(
            status_code=403,
            detail="RBI compliance is only available for RBI-regulated financial institutions",
        )


@router.get("/categories")
def list_rbi_categories(
    db: Session = Depends(get_db),
    current_client=Depends(require_api_key),
):
    ensure_feature_access(current_client, "rbi_compliance", db=db)
    _ensure_rbi_workspace(current_client)
    categories = (
        db.query(RBIComplaintCategory)
        .filter(RBIComplaintCategory.is_active == True)
        .order_by(RBIComplaintCategory.category_code.asc(), RBIComplaintCategory.subcategory_code.asc())
        .all()
    )
    return {
        "items": [
            {
                "id": str(category.id),
                "category_code": category.category_code,
                "category_name": category.category_name,
                "subcategory_code": category.subcategory_code,
                "subcategory_name": category.subcategory_name,
                "tat_days": category.tat_days,
            }
            for category in categories
        ]
    }


@router.get("/complaints/{complaint_id}")
def get_rbi_complaint(
    complaint_id: str,
    db: Session = Depends(get_db),
    current_client=Depends(require_api_key),
):
    ensure_feature_access(current_client, "rbi_compliance", db=db)
    _ensure_rbi_workspace(current_client)
    parsed_id = _parse_complaint_id(complaint_id)
    complaint = db.query(Complaint).filter(Complaint.id == parsed_id, Complaint.client_id == current_client.id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    rbi_complaint = db.query(RBIComplaint).filter(RBIComplaint.complaint_id == complaint.id).first()
    if not rbi_complaint:
        classifier = RBITaxonomyClassifier(db)
        category_code, subcategory_code, confidence = classifier.classify(complaint.summary or "")
        rbi_complaint = RBIComplianceService(db).register_rbi_complaint(
            complaint,
            category_code=category_code,
            subcategory_code=subcategory_code,
            commit=True,
        )
        return {
            "complaint_id": str(complaint.id),
            "rbi_reference_number": rbi_complaint.rbi_reference_number,
            "category_code": rbi_complaint.category_code,
            "subcategory_code": rbi_complaint.subcategory_code,
            "tat_due_date": rbi_complaint.tat_due_date.isoformat() if rbi_complaint.tat_due_date else None,
            "tat_status": rbi_complaint.tat_status,
            "classifier_confidence": confidence,
            "audit_log": rbi_complaint.audit_log or [],
        }

    RBIComplianceService(db).sync_from_complaint(complaint, commit=True)
    return {
        "complaint_id": str(complaint.id),
        "rbi_reference_number": rbi_complaint.rbi_reference_number,
        "category_code": rbi_complaint.category_code,
        "subcategory_code": rbi_complaint.subcategory_code,
        "tat_due_date": rbi_complaint.tat_due_date.isoformat() if rbi_complaint.tat_due_date else None,
        "tat_status": rbi_complaint.tat_status,
        "escalation_level": rbi_complaint.escalation_level,
        "escalated_to_rbi": rbi_complaint.escalated_to_rbi,
        "resolution_date": rbi_complaint.resolution_date.isoformat() if rbi_complaint.resolution_date else None,
        "audit_log": rbi_complaint.audit_log or [],
    }


@router.get("/mis-report/{year}/{month}")
def get_mis_report(
    year: int,
    month: int,
    db: Session = Depends(get_db),
    current_client=Depends(require_api_key),
):
    ensure_feature_access(current_client, "rbi_compliance", db=db)
    _ensure_rbi_workspace(current_client)
    if month < 1 or month > 12:
        raise HTTPException(status_code=400, detail="Invalid month")
    report_date = datetime(year, month, 1)
    report = RBIComplianceService(db).generate_monthly_mis_report(current_client.id, report_date, commit=True)
    return report


@router.post("/complaints/{complaint_id}/escalate-rbi")
def escalate_to_rbi(
    complaint_id: str,
    db: Session = Depends(get_db),
    current_client=Depends(require_api_key),
):
    ensure_feature_access(current_client, "rbi_compliance", db=db)
    _ensure_rbi_workspace(current_client)
    parsed_id = _parse_complaint_id(complaint_id)
    complaint = db.query(Complaint).filter(Complaint.id == parsed_id, Complaint.client_id == current_client.id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    rbi_complaint = db.query(RBIComplaint).filter(RBIComplaint.complaint_id == complaint.id).first()
    if not rbi_complaint:
        raise HTTPException(status_code=404, detail="RBI complaint not found")

    service = RBIComplianceService(db)
    escalated = service.escalate_to_rbi(
        rbi_complaint,
        escalated_by=f"client-{str(current_client.id)[:8]}@system.local",
        commit=True,
    )
    return {"success": True, "rbi_reference": escalated.rbi_reference_number}
