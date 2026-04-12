from datetime import datetime, timedelta, timezone
import uuid
from typing import Any, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.db.models import Complaint, Customer, CustomerInteraction, CustomerNote, CustomerRelationship, UnifiedMessage
from app.services.customer_deduplication import CustomerDeduplicator


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_name(value: str | None) -> str:
    return " ".join((value or "").strip().lower().split())


def _email_domain(email: str | None) -> str:
    normalized = CustomerDeduplicator._normalize_email(email)
    if "@" not in normalized:
        return ""
    return normalized.split("@", 1)[1]


def _safe_timestamp(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _safe_iso(value: datetime | None) -> str | None:
    timestamp = _safe_timestamp(value)
    return timestamp.isoformat() if timestamp else None


def _sentiment_label(score: float | None) -> str:
    numeric = float(score or 0.0)
    if numeric > 0.2:
        return "positive"
    if numeric < -0.2:
        return "negative"
    return "neutral"


class CustomerProfileService:
    def __init__(self, db: Session):
        self.db = db

    def resolve_customer(
        self,
        client_id,
        email: Optional[str] = None,
        name: Optional[str] = None,
        phone: Optional[str] = None,
        company: Optional[str] = None,
        commit: bool = False,
    ) -> Optional[Customer]:
        normalized_email = CustomerDeduplicator._normalize_email(email)
        normalized_phone = CustomerDeduplicator._normalize_phone(phone)
        normalized_name = _normalize_name(name)

        if not normalized_email and not normalized_phone:
            return None

        existing = self._find_existing_customer(
            client_id,
            normalized_email=normalized_email,
            normalized_phone=normalized_phone,
            normalized_name=normalized_name,
        )
        if existing:
            changed = self._apply_identity_updates(existing, normalized_email, normalized_phone, name, company)
            if changed:
                self._link_matching_complaints(existing)
                self._link_matching_messages(existing)
                self.refresh_customer_metrics(existing, commit=False)
            if commit:
                self.db.commit()
                self.db.refresh(existing)
            elif changed:
                self.db.flush()
            return existing

        customer = Customer(
            client_id=client_id,
            primary_email=normalized_email or None,
            name=(name or "").strip() or None,
            primary_phone=normalized_phone or None,
            full_name=(name or "").strip() or None,
            company_name=(company or "").strip() or None,
            emails=[normalized_email] if normalized_email else [],
            merged_emails=[],
            phones=[normalized_phone] if normalized_phone else [],
            first_interaction_at=_utcnow(),
            last_interaction_at=_utcnow(),
            last_contacted_at=_utcnow(),
        )
        self.db.add(customer)
        self.db.flush()

        merged = CustomerDeduplicator(self.db).auto_deduplicate(customer, commit=False)
        resolved = merged or customer
        self._link_matching_complaints(resolved)
        self._link_matching_messages(resolved)
        self.refresh_customer_metrics(resolved, commit=False)

        if commit:
            self.db.commit()
            self.db.refresh(resolved)
        else:
            self.db.flush()
        return resolved

    def get_or_create_customer(
        self,
        client_id,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        name: Optional[str] = None,
        company: Optional[str] = None,
        commit: bool = False,
    ) -> Optional[Customer]:
        return self.resolve_customer(
            client_id=client_id,
            email=email,
            name=name,
            phone=phone,
            company=company,
            commit=commit,
        )

    def sync_customer_for_complaint(
        self,
        complaint: Complaint,
        interaction_type: str = "ticket",
        interaction_channel: Optional[str] = None,
        name: Optional[str] = None,
        company: Optional[str] = None,
        source_message: UnifiedMessage | None = None,
        commit: bool = False,
    ) -> Optional[Customer]:
        customer = None
        if complaint.customer_id:
            customer = self.db.query(Customer).filter(Customer.id == complaint.customer_id).first()

        if customer is None:
            customer = self.resolve_customer(
                client_id=complaint.client_id,
                email=complaint.customer_email,
                name=name,
                phone=complaint.customer_phone,
                company=company,
                commit=False,
            )

        if customer is None:
            return None

        if complaint.customer_id != customer.id:
            complaint.customer_id = customer.id
        if source_message is not None and source_message.customer_id != customer.id:
            source_message.customer_id = customer.id

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
            name,
            company,
        )
        self._link_matching_complaints(customer)
        self._link_matching_messages(customer)
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
        message_rows = (
            self.db.query(UnifiedMessage)
            .filter(UnifiedMessage.customer_id == customer.id)
            .order_by(UnifiedMessage.timestamp.asc(), UnifiedMessage.created_at.asc())
            .all()
        )
        interaction_rows = (
            self.db.query(CustomerInteraction)
            .filter(CustomerInteraction.customer_id == customer.id)
            .order_by(CustomerInteraction.created_at.asc())
            .all()
        )

        if customer.name and not customer.full_name:
            customer.full_name = customer.name
        elif customer.full_name and not customer.name:
            customer.name = customer.full_name

        customer.total_messages = len(message_rows)
        customer.total_tickets = len(complaint_rows)
        customer.open_tickets = len([row for row in complaint_rows if row.resolution_status != "resolved"])
        customer.total_interactions = len(interaction_rows)

        timestamps = [
            timestamp
            for timestamp in (
                _safe_timestamp(row.created_at)
                for row in complaint_rows
            )
            if timestamp is not None
        ]
        timestamps.extend(
            timestamp
            for timestamp in (
                _safe_timestamp(row.created_at)
                for row in interaction_rows
            )
            if timestamp is not None
        )
        timestamps.extend(
            timestamp
            for timestamp in (
                _safe_timestamp(row.timestamp) or _safe_timestamp(row.created_at)
                for row in message_rows
            )
            if timestamp is not None
        )
        if timestamps:
            customer.first_interaction_at = min(timestamps)
            customer.last_interaction_at = max(timestamps)
            customer.last_contacted_at = max(timestamps)

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
        response_times = [float(row.response_time_seconds) for row in complaint_rows if row.response_time_seconds is not None]
        customer.avg_response_time = round(sum(response_times) / len(response_times), 2) if response_times else None

        sentiment = self.compute_customer_sentiment(customer.id)
        customer.sentiment_score = sentiment["score"]
        customer.sentiment_label = sentiment["label"]

        churn = self.compute_churn_risk(customer)
        customer.churn_risk = churn["level"]
        customer.churn_risk_score = churn["score"]

        if commit:
            self.db.commit()
            self.db.refresh(customer)
        else:
            self.db.flush()
        return customer

    def get_customer_360(self, customer_id: str) -> dict[str, Any]:
        customer = self._get_customer_or_master(customer_id)

        self.refresh_customer_metrics(customer, commit=False)

        recent_tickets = (
            self.db.query(Complaint)
            .filter(Complaint.customer_id == customer.id)
            .order_by(Complaint.created_at.desc())
            .limit(30)
            .all()
        )
        recent_messages = (
            self.db.query(UnifiedMessage)
            .filter(UnifiedMessage.customer_id == customer.id)
            .order_by(UnifiedMessage.timestamp.desc(), UnifiedMessage.created_at.desc())
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
        active_tickets = [ticket for ticket in recent_tickets if ticket.resolution_status != "resolved"]
        sentiment = self.compute_customer_sentiment(customer.id)
        churn = self.compute_churn_risk(customer)
        timeline = self._build_customer_timeline(
            recent_messages=recent_messages,
            recent_tickets=recent_tickets,
            notes=notes,
        )

        return {
            "profile": customer,
            "recent_tickets": recent_tickets,
            "recent_messages": recent_messages,
            "active_tickets": active_tickets,
            "interaction_timeline": interactions,
            "timeline": timeline,
            "notes": notes,
            "relationships": relationships,
            "satisfaction_trend": self._build_satisfaction_trend(customer.id),
            "churn_indicators": self._calculate_churn_indicators(customer),
            "sentiment": sentiment,
            "insights": self._build_insights(customer, recent_tickets, sentiment, churn),
            "stats": {
                "total_messages": customer.total_messages,
                "total_tickets": customer.total_tickets,
                "open_tickets": customer.open_tickets,
                "total_interactions": customer.total_interactions,
                "last_contacted_at": _safe_iso(customer.last_contacted_at),
                "avg_response_time": customer.avg_response_time,
                "avg_satisfaction": customer.avg_satisfaction_score,
                "churn_risk": customer.churn_risk_score,
                "lifetime_value": customer.lifetime_value,
            },
        }

    def get_customer_360_snapshot(self, customer_id: str) -> dict[str, Any]:
        customer = self._get_customer_or_master(customer_id)
        self.refresh_customer_metrics(customer, commit=False)

        recent_messages = (
            self.db.query(UnifiedMessage)
            .filter(UnifiedMessage.customer_id == customer.id)
            .order_by(UnifiedMessage.timestamp.desc(), UnifiedMessage.created_at.desc())
            .limit(10)
            .all()
        )
        recent_tickets = (
            self.db.query(Complaint)
            .filter(Complaint.customer_id == customer.id)
            .order_by(Complaint.created_at.desc())
            .limit(10)
            .all()
        )
        notes = (
            self.db.query(CustomerNote)
            .filter(CustomerNote.customer_id == customer.id)
            .order_by(CustomerNote.pinned.desc(), CustomerNote.created_at.desc())
            .limit(10)
            .all()
        )
        active_tickets = [ticket for ticket in recent_tickets if ticket.resolution_status != "resolved"]
        sentiment = self.compute_customer_sentiment(customer.id)
        churn = self.compute_churn_risk(customer)
        return {
            "identity": {
                "id": str(customer.id),
                "client_id": str(customer.client_id),
                "name": customer.name or customer.full_name,
                "primary_email": customer.primary_email,
                "merged_emails": CustomerDeduplicator._merged_emails_for(customer),
                "tags": list(customer.tags or []),
                "notes": customer.notes,
                "created_at": _safe_iso(customer.created_at),
                "updated_at": _safe_iso(customer.updated_at),
            },
            "metrics": {
                "total_messages": customer.total_messages,
                "total_tickets": customer.total_tickets,
                "open_tickets": customer.open_tickets,
                "last_contacted_at": _safe_iso(customer.last_contacted_at),
                "avg_response_time": customer.avg_response_time,
            },
            "sentiment": sentiment,
            "churn_risk": churn["level"],
            "recent_messages": [serialize_customer_message(message) for message in recent_messages],
            "recent_tickets": [serialize_customer_ticket(ticket) for ticket in recent_tickets],
            "active_tickets": [serialize_customer_ticket(ticket) for ticket in active_tickets],
            "timeline": self._build_customer_timeline(
                recent_messages=recent_messages,
                recent_tickets=recent_tickets,
                notes=notes,
            ),
            "insights": self._build_insights(customer, recent_tickets, sentiment, churn),
        }

    def _find_existing_customer(
        self,
        client_id,
        normalized_email: str,
        normalized_phone: str,
        normalized_name: str | None = None,
    ) -> Optional[Customer]:
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

        if normalized_email and normalized_name:
            email_domain = _email_domain(normalized_email)
            for candidate in candidates:
                candidate_domain = _email_domain(candidate.primary_email)
                candidate_name = _normalize_name(candidate.name or candidate.full_name)
                if email_domain and candidate_domain == email_domain and candidate_name == normalized_name:
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
            elif customer.primary_email != normalized_email:
                merged_emails = CustomerDeduplicator._merged_emails_for(customer)
                if normalized_email not in merged_emails:
                    merged_emails.append(normalized_email)
                    customer.merged_emails = merged_emails
                    changed = True

            emails = CustomerDeduplicator._emails_for(customer)
            if normalized_email not in emails:
                emails.append(normalized_email)
            if customer.primary_email and customer.primary_email not in emails:
                emails.insert(0, customer.primary_email)
            if emails != list(customer.emails or []):
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
        if display_name and not customer.name:
            customer.name = display_name
            changed = True
        if display_name and not customer.full_name:
            customer.full_name = display_name
            changed = True
        if customer.name and not customer.full_name:
            customer.full_name = customer.name
            changed = True
        if customer.full_name and not customer.name:
            customer.name = customer.full_name
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

    def _link_matching_messages(self, customer: Customer) -> None:
        emails = CustomerDeduplicator._emails_for(customer)
        phones = CustomerDeduplicator._phones_for(customer)
        query = self.db.query(UnifiedMessage).filter(
            UnifiedMessage.client_id == customer.client_id,
            UnifiedMessage.customer_id.is_(None),
        )
        match_filters = []
        if emails:
            match_filters.append(
                (UnifiedMessage.channel.in_(["email", "gmail"])) & func.lower(UnifiedMessage.sender_id).in_(emails)
            )
        if phones:
            match_filters.append((UnifiedMessage.channel == "whatsapp") & UnifiedMessage.sender_id.in_(phones))
        if not match_filters:
            return
        query.filter(or_(*match_filters)).update({"customer_id": customer.id}, synchronize_session=False)

    def compute_customer_sentiment(self, customer_id) -> dict[str, Any]:
        resolved_customer = self._get_customer_or_master(customer_id)
        recent_messages = (
            self.db.query(UnifiedMessage)
            .filter(
                UnifiedMessage.customer_id == resolved_customer.id,
                UnifiedMessage.direction == "inbound",
            )
            .order_by(UnifiedMessage.timestamp.desc(), UnifiedMessage.created_at.desc())
            .limit(10)
            .all()
        )

        scores: list[float] = []
        for message in recent_messages:
            score = self._message_sentiment_score(message)
            if score is not None:
                scores.append(score)

        if len(scores) < 5:
            complaints = (
                self.db.query(Complaint)
                .filter(Complaint.customer_id == resolved_customer.id)
                .order_by(Complaint.created_at.desc())
                .limit(10)
                .all()
            )
            for complaint in complaints:
                if complaint.sentiment is None:
                    continue
                scores.append(float(complaint.sentiment))
                if len(scores) >= 10:
                    break

        score = round(sum(scores) / len(scores), 3) if scores else None
        return {
            "score": score,
            "label": _sentiment_label(score),
            "sample_size": len(scores),
        }

    def compute_churn_risk(self, customer: Customer | str | uuid.UUID) -> dict[str, Any]:
        resolved_customer = customer if isinstance(customer, Customer) else self._get_customer_or_master(customer)
        indicators = self._calculate_churn_indicators(resolved_customer)

        negative_streak = bool(indicators["negative_sentiment_streak"])
        many_recent_complaints = indicators["recent_ticket_volume"] >= 3
        unresolved_tickets = indicators["unresolved_tickets"] >= 2

        if (negative_streak and (many_recent_complaints or unresolved_tickets)) or (
            indicators["recent_negative_tickets"] >= 3 and indicators["unresolved_tickets"] >= 1
        ):
            level = "high"
            score = min(95, 80 + indicators["recent_negative_tickets"] * 3 + indicators["unresolved_tickets"] * 2)
        elif negative_streak or many_recent_complaints or indicators["unresolved_tickets"] >= 1:
            level = "medium"
            score = min(70, 45 + indicators["recent_ticket_volume"] * 4 + indicators["unresolved_tickets"] * 3)
        else:
            level = "low"
            score = min(30, 10 + indicators["recent_ticket_volume"] * 3)

        return {
            "level": level,
            "score": float(score),
            "signals": indicators,
        }

    def _get_customer_or_master(self, customer_id) -> Customer:
        customer = self.db.query(Customer).filter(Customer.id == self._as_uuid(customer_id)).first()
        if not customer:
            raise ValueError("Customer not found")
        if not customer.is_master and customer.merged_into:
            resolved = self.db.query(Customer).filter(Customer.id == customer.merged_into).first()
            if resolved:
                customer = resolved
        return customer

    def _build_customer_timeline(
        self,
        *,
        recent_messages: list[UnifiedMessage],
        recent_tickets: list[Complaint],
        notes: list[CustomerNote],
    ) -> list[dict[str, Any]]:
        items = [serialize_customer_timeline_message(message) for message in recent_messages]
        items.extend(serialize_customer_timeline_ticket(ticket) for ticket in recent_tickets)
        items.extend(serialize_customer_timeline_note(note) for note in notes)
        return sorted(items, key=lambda item: item["sort_at"] or "", reverse=True)

    def _build_insights(
        self,
        customer: Customer,
        recent_tickets: list[Complaint],
        sentiment: dict[str, Any],
        churn: dict[str, Any],
    ) -> list[str]:
        insights: list[str] = []
        if recent_tickets:
            categories: dict[str, int] = {}
            for ticket in recent_tickets:
                category = (ticket.category or "general").strip().lower() or "general"
                categories[category] = categories.get(category, 0) + 1
            top_category, top_count = sorted(categories.items(), key=lambda item: item[1], reverse=True)[0]
            if top_count >= 2:
                insights.append(f"Frequent complaints: {top_category}")
        if sentiment.get("label") == "negative":
            insights.append("Negative sentiment trend")
        if churn["level"] == "high":
            insights.append("High churn risk")
        elif churn["level"] == "medium":
            insights.append("Retention follow-up recommended")
        if customer.open_tickets:
            insights.append(f"{customer.open_tickets} unresolved ticket(s) need attention")
        return insights[:5]

    def _message_sentiment_score(self, message: UnifiedMessage) -> float | None:
        raw_payload = message.raw_payload if isinstance(message.raw_payload, dict) else {}
        raw_score = raw_payload.get("sentiment")
        if raw_score is None:
            return None
        try:
            return float(raw_score)
        except (TypeError, ValueError):
            return None

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
        recent_message_scores = [
            score
            for score in (
                self._message_sentiment_score(message)
                for message in self.db.query(UnifiedMessage)
                .filter(
                    UnifiedMessage.customer_id == customer.id,
                    UnifiedMessage.direction == "inbound",
                )
                .order_by(UnifiedMessage.timestamp.desc(), UnifiedMessage.created_at.desc())
                .limit(5)
                .all()
            )
            if score is not None
        ]
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
        unresolved_tickets = (
            self.db.query(func.count(Complaint.id))
            .filter(
                Complaint.customer_id == customer.id,
                Complaint.resolution_status != "resolved",
            )
            .scalar()
            or 0
        )

        days_since_last = None
        last_seen = _safe_timestamp(customer.last_contacted_at or customer.last_interaction_at)
        if last_seen:
            days_since_last = (_utcnow() - last_seen).days

        return {
            "recent_ticket_volume": int(recent_tickets),
            "recent_negative_tickets": int(recent_negative_tickets),
            "negative_sentiment_streak": bool(recent_message_scores[:3]) and all(score <= -0.25 for score in recent_message_scores[:3]),
            "unresolved_tickets": int(unresolved_tickets),
            "total_escalations": int(total_escalations),
            "days_since_last_interaction": days_since_last,
            "low_satisfaction": bool(customer.avg_satisfaction_score is not None and customer.avg_satisfaction_score < 3.0),
        }

    def _calculate_churn_risk_score(self, customer: Customer) -> float:
        return round(float(self.compute_churn_risk(customer)["score"]), 2)

    @staticmethod
    def _as_uuid(value) -> uuid.UUID:
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))


