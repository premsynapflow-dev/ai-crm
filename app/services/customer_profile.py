from datetime import datetime, timedelta, timezone
import uuid
from typing import Any, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.db.models import Complaint, Customer, CustomerInteraction, CustomerNote, CustomerRelationship
from app.services.customer_deduplication import CustomerDeduplicator


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CustomerProfileService:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create_customer(
        self,
        client_id,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        name: Optional[str] = None,
        company: Optional[str] = None,
        commit: bool = False,
    ) -> Optional[Customer]:
        normalized_email = CustomerDeduplicator._normalize_email(email)
        normalized_phone = CustomerDeduplicator._normalize_phone(phone)

        if not normalized_email and not normalized_phone:
            return None

        existing = self._find_existing_customer(client_id, normalized_email, normalized_phone)
        if existing:
            changed = self._apply_identity_updates(existing, normalized_email, normalized_phone, name, company)
            if changed:
                self.refresh_customer_metrics(existing, commit=False)
                if commit:
                    self.db.commit()
                    self.db.refresh(existing)
                else:
                    self.db.flush()
            return existing

        customer = Customer(
            client_id=client_id,
            primary_email=normalized_email or None,
            primary_phone=normalized_phone or None,
            full_name=(name or "").strip() or None,
            company_name=(company or "").strip() or None,
            emails=[normalized_email] if normalized_email else [],
            phones=[normalized_phone] if normalized_phone else [],
            first_interaction_at=_utcnow(),
            last_interaction_at=_utcnow(),
        )
        self.db.add(customer)
        self.db.flush()

        merged = CustomerDeduplicator(self.db).auto_deduplicate(customer, commit=False)
        resolved = merged or customer
        self._link_matching_complaints(resolved)
        self.refresh_customer_metrics(resolved, commit=False)

        if commit:
            self.db.commit()
            self.db.refresh(resolved)
        else:
            self.db.flush()
        return resolved

    def sync_customer_for_complaint(
        self,
        complaint: Complaint,
        interaction_type: str = "ticket",
        interaction_channel: Optional[str] = None,
        commit: bool = False,
    ) -> Optional[Customer]:
        customer = None
        if complaint.customer_id:
            customer = self.db.query(Customer).filter(Customer.id == complaint.customer_id).first()

        if customer is None:
            customer = self.get_or_create_customer(
                client_id=complaint.client_id,
                email=complaint.customer_email,
                phone=complaint.customer_phone,
                commit=False,
            )

        if customer is None:
            return None

        if complaint.customer_id != customer.id:
            complaint.customer_id = customer.id

        existing_interaction = None
        if complaint.id:
            existing_interaction = (
                self.db.query(CustomerInteraction)
                .filter(
                    CustomerInteraction.customer_id == customer.id,
                    CustomerInteraction.complaint_id == complaint.id,
                    CustomerInteraction.interaction_type == interaction_type,
                )
                .first()
            )

        if existing_interaction is None:
            self.db.add(
                CustomerInteraction(
                    customer_id=customer.id,
                    client_id=complaint.client_id,
                    interaction_type=interaction_type,
                    interaction_channel=interaction_channel or complaint.source,
                    complaint_id=complaint.id,
                    summary=complaint.summary,
                    sentiment_score=complaint.sentiment,
                    metadata_json={
                        "ticket_id": complaint.ticket_id,
                        "state": complaint.state,
                        "source": complaint.source,
                    },
                )
            )
        else:
            existing_interaction.summary = complaint.summary
            existing_interaction.interaction_channel = interaction_channel or complaint.source
            existing_interaction.sentiment_score = complaint.sentiment
            existing_interaction.metadata_json = {
                "ticket_id": complaint.ticket_id,
                "state": complaint.state,
                "source": complaint.source,
            }

        self.db.flush()
        self._apply_identity_updates(
            customer,
            CustomerDeduplicator._normalize_email(complaint.customer_email),
            CustomerDeduplicator._normalize_phone(complaint.customer_phone),
            None,
            None,
        )
        self.refresh_customer_metrics(customer, commit=False)

        if commit:
            self.db.commit()
            self.db.refresh(customer)
        else:
            self.db.flush()
        return customer

    def refresh_customer_metrics(self, customer: Customer, commit: bool = False) -> Customer:
        complaint_rows = (
            self.db.query(Complaint)
            .filter(Complaint.customer_id == customer.id)
            .order_by(Complaint.created_at.asc())
            .all()
        )
        interaction_rows = (
            self.db.query(CustomerInteraction)
            .filter(CustomerInteraction.customer_id == customer.id)
            .order_by(CustomerInteraction.created_at.asc())
            .all()
        )

        customer.total_tickets = len(complaint_rows)
        customer.total_interactions = len(interaction_rows)

        timestamps = [row.created_at for row in complaint_rows if row.created_at] + [
            row.created_at for row in interaction_rows if row.created_at
        ]
        if timestamps:
            customer.first_interaction_at = min(timestamps)
            customer.last_interaction_at = max(timestamps)

        satisfaction_scores = [
            float(score)
            for score in (
                complaint.satisfaction_score or complaint.customer_satisfaction_score
                for complaint in complaint_rows
            )
            if score is not None
        ]
        customer.avg_satisfaction_score = (
            round(sum(satisfaction_scores) / len(satisfaction_scores), 2) if satisfaction_scores else None
        )
        customer.churn_risk_score = self._calculate_churn_risk_score(customer)

        if commit:
            self.db.commit()
            self.db.refresh(customer)
        else:
            self.db.flush()
        return customer

    def get_customer_360(self, customer_id: str) -> dict[str, Any]:
        customer = self.db.query(Customer).filter(Customer.id == self._as_uuid(customer_id)).first()
        if not customer:
            raise ValueError("Customer not found")
        if not customer.is_master and customer.merged_into:
            resolved = self.db.query(Customer).filter(Customer.id == customer.merged_into).first()
            if resolved:
                customer = resolved

        self.refresh_customer_metrics(customer, commit=False)

        recent_tickets = (
            self.db.query(Complaint)
            .filter(Complaint.customer_id == customer.id)
            .order_by(Complaint.created_at.desc())
            .limit(30)
            .all()
        )
        interactions = (
            self.db.query(CustomerInteraction)
            .filter(CustomerInteraction.customer_id == customer.id)
            .order_by(CustomerInteraction.created_at.desc())
            .limit(50)
            .all()
        )
        notes = (
            self.db.query(CustomerNote)
            .filter(CustomerNote.customer_id == customer.id)
            .order_by(CustomerNote.pinned.desc(), CustomerNote.created_at.desc())
            .limit(50)
            .all()
        )
        relationships = (
            self.db.query(CustomerRelationship)
            .filter(
                or_(
                    CustomerRelationship.parent_customer_id == customer.id,
                    CustomerRelationship.child_customer_id == customer.id,
                )
            )
            .order_by(CustomerRelationship.created_at.desc())
            .all()
        )

        return {
            "profile": customer,
            "recent_tickets": recent_tickets,
            "interaction_timeline": interactions,
            "notes": notes,
            "relationships": relationships,
            "satisfaction_trend": self._build_satisfaction_trend(customer.id),
            "churn_indicators": self._calculate_churn_indicators(customer),
            "stats": {
                "total_tickets": customer.total_tickets,
                "total_interactions": customer.total_interactions,
                "avg_satisfaction": customer.avg_satisfaction_score,
                "churn_risk": customer.churn_risk_score,
                "lifetime_value": customer.lifetime_value,
            },
        }

    def _find_existing_customer(self, client_id, normalized_email: str, normalized_phone: str) -> Optional[Customer]:
        if normalized_email:
            direct = (
                self.db.query(Customer)
                .filter(
                    Customer.client_id == client_id,
                    Customer.is_master == True,
                    Customer.primary_email == normalized_email,
                )
                .first()
            )
            if direct:
                return direct

        if normalized_phone:
            direct = (
                self.db.query(Customer)
                .filter(
                    Customer.client_id == client_id,
                    Customer.is_master == True,
                    Customer.primary_phone == normalized_phone,
                )
                .first()
            )
            if direct:
                return direct

        candidates = (
            self.db.query(Customer)
            .filter(Customer.client_id == client_id, Customer.is_master == True)
            .all()
        )
        for candidate in candidates:
            if normalized_email and normalized_email in CustomerDeduplicator._emails_for(candidate):
                return candidate
            if normalized_phone and normalized_phone in CustomerDeduplicator._phones_for(candidate):
                return candidate
        return None

    def _apply_identity_updates(
        self,
        customer: Customer,
        normalized_email: str,
        normalized_phone: str,
        name: Optional[str],
        company: Optional[str],
    ) -> bool:
        changed = False
        if normalized_email:
            if not customer.primary_email:
                customer.primary_email = normalized_email
                changed = True
            emails = list(customer.emails or [])
            if normalized_email not in emails:
                emails.append(normalized_email)
                customer.emails = emails
                changed = True
        if normalized_phone:
            if not customer.primary_phone:
                customer.primary_phone = normalized_phone
                changed = True
            phones = list(customer.phones or [])
            if normalized_phone not in phones:
                phones.append(normalized_phone)
                customer.phones = phones
                changed = True
        display_name = (name or "").strip()
        company_name = (company or "").strip()
        if display_name and not customer.full_name:
            customer.full_name = display_name
            changed = True
        if company_name and not customer.company_name:
            customer.company_name = company_name
            changed = True
        return changed

    def _link_matching_complaints(self, customer: Customer) -> None:
        emails = CustomerDeduplicator._emails_for(customer)
        phones = CustomerDeduplicator._phones_for(customer)
        query = self.db.query(Complaint).filter(Complaint.client_id == customer.client_id, Complaint.customer_id.is_(None))
        filters = []
        if emails:
            filters.append(func.lower(Complaint.customer_email).in_(emails))
        if phones:
            filters.append(Complaint.customer_phone.in_(phones))
        if not filters:
            return
        query.filter(or_(*filters)).update({"customer_id": customer.id}, synchronize_session=False)

    def _build_satisfaction_trend(self, customer_id) -> list[dict[str, Any]]:
        ninety_days_ago = _utcnow() - timedelta(days=90)
        complaints = (
            self.db.query(Complaint)
            .filter(
                Complaint.customer_id == customer_id,
                Complaint.created_at >= ninety_days_ago,
            )
            .order_by(Complaint.created_at.asc())
            .all()
        )

        weekly_scores: dict[str, list[float]] = {}
        for complaint in complaints:
            score = complaint.satisfaction_score or complaint.customer_satisfaction_score
            if score is None or complaint.created_at is None:
                continue
            created_at = complaint.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            week_start = (created_at - timedelta(days=created_at.weekday())).date().isoformat()
            weekly_scores.setdefault(week_start, []).append(float(score))

        return [
            {"week": week_start, "avg_score": round(sum(scores) / len(scores), 2)}
            for week_start, scores in sorted(weekly_scores.items())
        ]

    def _calculate_churn_indicators(self, customer: Customer) -> dict[str, Any]:
        thirty_days_ago = _utcnow() - timedelta(days=30)
        recent_tickets = (
            self.db.query(func.count(Complaint.id))
            .filter(Complaint.customer_id == customer.id, Complaint.created_at >= thirty_days_ago)
            .scalar()
            or 0
        )
        recent_negative_tickets = (
            self.db.query(func.count(Complaint.id))
            .filter(
                Complaint.customer_id == customer.id,
                Complaint.created_at >= thirty_days_ago,
                Complaint.sentiment < -0.3,
            )
            .scalar()
            or 0
        )
        total_escalations = (
            self.db.query(func.count(Complaint.id))
            .filter(Complaint.customer_id == customer.id, Complaint.escalation_level > 0)
            .scalar()
            or 0
        )

        days_since_last = None
        if customer.last_interaction_at:
            last_seen = customer.last_interaction_at
            if last_seen.tzinfo is None:
                last_seen = last_seen.replace(tzinfo=timezone.utc)
            days_since_last = (_utcnow() - last_seen).days

        return {
            "recent_ticket_volume": int(recent_tickets),
            "recent_negative_tickets": int(recent_negative_tickets),
            "total_escalations": int(total_escalations),
            "days_since_last_interaction": days_since_last,
            "low_satisfaction": bool(customer.avg_satisfaction_score is not None and customer.avg_satisfaction_score < 3.0),
        }

    def _calculate_churn_risk_score(self, customer: Customer) -> float:
        indicators = self._calculate_churn_indicators(customer)
        score = 0.0
        score += min(indicators["recent_ticket_volume"] * 12, 36)
        score += min(indicators["recent_negative_tickets"] * 15, 30)
        score += min(indicators["total_escalations"] * 8, 24)
        if indicators["low_satisfaction"]:
            score += 10
        if indicators["days_since_last_interaction"] is not None and indicators["days_since_last_interaction"] > 45:
            score += min((indicators["days_since_last_interaction"] - 45) * 0.4, 20)
        return round(min(score, 100.0), 2)

    @staticmethod
    def _as_uuid(value) -> uuid.UUID:
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))


