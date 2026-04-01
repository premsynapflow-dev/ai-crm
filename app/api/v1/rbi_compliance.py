import uuid
from datetime import datetime
from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models import Complaint, RBIComplaint, RBIComplaintCategory, RBITATRule
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
    service = RBIComplianceService(db)
    rbi_complaint = db.query(RBIComplaint).filter(RBIComplaint.complaint_id == complaint.id).first()
    if not rbi_complaint:
        classifier = RBITaxonomyClassifier(db)
        category_code, subcategory_code, confidence = classifier.classify(complaint.summary or "")
        rbi_complaint = service.register_rbi_complaint(
            complaint,
            category_code=category_code,
            subcategory_code=subcategory_code,
            commit=True,
        )
        category = (
            db.query(RBIComplaintCategory)
            .filter(
                RBIComplaintCategory.category_code == rbi_complaint.category_code,
                RBIComplaintCategory.subcategory_code == rbi_complaint.subcategory_code,
            )
            .first()
        )
        return {
            "complaint_id": str(complaint.id),
            "ticket_id": complaint.ticket_id,
            "rbi_reference_number": rbi_complaint.rbi_reference_number,
            "category_code": rbi_complaint.category_code,
            "category_name": category.category_name if category else rbi_complaint.category_code,
            "subcategory_code": rbi_complaint.subcategory_code,
            "subcategory_name": category.subcategory_name if category else rbi_complaint.subcategory_code,
            "tat_due_date": complaint.tat_due_at.isoformat() if complaint.tat_due_at else (rbi_complaint.tat_due_date.isoformat() if rbi_complaint.tat_due_date else None),
            "tat_due_at": complaint.tat_due_at.isoformat() if complaint.tat_due_at else None,
            "tat_status": complaint.tat_status or rbi_complaint.tat_status,
            "tat_breached_at": complaint.tat_breached_at.isoformat() if complaint.tat_breached_at else None,
            "breached": (complaint.tat_status or rbi_complaint.tat_status) == "breached",
            "classifier_confidence": confidence,
            "escalation_level": complaint.escalation_level,
            "escalation_status": complaint.escalated_to or "Not escalated",
            "escalation_history": service.get_escalation_history(complaint),
            "audit_log": service.get_audit_trail(complaint),
        }

    service.sync_from_complaint(complaint, commit=True)
    category = (
        db.query(RBIComplaintCategory)
        .filter(
            RBIComplaintCategory.category_code == rbi_complaint.category_code,
            RBIComplaintCategory.subcategory_code == rbi_complaint.subcategory_code,
        )
        .first()
    )
    return {
        "complaint_id": str(complaint.id),
        "ticket_id": complaint.ticket_id,
        "rbi_reference_number": rbi_complaint.rbi_reference_number,
        "category_code": rbi_complaint.category_code,
        "category_name": category.category_name if category else rbi_complaint.category_code,
        "subcategory_code": rbi_complaint.subcategory_code,
        "subcategory_name": category.subcategory_name if category else rbi_complaint.subcategory_code,
        "tat_due_date": complaint.tat_due_at.isoformat() if complaint.tat_due_at else (rbi_complaint.tat_due_date.isoformat() if rbi_complaint.tat_due_date else None),
        "tat_due_at": complaint.tat_due_at.isoformat() if complaint.tat_due_at else None,
        "tat_status": complaint.tat_status or rbi_complaint.tat_status,
        "tat_breached_at": complaint.tat_breached_at.isoformat() if complaint.tat_breached_at else None,
        "breached": (complaint.tat_status or rbi_complaint.tat_status) == "breached",
        "escalation_level": complaint.escalation_level,
        "escalated_to_rbi": rbi_complaint.escalated_to_rbi,
        "escalation_status": complaint.escalated_to or "Not escalated",
        "escalation_history": service.get_escalation_history(complaint),
        "resolution_date": rbi_complaint.resolution_date.isoformat() if rbi_complaint.resolution_date else None,
        "audit_log": service.get_audit_trail(complaint),
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
    return {"success": True, "rbi_reference": escalated.rbi_reference_number, "escalated_to": "Internal Ombudsman"}


@router.post("/complaints/{complaint_id}/escalate-internal")
def escalate_internally(
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

    RBIComplianceService(db).escalate_to_internal_ombudsman(
        complaint,
        reason="Manual internal compliance escalation",
        escalated_by=f"client-{str(current_client.id)[:8]}@system.local",
        commit=True,
    )
    return {"success": True, "escalated_to": "Internal Ombudsman"}


# ===== TAT Rules Management =====

class TATRuleCreate(BaseModel):
    category_code: str
    tat_days: int


class TATRuleUpdate(BaseModel):
    tat_days: int


class TATRuleResponse(BaseModel):
    id: str
    category_code: str
    tat_days: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


@router.get("/tat-rules")
def list_tat_rules(
    db: Session = Depends(get_db),
    current_client=Depends(require_api_key),
):
    """
    List all TAT rules for current client.
    Returns configurable TAT values per category.
    """
    ensure_feature_access(current_client, "rbi_compliance", db=db)
    _ensure_rbi_workspace(current_client)
    
    rules = (
        db.query(RBITATRule)
        .filter(
            RBITATRule.client_id == current_client.id,
            RBITATRule.is_active == True,
        )
        .order_by(RBITATRule.category_code.asc())
        .all()
    )
    
    return {
        "items": [
            TATRuleResponse(
                id=str(rule.id),
                category_code=rule.category_code,
                tat_days=rule.tat_days,
                is_active=rule.is_active,
                created_at=rule.created_at,
                updated_at=rule.updated_at,
            )
            for rule in rules
        ]
    }


@router.post("/tat-rules")
def create_tat_rule(
    rule_data: TATRuleCreate,
    db: Session = Depends(get_db),
    current_client=Depends(require_api_key),
):
    """
    Create or update TAT rule for a category.
    Replaces hardcoded defaults with client-specific values.
    
    Example:
    {
        "category_code": "ATM",
        "tat_days": 7
    }
    """
    ensure_feature_access(current_client, "rbi_compliance", db=db)
    _ensure_rbi_workspace(current_client)
    
    # Validate TAT days
    if rule_data.tat_days <= 0 or rule_data.tat_days > 365:
        raise HTTPException(
            status_code=400,
            detail="tat_days must be between 1 and 365"
        )
    
    # Check if category exists
    category = (
        db.query(RBIComplaintCategory)
        .filter(
            RBIComplaintCategory.category_code == rule_data.category_code,
            RBIComplaintCategory.is_active == True,
        )
        .first()
    )
    if not category:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category_code: {rule_data.category_code}"
        )
    
    # Create or update rule
    existing_rule = (
        db.query(RBITATRule)
        .filter(
            RBITATRule.client_id == current_client.id,
            RBITATRule.category_code == rule_data.category_code,
        )
        .first()
    )
    
    if existing_rule:
        existing_rule.tat_days = rule_data.tat_days
        existing_rule.is_active = True
        rule = existing_rule
    else:
        rule = RBITATRule(
            client_id=current_client.id,
            category_code=rule_data.category_code,
            tat_days=rule_data.tat_days,
            is_active=True,
        )
        db.add(rule)
    
    db.commit()
    db.refresh(rule)
    
    return TATRuleResponse(
        id=str(rule.id),
        category_code=rule.category_code,
        tat_days=rule.tat_days,
        is_active=rule.is_active,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )


@router.put("/tat-rules/{category_code}")
def update_tat_rule(
    category_code: str,
    rule_data: TATRuleUpdate,
    db: Session = Depends(get_db),
    current_client=Depends(require_api_key),
):
    """
    Update TAT rule for a specific category.
    """
    ensure_feature_access(current_client, "rbi_compliance", db=db)
    _ensure_rbi_workspace(current_client)
    
    # Validate TAT days
    if rule_data.tat_days <= 0 or rule_data.tat_days > 365:
        raise HTTPException(
            status_code=400,
            detail="tat_days must be between 1 and 365"
        )
    
    rule = (
        db.query(RBITATRule)
        .filter(
            RBITATRule.client_id == current_client.id,
            RBITATRule.category_code == category_code,
        )
        .first()
    )
    
    if not rule:
        raise HTTPException(
            status_code=404,
            detail=f"No TAT rule found for category: {category_code}"
        )
    
    rule.tat_days = rule_data.tat_days
    db.commit()
    db.refresh(rule)
    
    return TATRuleResponse(
        id=str(rule.id),
        category_code=rule.category_code,
        tat_days=rule.tat_days,
        is_active=rule.is_active,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )


@router.delete("/tat-rules/{category_code}")
def delete_tat_rule(
    category_code: str,
    db: Session = Depends(get_db),
    current_client=Depends(require_api_key),
):
    """
    Delete TAT rule for a category.
    After deletion, will use category defaults or system defaults.
    """
    ensure_feature_access(current_client, "rbi_compliance", db=db)
    _ensure_rbi_workspace(current_client)
    
    rule = (
        db.query(RBITATRule)
        .filter(
            RBITATRule.client_id == current_client.id,
            RBITATRule.category_code == category_code,
        )
        .first()
    )
    
    if not rule:
        raise HTTPException(
            status_code=404,
            detail=f"No TAT rule found for category: {category_code}"
        )
    
    db.delete(rule)
    db.commit()
    
    return {"success": True, "message": f"TAT rule for {category_code} deleted"}