def serialize_customer(customer: Customer) -> dict[str, Any]:
    return {
        "id": str(customer.id),
        "client_id": str(customer.client_id),
        "name": customer.name or customer.full_name,
        "primary_email": customer.primary_email,
        "primary_phone": customer.primary_phone,
        "full_name": customer.name or customer.full_name,
        "company_name": customer.company_name,
        "emails": customer.emails or [],
        "merged_emails": CustomerDeduplicator._merged_emails_for(customer),
        "phones": customer.phones or [],
        "customer_type": customer.customer_type,
        "status": customer.status,
        "tags": customer.tags or [],
        "notes": customer.notes,
        "total_messages": customer.total_messages,
        "total_tickets": customer.total_tickets,
        "open_tickets": customer.open_tickets,
        "total_interactions": customer.total_interactions,
        "first_interaction_at": _safe_iso(customer.first_interaction_at),
        "last_interaction_at": _safe_iso(customer.last_interaction_at),
        "last_contacted_at": _safe_iso(customer.last_contacted_at),
        "avg_response_time": customer.avg_response_time,
        "sentiment_score": customer.sentiment_score,
        "sentiment_label": customer.sentiment_label,
        "churn_risk": customer.churn_risk,
        "avg_satisfaction_score": customer.avg_satisfaction_score,
        "churn_risk_score": customer.churn_risk_score,
        "lifetime_value": customer.lifetime_value,
        "enrichment_data": customer.enrichment_data or {},
        "custom_fields": customer.custom_fields or {},
        "is_master": customer.is_master,
        "merged_into": str(customer.merged_into) if customer.merged_into else None,
        "confidence_score": customer.confidence_score,
        "created_at": _safe_iso(customer.created_at),
        "updated_at": _safe_iso(customer.updated_at),
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
        "created_at": _safe_iso(interaction.created_at),
    }


