import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.models import Customer, CustomerNote, CustomerRelationship
from app.db.session import get_db
from app.dependencies.auth import require_api_key
from app.middleware.feature_gate import ensure_feature_access
from app.services.customer_deduplication import CustomerDeduplicator
from app.services.customer_profile import (
    CustomerProfileService,
    serialize_customer,
    serialize_customer_interaction,
    serialize_customer_message,
    serialize_customer_note,
    serialize_customer_relationship,
    serialize_customer_ticket,
)

router = APIRouter(prefix="/api/v1/customers", tags=["customers-v1"])


def _parse_customer_id(customer_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(customer_id))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid customer id") from exc


def _actor_email(client) -> str:
    return f"client-{str(client.id)[:8]}@system.local"


def _get_customer_or_404(db: Session, customer_id: uuid.UUID, client_id) -> Customer:
    customer = db.query(Customer).filter(Customer.id == customer_id, Customer.client_id == client_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


class MergeCustomersRequest(BaseModel):
    master_customer_id: str
    duplicate_customer_id: str
    merged_by: Optional[str] = None


class CustomerNoteRequest(BaseModel):
    content: str = Field(..., min_length=1)
    note_type: str = "general"
    pinned: bool = False
    author_email: Optional[str] = None


class CustomerRelationshipRequest(BaseModel):
    child_customer_id: str
    relationship_type: str = Field(..., min_length=1)
    role_title: Optional[str] = None
    is_primary_contact: bool = False


class UpdateCustomerRequest(BaseModel):
    name: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[list[str]] = None


@router.get("")
def list_customers(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    search: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    current_client=Depends(require_api_key),
):
    query = db.query(Customer).filter(Customer.client_id == current_client.id, Customer.is_master == True)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Customer.name.ilike(pattern),
                Customer.full_name.ilike(pattern),
                Customer.primary_email.ilike(pattern),
                Customer.company_name.ilike(pattern),
                Customer.primary_phone.ilike(pattern),
            )
        )

    total = query.count()
    customers = query.order_by(Customer.last_contacted_at.desc(), Customer.updated_at.desc()).offset(skip).limit(limit).all()
    return {"total": total, "items": [serialize_customer(customer) for customer in customers]}


@router.post("/merge")
def merge_customers(
    request: MergeCustomersRequest,
    db: Session = Depends(get_db),
    current_client=Depends(require_api_key),
):
    master = _get_customer_or_404(db, _parse_customer_id(request.master_customer_id), current_client.id)
    duplicate = _get_customer_or_404(db, _parse_customer_id(request.duplicate_customer_id), current_client.id)
    try:
        merged = CustomerDeduplicator(db).merge_customers(
            master_id=str(master.id),
            duplicate_id=str(duplicate.id),
            merged_by=(request.merged_by or current_client.name or _actor_email(current_client)),
            merge_strategy="manual",
            confidence_score=1.0,
            commit=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "master_customer": serialize_customer(merged)}


@router.get("/{customer_id}")
def get_customer_360(
    customer_id: str,
    db: Session = Depends(get_db),
    current_client=Depends(require_api_key),
):
    parsed_customer_id = _parse_customer_id(customer_id)
    customer = _get_customer_or_404(db, parsed_customer_id, current_client.id)

    service = CustomerProfileService(db)
    data = service.get_customer_360(str(customer.id))

    profile = data["profile"]
    if str(profile.client_id) != str(current_client.id):
        raise HTTPException(status_code=403, detail="Access denied")

    return {
        "profile": serialize_customer(profile),
        "recent_tickets": [serialize_customer_ticket(ticket) for ticket in data["recent_tickets"]],
        "recent_messages": [serialize_customer_message(message) for message in data.get("recent_messages", [])],
        "active_tickets": [serialize_customer_ticket(ticket) for ticket in data.get("active_tickets", [])],
        "interaction_timeline": [serialize_customer_interaction(item) for item in data["interaction_timeline"]],
        "timeline": data.get("timeline", []),
        "notes": [serialize_customer_note(item) for item in data["notes"]],
        "relationships": [serialize_customer_relationship(item) for item in data["relationships"]],
        "satisfaction_trend": data["satisfaction_trend"],
        "churn_indicators": data["churn_indicators"],
        "sentiment": data.get("sentiment"),
        "insights": data.get("insights", []),
        "stats": data["stats"],
    }


@router.get("/{customer_id}/360")
def get_customer_360_snapshot(
    customer_id: str,
    db: Session = Depends(get_db),
    current_client=Depends(require_api_key),
):
    customer = _get_customer_or_404(db, _parse_customer_id(customer_id), current_client.id)
    snapshot = CustomerProfileService(db).get_customer_360_snapshot(str(customer.id))
    if snapshot["identity"]["client_id"] != str(current_client.id):
        raise HTTPException(status_code=403, detail="Access denied")
    return snapshot