def serialize_customer(customer: Customer) -> dict[str, Any]:
    return {
        "id": str(customer.id),
        "client_id": str(customer.client_id),
        "primary_email": customer.primary_email,
        "primary_phone": customer.primary_phone,
        "full_name": customer.full_name,
        "company_name": customer.company_name,
        "emails": customer.emails or [],
        "phones": customer.phones or [],
        "customer_type": customer.customer_type,
        "status": customer.status,
        "tags": customer.tags or [],
        "total_tickets": customer.total_tickets,
        "total_interactions": customer.total_interactions,
        "first_interaction_at": customer.first_interaction_at.isoformat() if customer.first_interaction_at else None,
        "last_interaction_at": customer.last_interaction_at.isoformat() if customer.last_interaction_at else None,
        "avg_satisfaction_score": customer.avg_satisfaction_score,
        "churn_risk_score": customer.churn_risk_score,
        "lifetime_value": customer.lifetime_value,
        "enrichment_data": customer.enrichment_data or {},
        "custom_fields": customer.custom_fields or {},
        "is_master": customer.is_master,
        "merged_into": str(customer.merged_into) if customer.merged_into else None,
        "confidence_score": customer.confidence_score,
        "created_at": customer.created_at.isoformat() if customer.created_at else None,
        "updated_at": customer.updated_at.isoformat() if customer.updated_at else None,
    }


