import logging
import re
import uuid
from difflib import SequenceMatcher
from typing import Optional

from sqlalchemy.orm import Session

from app.db.models import (
    Complaint,
    Customer,
    CustomerInteraction,
    CustomerMergeHistory,
    CustomerNote,
    CustomerRelationship,
    UnifiedMessage,
)

logger = logging.getLogger(__name__)


class CustomerDeduplicator:
    """Multi-strategy customer deduplication."""

    EXACT_MATCH_THRESHOLD = 1.0
    FUZZY_NAME_THRESHOLD = 0.85
    AUTO_MERGE_THRESHOLD = 0.95

    def __init__(self, db: Session):
        self.db = db

    def find_duplicates(self, customer: Customer, limit: int = 10) -> list[tuple[Customer, float]]:
        candidates = (
            self.db.query(Customer)
            .filter(
                Customer.client_id == customer.client_id,
                Customer.id != customer.id,
                Customer.is_master == True,
            )
            .all()
        )

        scored: list[tuple[Customer, float]] = []
        customer_emails = set(self._emails_for(customer))
        customer_phones = set(self._phones_for(customer))
        customer_domain = self._email_domain(customer.primary_email)
        customer_name = self._display_name(customer)
        customer_company = (customer.company_name or "").strip().lower()

        for candidate in candidates:
            score = 0.0

            if customer_emails and customer_emails.intersection(self._emails_for(candidate)):
                score = 1.0

            if customer_phones and customer_phones.intersection(self._phones_for(candidate)):
                score = max(score, 1.0)

            if customer_company and customer_company == (candidate.company_name or "").strip().lower():
                score = max(score, 0.8)

            candidate_name = self._display_name(candidate)
            candidate_domain = self._email_domain(candidate.primary_email)
            if customer_name and candidate_name and customer_domain and customer_domain == candidate_domain:
                similarity = SequenceMatcher(None, customer_name, candidate_name).ratio()
                if similarity >= self.FUZZY_NAME_THRESHOLD:
                    score = max(score, similarity)

            if score > 0:
                scored.append((candidate, round(score, 4)))

        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:limit]

    def merge_customers(
        self,
        master_id: str,
        duplicate_id: str,
        merged_by: str,
        merge_strategy: str = "manual",
        confidence_score: float = 1.0,
        commit: bool = True,
    ) -> Customer:
        master_uuid = self._as_uuid(master_id)
        duplicate_uuid = self._as_uuid(duplicate_id)
        master = self.db.query(Customer).filter(Customer.id == master_uuid).first()
        duplicate = self.db.query(Customer).filter(Customer.id == duplicate_uuid).first()

        if not master or not duplicate:
            raise ValueError("Customer not found")
        if master.id == duplicate.id:
            raise ValueError("Cannot merge a customer into itself")
        if master.client_id != duplicate.client_id:
            raise ValueError("Cannot merge across tenants")

        if not master.is_master and master.merged_into:
            resolved_master = self.db.query(Customer).filter(Customer.id == master.merged_into).first()
            if resolved_master:
                master = resolved_master
        if not duplicate.is_master and duplicate.merged_into:
            raise ValueError("Duplicate customer is already merged")

        master.primary_email = master.primary_email or duplicate.primary_email
        master.primary_phone = master.primary_phone or duplicate.primary_phone
        master.name = master.name or duplicate.name or duplicate.full_name
        master.full_name = master.full_name or duplicate.full_name
        master.company_name = master.company_name or duplicate.company_name
        master.customer_type = master.customer_type or duplicate.customer_type or "individual"
        master.status = master.status or duplicate.status or "active"
        master.emails = self._merge_unique(self._emails_for(master), self._emails_for(duplicate))
        master.merged_emails = self._merge_unique(
            self._merged_emails_for(master),
            [email for email in self._emails_for(duplicate) if email != self._normalize_email(master.primary_email)],
        )
        master.phones = self._merge_unique(self._phones_for(master), self._phones_for(duplicate))
        master.tags = self._merge_unique(master.tags or [], duplicate.tags or [])
        master.notes = self._merge_text(master.notes, duplicate.notes)
        master.custom_fields = {**(duplicate.custom_fields or {}), **(master.custom_fields or {})}
        master.enrichment_data = {**(duplicate.enrichment_data or {}), **(master.enrichment_data or {})}
        master.lifetime_value = float(master.lifetime_value or 0.0) + float(duplicate.lifetime_value or 0.0)
        master.confidence_score = max(float(master.confidence_score or 0.0), float(confidence_score or 0.0))

        self.db.query(Complaint).filter(Complaint.customer_id == duplicate.id).update({"customer_id": master.id})
        self.db.query(CustomerInteraction).filter(CustomerInteraction.customer_id == duplicate.id).update({"customer_id": master.id})
        self.db.query(CustomerNote).filter(CustomerNote.customer_id == duplicate.id).update({"customer_id": master.id})
        self.db.query(UnifiedMessage).filter(UnifiedMessage.customer_id == duplicate.id).update({"customer_id": master.id})

        self._merge_relationships(master, duplicate)

        duplicate.is_master = False
        duplicate.merged_into = master.id
        duplicate.status = "inactive"
        duplicate.primary_email = None

        self.db.add(
            CustomerMergeHistory(
                client_id=master.client_id,
                master_customer_id=master.id,
                merged_customer_id=duplicate.id,
                merge_reason=f"Merged via {merge_strategy}",
                confidence_score=confidence_score,
                merged_by=merged_by,
                auto_merged=(merge_strategy == "auto"),
                merge_strategy=merge_strategy,
                metadata_json={
                    "master_emails": master.emails or [],
                    "master_phones": master.phones or [],
                },
            )
        )

        from app.services.customer_profile import CustomerProfileService

        CustomerProfileService(self.db).refresh_customer_metrics(master, commit=False)

        if commit:
            self.db.commit()
            self.db.refresh(master)
        else:
            self.db.flush()

        logger.info("Merged customer %s into %s using %s", duplicate.id, master.id, merge_strategy)
        return master

    def auto_deduplicate(self, customer: Customer, commit: bool = True) -> Optional[Customer]:
        duplicates = self.find_duplicates(customer, limit=5)
        for duplicate, confidence in duplicates:
            if confidence >= self.AUTO_MERGE_THRESHOLD:
                logger.info(
                    "Auto-merging customer %s into %s with confidence %.2f",
                    customer.id,
                    duplicate.id,
                    confidence,
                )
                return self.merge_customers(
                    master_id=str(duplicate.id),
                    duplicate_id=str(customer.id),
                    merged_by="system",
                    merge_strategy="auto",
                    confidence_score=confidence,
                    commit=commit,
                )
        return None

    def _merge_relationships(self, master: Customer, duplicate: Customer) -> None:
        relationships = (
            self.db.query(CustomerRelationship)
            .filter(
                (CustomerRelationship.parent_customer_id == duplicate.id)
                | (CustomerRelationship.child_customer_id == duplicate.id)
            )
            .all()
        )
        for relationship in relationships:
            new_parent = master.id if relationship.parent_customer_id == duplicate.id else relationship.parent_customer_id
            new_child = master.id if relationship.child_customer_id == duplicate.id else relationship.child_customer_id

            if new_parent == new_child:
                self.db.delete(relationship)
                continue

            existing = (
                self.db.query(CustomerRelationship)
                .filter(
                    CustomerRelationship.id != relationship.id,
                    CustomerRelationship.parent_customer_id == new_parent,
                    CustomerRelationship.child_customer_id == new_child,
                )
                .first()
            )
            if existing:
                existing.is_primary_contact = existing.is_primary_contact or relationship.is_primary_contact
                existing.role_title = existing.role_title or relationship.role_title
                self.db.delete(relationship)
                continue

            relationship.parent_customer_id = new_parent
            relationship.child_customer_id = new_child

    @staticmethod
    def _normalize_email(email: str | None) -> str:
        return (email or "").strip().lower()

    @staticmethod
    def _as_uuid(value) -> uuid.UUID:
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))

    @classmethod
    def _normalize_phone(cls, phone: str | None) -> str:
        if not phone:
            return ""
        digits = re.sub(r"\D", "", phone)
        return digits[-10:] if len(digits) >= 10 else digits

    @classmethod
    def _emails_for(cls, customer: Customer) -> list[str]:
        values = list(customer.emails or [])
        values.extend(customer.merged_emails or [])
        if customer.primary_email:
            values.append(customer.primary_email)
        normalized: list[str] = []
        for value in values:
            email = cls._normalize_email(value)
            if email and email not in normalized:
                normalized.append(email)
        return normalized

    @classmethod
    def _merged_emails_for(cls, customer: Customer) -> list[str]:
        normalized: list[str] = []
        for value in customer.merged_emails or []:
            email = cls._normalize_email(value)
            if email and email != cls._normalize_email(customer.primary_email) and email not in normalized:
                normalized.append(email)
        return normalized

    @classmethod
    def _phones_for(cls, customer: Customer) -> list[str]:
        values = list(customer.phones or [])
        if customer.primary_phone:
            values.append(customer.primary_phone)
        normalized: list[str] = []
        for value in values:
            phone = cls._normalize_phone(value)
            if phone and phone not in normalized:
                normalized.append(phone)
        return normalized

    @staticmethod
    def _email_domain(email: str | None) -> str:
        value = (email or "").strip().lower()
        if "@" not in value:
            return ""
        return value.split("@", 1)[1]

    @classmethod
    def _display_name(cls, customer: Customer) -> str:
        return (customer.name or customer.full_name or "").strip().lower()

    @staticmethod
    def _merge_unique(primary: list, secondary: list) -> list:
        merged: list = []
        for value in [*(primary or []), *(secondary or [])]:
            if value not in merged:
                merged.append(value)
        return merged

    @staticmethod
    def _merge_text(primary: str | None, secondary: str | None) -> str | None:
        first = (primary or "").strip()
        second = (secondary or "").strip()
        if not first:
            return second or None
        if not second or second == first:
            return first
        return f"{first}\n\n{second}"