@router.patch("/{customer_id}")
def update_customer(
    customer_id: str,
    request: UpdateCustomerRequest,
    db: Session = Depends(get_db),
    current_client=Depends(require_api_key),
):
    customer = _get_customer_or_404(db, _parse_customer_id(customer_id), current_client.id)
    update_data = request.model_dump(exclude_unset=True)
    if "name" in update_data:
        normalized_name = (request.name or "").strip() or None
        customer.name = normalized_name
        customer.full_name = normalized_name
    if "notes" in update_data:
        customer.notes = (request.notes or "").strip() or None
    if "tags" in update_data and request.tags is not None:
        customer.tags = [tag for tag in dict.fromkeys((tag or "").strip() for tag in request.tags) if tag]
    CustomerProfileService(db).refresh_customer_metrics(customer, commit=False)
    db.commit()
    db.refresh(customer)
    return {"success": True, "customer": serialize_customer(customer)}


@router.get("/{customer_id}/duplicates")
def find_duplicates(
    customer_id: str,
    db: Session = Depends(get_db),
    current_client=Depends(require_api_key),
):
    customer = _get_customer_or_404(db, _parse_customer_id(customer_id), current_client.id)
    duplicates = CustomerDeduplicator(db).find_duplicates(customer, limit=10)
    return {
        "customer_id": str(customer.id),
        "potential_duplicates": [
            {
                "customer": serialize_customer(duplicate),
                "confidence_score": confidence,
            }
            for duplicate, confidence in duplicates
        ],
    }


@router.get("/{customer_id}/notes")
def list_customer_notes(
    customer_id: str,
    db: Session = Depends(get_db),
    current_client=Depends(require_api_key),
):
    customer = _get_customer_or_404(db, _parse_customer_id(customer_id), current_client.id)
    notes = (
        db.query(CustomerNote)
        .filter(CustomerNote.customer_id == customer.id)
        .order_by(CustomerNote.pinned.desc(), CustomerNote.created_at.desc())
        .all()
    )
    return {"items": [serialize_customer_note(note) for note in notes]}


@router.post("/{customer_id}/notes")
def create_customer_note(
    customer_id: str,
    request: CustomerNoteRequest,
    db: Session = Depends(get_db),
    current_client=Depends(require_api_key),
):
    customer = _get_customer_or_404(db, _parse_customer_id(customer_id), current_client.id)
    note = CustomerNote(
        customer_id=customer.id,
        author_email=(request.author_email or _actor_email(current_client)).strip(),
        note_type=request.note_type.strip() or "general",
        content=request.content.strip(),
        pinned=request.pinned,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return {"success": True, "note": serialize_customer_note(note)}


@router.get("/{customer_id}/relationships")
def list_customer_relationships(
    customer_id: str,
    db: Session = Depends(get_db),
    current_client=Depends(require_api_key),
):
    customer = _get_customer_or_404(db, _parse_customer_id(customer_id), current_client.id)
    relationships = (
        db.query(CustomerRelationship)
        .filter(
            or_(
                CustomerRelationship.parent_customer_id == customer.id,
                CustomerRelationship.child_customer_id == customer.id,
            )
        )
        .order_by(CustomerRelationship.created_at.desc())
        .all()
    )
    return {"items": [serialize_customer_relationship(item) for item in relationships]}


@router.post("/{customer_id}/relationships")
def create_customer_relationship(
    customer_id: str,
    request: CustomerRelationshipRequest,
    db: Session = Depends(get_db),
    current_client=Depends(require_api_key),
):
    parent_customer = _get_customer_or_404(db, _parse_customer_id(customer_id), current_client.id)
    child_customer = _get_customer_or_404(db, _parse_customer_id(request.child_customer_id), current_client.id)
    if parent_customer.id == child_customer.id:
        raise HTTPException(status_code=400, detail="Cannot relate a customer to itself")

    existing = (
        db.query(CustomerRelationship)
        .filter(
            CustomerRelationship.parent_customer_id == parent_customer.id,
            CustomerRelationship.child_customer_id == child_customer.id,
        )
        .first()
    )
    if existing:
        existing.relationship_type = request.relationship_type.strip()
        existing.role_title = request.role_title
        existing.is_primary_contact = request.is_primary_contact
        db.commit()
        db.refresh(existing)
        return {"success": True, "relationship": serialize_customer_relationship(existing)}

    relationship = CustomerRelationship(
        client_id=current_client.id,
        parent_customer_id=parent_customer.id,
        child_customer_id=child_customer.id,
        relationship_type=request.relationship_type.strip(),
        role_title=request.role_title,
        is_primary_contact=request.is_primary_contact,
    )
    db.add(relationship)
    db.commit()
    db.refresh(relationship)
    return {"success": True, "relationship": serialize_customer_relationship(relationship)}