def serialize_customer_interaction(interaction: CustomerInteraction) -> dict[str, Any]:
    return {
        "id": str(interaction.id),
        "customer_id": str(interaction.customer_id),
        "client_id": str(interaction.client_id),
        "interaction_type": interaction.interaction_type,
        "interaction_channel": interaction.interaction_channel,
        "complaint_id": str(interaction.complaint_id) if interaction.complaint_id else None,
        "summary": interaction.summary,
        "sentiment_score": interaction.sentiment_score,
        "duration_seconds": interaction.duration_seconds,
        "metadata": interaction.metadata_json or {},
        "created_at": interaction.created_at.isoformat() if interaction.created_at else None,
    }


def serialize_customer_note(note: CustomerNote) -> dict[str, Any]:
    return {
        "id": str(note.id),
        "customer_id": str(note.customer_id),
        "author_email": note.author_email,
        "note_type": note.note_type,
        "content": note.content,
        "pinned": note.pinned,
        "created_at": note.created_at.isoformat() if note.created_at else None,
        "updated_at": note.updated_at.isoformat() if note.updated_at else None,
    }


def serialize_customer_relationship(relationship: CustomerRelationship) -> dict[str, Any]:
    return {
        "id": str(relationship.id),
        "client_id": str(relationship.client_id),
        "parent_customer_id": str(relationship.parent_customer_id),
        "child_customer_id": str(relationship.child_customer_id),
        "relationship_type": relationship.relationship_type,
        "role_title": relationship.role_title,
        "is_primary_contact": relationship.is_primary_contact,
        "created_at": relationship.created_at.isoformat() if relationship.created_at else None,
    }


def serialize_customer_ticket(complaint: Complaint) -> dict[str, Any]:
    return {
        "id": str(complaint.id),
        "ticket_id": complaint.ticket_id,
        "ticket_number": complaint.ticket_number or complaint.ticket_id,
        "summary": complaint.summary,
        "source": complaint.source,
        "category": complaint.category,
        "priority": complaint.priority,
        "state": complaint.state,
        "sla_status": complaint.sla_status,
        "resolution_status": complaint.resolution_status,
        "assigned_to": complaint.assigned_to,
        "created_at": complaint.created_at.isoformat() if complaint.created_at else None,
        "resolved_at": complaint.resolved_at.isoformat() if complaint.resolved_at else None,
    }