def serialize_customer_note(note: CustomerNote) -> dict[str, Any]:
    return {
        "id": str(note.id),
        "customer_id": str(note.customer_id),
        "author_email": note.author_email,
        "note_type": note.note_type,
        "content": note.content,
        "pinned": note.pinned,
        "created_at": _safe_iso(note.created_at),
        "updated_at": _safe_iso(note.updated_at),
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
        "created_at": _safe_iso(relationship.created_at),
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
        "created_at": _safe_iso(complaint.created_at),
        "resolved_at": _safe_iso(complaint.resolved_at),
    }


def serialize_customer_message(message: UnifiedMessage) -> dict[str, Any]:
    raw_payload = message.raw_payload if isinstance(message.raw_payload, dict) else {}
    return {
        "id": str(message.id),
        "customer_id": str(message.customer_id) if message.customer_id else None,
        "channel": message.channel,
        "direction": message.direction,
        "status": message.status,
        "sender_id": message.sender_id,
        "sender_name": message.sender_name,
        "message_text": message.message_text,
        "complaint_id": str(raw_payload.get("complaint_id")) if raw_payload.get("complaint_id") else None,
        "timestamp": _safe_iso(message.timestamp or message.created_at),
        "created_at": _safe_iso(message.created_at),
    }


def serialize_customer_timeline_message(message: UnifiedMessage) -> dict[str, Any]:
    serialized = serialize_customer_message(message)
    channel_str = message.channel or "Unknown"
    return {
        "id": f"message:{serialized['id']}",
        "type": "message",
        "title": f"{channel_str.title()} message",
        "body": serialized["message_text"] or "No message content available",
        "channel": message.channel,
        "direction": message.direction,
        "status": message.status,
        "sort_at": serialized["timestamp"],
        "timestamp": serialized["timestamp"],
        "data": serialized,
    }


