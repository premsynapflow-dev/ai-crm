from datetime import datetime, timedelta, timezone
import uuid
from typing import Any, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.db.models import Complaint, Customer, CustomerEvent, CustomerInteraction, CustomerNote, CustomerRelationship, EventLog, UnifiedMessage
from app.intelligence.calibration import calibrate_churn_probability
from app.intelligence.constants import (
    RISK_LEVEL_HIGH,
    RISK_LEVEL_MEDIUM,
    RISK_MODEL_VERSION,
    SENTIMENT_NEGATIVE,
    SENTIMENT_STRONG_NEG,
    SENTIMENT_STREAK_NEG,
    SATISFACTION_LOW,
)
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
        customer.predicted_churn_probability = calibrate_churn_probability(churn["score"])
        customer.prediction_explanation = churn.get("breakdown")
        customer.risk_score_version = RISK_MODEL_VERSION
        customer.risk_score_computed_at = _utcnow()

        # Persist enhanced signal columns
        signals = churn.get("signals", {})
        customer.tenure_days = signals.get("tenure_days")
        customer.complaint_velocity_score = signals.get("complaint_velocity_ratio")
        customer.competitive_mention_count = int(signals.get("competitive_mention_count", 0))

        resolved_count = sum(1 for row in complaint_rows if row.resolution_status == "resolved")
        customer.lifetime_value = self._compute_lifetime_value(customer, resolved_count)

        # Set value source and revenue risk confidence (follows 5-tier priority)
        from app.intelligence.constants import (
            VALUE_SOURCE_ACTUAL, VALUE_SOURCE_CONTRACT,
            VALUE_SOURCE_MRR, VALUE_SOURCE_ESTIMATED, VALUE_SOURCE_UNKNOWN,
        )
        if customer.actual_customer_value and customer.actual_customer_value > 0:
            customer.customer_value_source = VALUE_SOURCE_ACTUAL
            customer.revenue_risk_confidence = "high"
        elif (customer.customer_lifetime_revenue and customer.customer_lifetime_revenue > 0):
            customer.customer_value_source = VALUE_SOURCE_ACTUAL
            customer.revenue_risk_confidence = "high"
        elif customer.annual_contract_value and customer.annual_contract_value > 0:
            customer.customer_value_source = VALUE_SOURCE_CONTRACT
            customer.revenue_risk_confidence = "medium"
        elif customer.monthly_recurring_value and customer.monthly_recurring_value > 0:
            customer.customer_value_source = VALUE_SOURCE_MRR
            customer.revenue_risk_confidence = "medium"
        elif customer.estimated_customer_value and customer.estimated_customer_value > 0:
            customer.customer_value_source = VALUE_SOURCE_ESTIMATED
            customer.revenue_risk_confidence = "medium"
        else:
            customer.customer_value_source = VALUE_SOURCE_UNKNOWN
            customer.revenue_risk_confidence = "low"

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
        recent_events = (
            self.db.query(CustomerEvent)
            .filter(
                CustomerEvent.client_id == customer.client_id,
                CustomerEvent.customer_id == customer.id,
            )
            .order_by(CustomerEvent.event_timestamp.desc(), CustomerEvent.created_at.desc())
            .limit(50)
            .all()
        )
        if not recent_events:
            recent_events = (
                self.db.query(EventLog)
                .filter(
                    EventLog.client_id == customer.client_id,
                    EventLog.customer_id == customer.id,
                )
                .order_by(EventLog.event_timestamp.desc(), EventLog.created_at.desc())
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
            recent_events=recent_events,
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
            "risk": churn,
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
        recent_events = (
            self.db.query(CustomerEvent)
            .filter(CustomerEvent.client_id == customer.client_id, CustomerEvent.customer_id == customer.id)
            .order_by(CustomerEvent.event_timestamp.desc(), CustomerEvent.created_at.desc())
            .limit(20)
            .all()
        )
        if not recent_events:
            recent_events = (
                self.db.query(EventLog)
                .filter(EventLog.client_id == customer.client_id, EventLog.customer_id == customer.id)
                .order_by(EventLog.event_timestamp.desc(), EventLog.created_at.desc())
                .limit(20)
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
                recent_events=recent_events,
            ),
            "risk": churn,
            "insights": self._build_insights(customer, recent_tickets, sentiment, churn),
            "satisfaction_trend": self._build_satisfaction_trend(customer.id),
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
        dimensions = self._aggregate_emotion_dimensions(resolved_customer.id)
        return {
            "score": score,
            "label": _sentiment_label(score),
            "sample_size": len(scores),
            "emotion_dimensions": dimensions,
            "trend": self._sentiment_trend(resolved_customer.id),
        }

    def compute_churn_risk(self, customer: Customer | str | uuid.UUID) -> dict[str, Any]:
        resolved_customer = customer if isinstance(customer, Customer) else self._get_customer_or_master(customer)
        indicators = self._calculate_churn_indicators(resolved_customer)
        industry = getattr(resolved_customer, "industry_profile", None)

        # Load feedback-calibrated group cap multipliers (falls back to all-1.0 gracefully)
        try:
            from app.services.feedback_loop import get_group_cap_multipliers
            multipliers = get_group_cap_multipliers(self.db, str(resolved_customer.client_id))
        except Exception:
            multipliers = None

        score, breakdown = self._weighted_churn_score(indicators, industry=industry, group_multipliers=multipliers)
        if score >= RISK_LEVEL_HIGH:
            level = "high"
        elif score >= RISK_LEVEL_MEDIUM:
            level = "medium"
        else:
            level = "low"

        return {
            "level": level,
            "score": float(score),
            "signals": indicators,
            "explanation": self._churn_explanation(indicators),
            "breakdown": breakdown,
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
        recent_events: list[CustomerEvent | EventLog] | None = None,
    ) -> list[dict[str, Any]]:
        items = [serialize_customer_timeline_message(message) for message in recent_messages]
        items.extend(serialize_customer_timeline_ticket(ticket) for ticket in recent_tickets)
        items.extend(serialize_customer_timeline_note(note) for note in notes)
        items.extend(serialize_customer_timeline_event(event) for event in (recent_events or []))
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
        if churn.get("explanation"):
            insights.extend(churn["explanation"][:2])
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
                Complaint.sentiment < SENTIMENT_NEGATIVE,
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

        # Complaint velocity: compare recent 30d vs prior 30d
        sixty_days_ago = _utcnow() - timedelta(days=60)
        prior_tickets = int(
            self.db.query(func.count(Complaint.id))
            .filter(
                Complaint.customer_id == customer.id,
                Complaint.created_at >= sixty_days_ago,
                Complaint.created_at < thirty_days_ago,
            )
            .scalar()
            or 0
        )
        velocity_ratio = round(float(recent_tickets) / max(prior_tickets, 1), 2) if recent_tickets else None

        # Tenure: days since first interaction
        tenure_days = None
        first_seen = _safe_timestamp(customer.first_interaction_at)
        if first_seen:
            tenure_days = max(0, (_utcnow() - first_seen).days)

        # Competitive mentions: explicit switching/cancellation language in recent messages
        competitive_mentions = self._count_competitive_mentions(customer.id)

        return {
            "recent_ticket_volume": int(recent_tickets),
            "recent_negative_tickets": int(recent_negative_tickets),
            "negative_sentiment_streak": bool(recent_message_scores[:3]) and all(score <= SENTIMENT_STREAK_NEG for score in recent_message_scores[:3]),
            "unresolved_tickets": int(unresolved_tickets),
            "total_escalations": int(total_escalations),
            "days_since_last_interaction": days_since_last,
            "low_satisfaction": bool(customer.avg_satisfaction_score is not None and customer.avg_satisfaction_score < SATISFACTION_LOW),
            "avg_recent_sentiment": round(sum(recent_message_scores) / len(recent_message_scores), 3) if recent_message_scores else None,
            "sentiment_drop_detected": self._sentiment_trend(customer.id).get("direction") == "declining",
            "refund_or_payment_events": self._count_recent_events(
                customer,
                ["refund_requested", "refund_processed", "payment_failed", "plan_downgraded"],
                days=90,
            ),
            "complaint_velocity_ratio": velocity_ratio,
            "tenure_days": tenure_days,
            "competitive_mention_count": competitive_mentions,
        }

    def _weighted_churn_score(
        self,
        indicators: dict[str, Any],
        industry: str | None = None,
        group_multipliers: dict[str, float] | None = None,
    ) -> tuple[float, dict[str, Any]]:
        """Grouped signal architecture — prevents double-counting within each category.

        Each of the 5 groups has a hard cap.  Signals within a group are additive
        up to that cap only.  This ensures that, e.g., having 10 escalations doesn't
        push Escalation Risk above 20 points while also inflating other groups.

        group_multipliers: from feedback_loop.get_group_cap_multipliers().  Adjusts
        the effective cap per group based on observed outcome accuracy.  Defaults to
        all-1.0 (no adjustment) when None.

        Returns (score, breakdown_dict) where breakdown_dict is suitable for storage
        in customer.prediction_explanation.
        """
        from app.intelligence.constants import (
            RISK_GROUP_CAPS, RISK_LOYALTY_MAX_DISCOUNT,
            INACTIVITY_EXEMPT_INDUSTRIES, RISK_MODEL_VERSION,
        )

        m = group_multipliers or {k: 1.0 for k in RISK_GROUP_CAPS}

        # ── Volume Risk (max 20 × multiplier) ───────────────────────────────
        vol = 0.0
        velocity_ratio = indicators.get("complaint_velocity_ratio")
        if velocity_ratio is not None:
            if velocity_ratio > 2.0:
                vol += 12.0
            elif velocity_ratio > 1.5:
                vol += 7.0
        vol += min(float(indicators["recent_ticket_volume"]) * 3.0, 8.0)
        volume_risk = min(vol, RISK_GROUP_CAPS["volume"] * m.get("volume", 1.0))

        # ── Sentiment Risk (max 25) ──────────────────────────────────────────
        sent = 0.0
        if indicators["negative_sentiment_streak"]:
            sent += 12.0
        if indicators["sentiment_drop_detected"]:
            sent += 9.0
        avg_sentiment = indicators.get("avg_recent_sentiment")
        if avg_sentiment is not None and avg_sentiment < SENTIMENT_STRONG_NEG:
            sent += 8.0
        if indicators["low_satisfaction"]:
            sent += 6.0
        sentiment_risk = min(sent, RISK_GROUP_CAPS["sentiment"] * m.get("sentiment", 1.0))

        # ── Escalation Risk (max 20) ─────────────────────────────────────────
        esc = 0.0
        # active escalation signal (check via indicators proxy: total > 0 recently)
        # We use total_escalations as a stand-in since active status isn't in indicators
        if indicators["total_escalations"] > 0:
            esc += 10.0
        esc += min(float(indicators["total_escalations"]) * 4.0, 15.0)
        escalation_risk = min(esc, RISK_GROUP_CAPS["escalation"] * m.get("escalation", 1.0))

        # ── Resolution Risk (max 20) ─────────────────────────────────────────
        res = 0.0
        res += min(float(indicators["unresolved_tickets"]) * 5.0, 15.0)
        res += min(float(indicators["recent_negative_tickets"]) * 3.0, 9.0)
        resolution_risk = min(res, RISK_GROUP_CAPS["resolution"] * m.get("resolution", 1.0))

        # ── Behavioral Risk (max 25) ─────────────────────────────────────────
        beh = 0.0
        beh += min(float(indicators["refund_or_payment_events"]) * 6.0, 15.0)
        beh += min(float(indicators.get("competitive_mention_count", 0)) * 8.0, 16.0)
        days_since_last = indicators.get("days_since_last_interaction")
        inactivity_exempt = (industry or "").strip() in INACTIVITY_EXEMPT_INDUSTRIES
        if days_since_last is not None and not inactivity_exempt:
            if days_since_last > 30:
                beh += 8.0
            elif days_since_last > 14:
                beh += 4.0
        behavioral_risk = min(beh, RISK_GROUP_CAPS["behavioral"] * m.get("behavioral", 1.0))

        # ── Loyalty Discount (subtract, capped) ──────────────────────────────
        loyalty_discount = 0.0
        tenure_days = indicators.get("tenure_days")
        if tenure_days is not None:
            if tenure_days > 365:
                loyalty_discount = 10.0
            elif tenure_days > 90:
                loyalty_discount = 5.0
        loyalty_discount = min(loyalty_discount, RISK_LOYALTY_MAX_DISCOUNT)

        raw = volume_risk + sentiment_risk + escalation_risk + resolution_risk + behavioral_risk
        score = min(100.0, max(0.0, raw - loyalty_discount))

        # Human-readable top factors (ordered by contribution)
        factor_scores = {
            "Negative sentiment": sentiment_risk,
            "Unresolved tickets": resolution_risk,
            "Complaint volume spike": volume_risk,
            "Escalation history": escalation_risk,
            "Behavioral signals": behavioral_risk,
        }
        top_factors = [k for k, v in sorted(factor_scores.items(), key=lambda x: x[1], reverse=True) if v > 0]

        breakdown = {
            "volume_risk": round(volume_risk, 1),
            "sentiment_risk": round(sentiment_risk, 1),
            "escalation_risk": round(escalation_risk, 1),
            "resolution_risk": round(resolution_risk, 1),
            "behavioral_risk": round(behavioral_risk, 1),
            "loyalty_discount": round(loyalty_discount, 1),
            "total_score": round(score, 1),
            "top_factors": top_factors[:3],
            "risk_score_version": RISK_MODEL_VERSION,
        }

        return round(score, 2), breakdown

    def _churn_explanation(self, indicators: dict[str, Any]) -> list[str]:
        explanation: list[str] = []
        if indicators.get("competitive_mention_count", 0) > 0:
            explanation.append("Customer mentioned switching or cancelling")
        if indicators["unresolved_tickets"]:
            explanation.append(f"{indicators['unresolved_tickets']} unresolved ticket(s)")
        if indicators["recent_negative_tickets"]:
            explanation.append(f"{indicators['recent_negative_tickets']} recent negative ticket(s)")
        velocity_ratio = indicators.get("complaint_velocity_ratio")
        if velocity_ratio is not None and velocity_ratio > 1.5:
            explanation.append(f"Complaint volume spiked {round(velocity_ratio, 1)}× vs prior period")
        if indicators["negative_sentiment_streak"]:
            explanation.append("Negative sentiment streak")
        if indicators["sentiment_drop_detected"]:
            explanation.append("Sentiment trend is declining")
        if indicators["total_escalations"]:
            explanation.append(f"{indicators['total_escalations']} escalation(s)")
        if indicators["refund_or_payment_events"]:
            explanation.append("Refund/payment risk event detected")
        if indicators["low_satisfaction"]:
            explanation.append("Low satisfaction score")
        days_since_last = indicators.get("days_since_last_interaction")
        if days_since_last is not None and days_since_last > 14:
            explanation.append(f"No recent interaction for {days_since_last} days")
        return explanation[:6]

    def _sentiment_trend(self, customer_id) -> dict[str, Any]:
        messages = (
            self.db.query(UnifiedMessage)
            .filter(UnifiedMessage.customer_id == customer_id, UnifiedMessage.direction == "inbound")
            .order_by(UnifiedMessage.timestamp.desc(), UnifiedMessage.created_at.desc())
            .limit(10)
            .all()
        )
        scores = [score for score in (self._message_sentiment_score(message) for message in messages) if score is not None]
        if len(scores) < 4:
            return {"direction": "stable", "delta": 0.0, "sample_size": len(scores)}
        recent = sum(scores[: len(scores) // 2]) / max(1, len(scores[: len(scores) // 2]))
        older = sum(scores[len(scores) // 2 :]) / max(1, len(scores[len(scores) // 2 :]))
        delta = round(recent - older, 3)
        if delta <= -0.2:
            direction = "declining"
        elif delta >= 0.2:
            direction = "improving"
        else:
            direction = "stable"
        return {"direction": direction, "delta": delta, "sample_size": len(scores)}

    def _aggregate_emotion_dimensions(self, customer_id) -> dict[str, float]:
        messages = (
            self.db.query(UnifiedMessage)
            .filter(UnifiedMessage.customer_id == customer_id)
            .order_by(UnifiedMessage.timestamp.desc(), UnifiedMessage.created_at.desc())
            .limit(20)
            .all()
        )
        totals: dict[str, list[float]] = {}
        for message in messages:
            raw_payload = message.raw_payload if isinstance(message.raw_payload, dict) else {}
            dimensions = raw_payload.get("emotion_dimensions") or {}
            if not isinstance(dimensions, dict):
                continue
            for key, value in dimensions.items():
                try:
                    totals.setdefault(str(key), []).append(float(value))
                except (TypeError, ValueError):
                    continue
        return {key: round(sum(values) / len(values), 3) for key, values in totals.items() if values}

    def _count_recent_events(self, customer: Customer, event_types: list[str], *, days: int) -> int:
        since = _utcnow() - timedelta(days=days)
        canonical_count = int(
            self.db.query(func.count(CustomerEvent.id))
            .filter(
                CustomerEvent.client_id == customer.client_id,
                CustomerEvent.customer_id == customer.id,
                CustomerEvent.event_type.in_(event_types),
                CustomerEvent.event_timestamp >= since,
            )
            .scalar()
            or 0
        )
        if canonical_count:
            return canonical_count
        return int(
            self.db.query(func.count(EventLog.id))
            .filter(
                EventLog.client_id == customer.client_id,
                EventLog.customer_id == customer.id,
                EventLog.event_type.in_(event_types),
                (EventLog.event_timestamp >= since) | (EventLog.created_at >= since),
            )
            .scalar()
            or 0
        )

    _COMPETITIVE_KEYWORDS = [
        "switching to", "moving to", "switch to", "move to",
        "cancel", "cancellation", "cancel my", "closing account", "close account",
        "better option", "competitor", "going with", "choosing another",
        "leaving you", "leaving your", "unsubscribe", "stop using",
    ]

    def _count_competitive_mentions(self, customer_id) -> int:
        since = _utcnow() - timedelta(days=90)
        messages = (
            self.db.query(UnifiedMessage)
            .filter(
                UnifiedMessage.customer_id == customer_id,
                UnifiedMessage.direction == "inbound",
                UnifiedMessage.created_at >= since,
            )
            .order_by(UnifiedMessage.created_at.desc())
            .limit(30)
            .all()
        )
        count = 0
        for msg in messages:
            content = (msg.content or "").lower()
            if any(kw in content for kw in self._COMPETITIVE_KEYWORDS):
                count += 1
        return count

    def _compute_lifetime_value(self, customer: Customer, resolved_count: int) -> float:
        """Return the best available customer value in INR.

        Priority order (highest trust first):
          1. actual_customer_value  — from Stripe / Razorpay integration
          2. customer_lifetime_revenue — historical actual revenue (manually imported)
          3. annual_contract_value  — contract value from CRM / manual entry
          4. monthly_recurring_value × 12 — annualised MRR
          5. estimated_customer_value — manual estimate
          6. 0.0 — no data; caller must show Risk Index, not a ₹ number

        NEVER computes value from ticket counts or SynapFlow plan pricing.
        """
        if customer.actual_customer_value and customer.actual_customer_value > 0:
            return float(customer.actual_customer_value)
        if customer.customer_lifetime_revenue and customer.customer_lifetime_revenue > 0:
            return float(customer.customer_lifetime_revenue)
        if customer.annual_contract_value and customer.annual_contract_value > 0:
            return float(customer.annual_contract_value)
        if customer.monthly_recurring_value and customer.monthly_recurring_value > 0:
            return float(customer.monthly_recurring_value) * 12
        if customer.estimated_customer_value and customer.estimated_customer_value > 0:
            return float(customer.estimated_customer_value)
        return 0.0

    def get_save_recommendations(self, customer: Customer) -> list[str]:
        churn = self.compute_churn_risk(customer)
        score = churn["score"]
        indicators = churn["signals"]
        recommendations: list[str] = []
        if score >= 75:
            recommendations.append("Offer a proactive discount or service credit to rebuild trust")
            recommendations.append("Schedule an executive callback within 48 hours")
        if indicators.get("unresolved_tickets", 0) > 0:
            recommendations.append(f"Resolve {indicators['unresolved_tickets']} open ticket(s) as top priority")
        if indicators.get("recent_negative_tickets", 0) >= 2:
            recommendations.append("Upgrade customer to priority support queue")
        if indicators.get("refund_or_payment_events", 0) > 0:
            recommendations.append("Review refund/billing history and offer goodwill credit")
        if not recommendations:
            recommendations.append("Send a proactive check-in message from a senior agent")
        return recommendations[:4]

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
        "predicted_churn_probability": customer.predicted_churn_probability,
        "lifetime_value": customer.lifetime_value,
        # Revenue intelligence
        "actual_customer_value": customer.actual_customer_value,
        "estimated_customer_value": customer.estimated_customer_value,
        "annual_contract_value": customer.annual_contract_value,
        "monthly_recurring_value": customer.monthly_recurring_value,
        "remaining_contract_value": customer.remaining_contract_value,
        "customer_lifetime_revenue": customer.customer_lifetime_revenue,
        "customer_value_source": customer.customer_value_source,
        "revenue_risk_confidence": customer.revenue_risk_confidence,
        # Industry
        "industry_profile": customer.industry_profile,
        # Model versioning
        "risk_score_version": customer.risk_score_version,
        "risk_score_computed_at": _safe_iso(customer.risk_score_computed_at),
        "prediction_explanation": customer.prediction_explanation,
        # Churn signals
        "tenure_days": customer.tenure_days,
        "complaint_velocity_score": customer.complaint_velocity_score,
        "competitive_mention_count": customer.competitive_mention_count,
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


def serialize_customer_timeline_event(event: CustomerEvent | EventLog) -> dict[str, Any]:
    is_canonical = isinstance(event, CustomerEvent)
    payload_source = event.metadata_json if is_canonical else event.payload
    payload = payload_source if isinstance(payload_source, dict) else {}
    timestamp = _safe_iso(event.event_timestamp or event.created_at)
    event_type = (event.event_type or "event").replace("_", " ").title()
    body = payload.get("summary") or payload.get("outcome") or payload.get("action_type") or event.event_type
    source_event_id = getattr(event, "source_event_id", None)
    public_id = source_event_id or event.id
    return {
        "id": f"event:{public_id}",
        "type": "event",
        "title": event_type,
        "body": str(body or "Customer event"),
        "channel": event.source,
        "status": payload.get("status") or payload.get("queue_status") or payload.get("outcome"),
        "sort_at": timestamp,
        "timestamp": timestamp,
        "data": {
            "id": str(event.id),
            "client_id": str(event.client_id) if event.client_id else None,
            "customer_id": str(event.customer_id) if event.customer_id else None,
            "complaint_id": str(event.complaint_id) if event.complaint_id else None,
            "conversation_id": str(event.conversation_id) if is_canonical and event.conversation_id else None,
            "message_id": str(event.message_id) if is_canonical and event.message_id else None,
            "workflow_execution_id": str(event.workflow_execution_id) if is_canonical and event.workflow_execution_id else None,
            "source_event_id": str(source_event_id) if source_event_id else None,
            "event_type": event.event_type,
            "source": event.source,
            "actor_type": event.actor_type,
            "actor_id": event.actor_id if is_canonical else payload.get("actor_id"),
            "sentiment_score": event.sentiment_score,
            "risk_delta": event.risk_delta,
            "payload": payload,
            "created_at": _safe_iso(event.created_at),
        },
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