def serialize_customer_timeline_ticket(complaint: Complaint) -> dict[str, Any]:
    serialized = serialize_customer_ticket(complaint)
    return {
        "id": f"ticket:{serialized['id']}",
        "type": "ticket",
        "title": serialized["ticket_number"],
        "body": serialized["summary"] or "Ticket created",
        "channel": serialized["source"],
        "status": serialized["resolution_status"],
        "sort_at": serialized["created_at"],
        "timestamp": serialized["created_at"],
        "data": serialized,
    }


def serialize_customer_timeline_note(note: CustomerNote) -> dict[str, Any]:
    serialized = serialize_customer_note(note)
    return {
        "id": f"action:{serialized['id']}",
        "type": "action",
        "title": serialized["note_type"].replace("_", " ").title(),
        "body": serialized["content"],
        "status": "pinned" if serialized["pinned"] else "noted",
        "sort_at": serialized["created_at"],
        "timestamp": serialized["created_at"],
        "data": serialized,
    }


def resolve_customer(
    db: Session,
    client_id,
    email: str | None,
    name: str | None = None,
    *,
    phone: str | None = None,
    company: str | None = None,
    commit: bool = False,
) -> Customer | None:
    return CustomerProfileService(db).resolve_customer(
        client_id=client_id,
        email=email,
        name=name,
        phone=phone,
        company=company,
        commit=commit,
    )


def compute_customer_sentiment(db: Session, customer_id) -> dict[str, Any]:
    return CustomerProfileService(db).compute_customer_sentiment(customer_id)


def compute_churn_risk(db: Session, customer: Customer | str | uuid.UUID) -> dict[str, Any]:
    return CustomerProfileService(db).compute_churn_risk(customer)
