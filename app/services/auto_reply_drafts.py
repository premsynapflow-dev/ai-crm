from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Any, Sequence

import httpx
from sqlalchemy import and_, desc
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import AutomationSetting, Client, Complaint, Customer, ReplyDraft, ReplyTemplate, UnifiedMessage
from app.intelligence.prompt_builder import (
    DEFAULT_CONFIG,
    build_auto_reply_generation_prompt,
    get_prompt_config_for_client,
)
from app.services.ai import _extract_json_payload, get_gemini_client
from app.services.conversation_threads import get_thread_messages
from app.services.event_logger import log_event

PROMPT_VERSION = "auto_reply_with_hitl_v1"
MAX_RECENT_MESSAGES = 5
MAX_CUSTOMER_HISTORY = 3
HIGH_PRIORITY_THRESHOLD = 4
HIGH_CHURN_RISK_THRESHOLD = 50.0
LEGAL_ESCALATION_PATTERN = re.compile(
    r"\b(legal|lawyer|attorney|court|lawsuit|sue|ombudsman|regulator|compliance|escalat(?:e|ion))\b",
    re.IGNORECASE,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _clamp_confidence(value: Any, fallback: float = 0.55) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = fallback
    return max(0.0, min(1.0, round(parsed, 4)))


@dataclass
class AutoReplyDraftResult:
    subject: str
    body: str
    confidence_score: float
    generation_metadata: dict[str, Any]


@dataclass
class DraftPreparationResult:
    draft: ReplyDraft | None
    generation: AutoReplyDraftResult | None
    skip_reason: str | None = None


class AutoReplyDraftService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    def prepare_draft(
        self,
        ticket: Complaint,
        *,
        client: Client | None = None,
        custom_config: dict[str, Any] | None = None,
        allow_disabled: bool = False,
        commit: bool = True,
    ) -> DraftPreparationResult:
        customer = self._resolve_customer(ticket)
        recent_messages = self._load_recent_messages(ticket)
        eligible, reason = self._is_eligible_for_generation(
            ticket,
            customer=customer,
            recent_messages=recent_messages,
            allow_disabled=allow_disabled,
        )
        if not eligible:
            if reason in {"high_priority", "legal_or_escalation", "high_churn_risk"}:
                ticket.ai_reply_status = "agent_review"
            log_event(
                self.db,
                ticket.client_id,
                "reply_draft_skipped",
                {
                    "ticket_id": ticket.ticket_id,
                    "complaint_id": str(ticket.id),
                    "reason": reason,
                },
            )
            if commit:
                self.db.commit()
            else:
                self.db.flush()
            return DraftPreparationResult(draft=None, generation=None, skip_reason=reason)

        generation = self.generate_auto_reply(
            ticket,
            customer,
            recent_messages,
            client=client,
            custom_config=custom_config,
        )
        draft = self._store_draft(ticket, customer, generation, commit=commit)
        return DraftPreparationResult(draft=draft, generation=generation)

    async def prepare_draft_async(
        self,
        ticket: Complaint,
        *,
        client: Client | None = None,
        custom_config: dict[str, Any] | None = None,
        allow_disabled: bool = False,
        commit: bool = True,
    ) -> DraftPreparationResult:
        customer = self._resolve_customer(ticket)
        recent_messages = self._load_recent_messages(ticket)
        eligible, reason = self._is_eligible_for_generation(
            ticket,
            customer=customer,
            recent_messages=recent_messages,
            allow_disabled=allow_disabled,
        )
        if not eligible:
            if reason in {"high_priority", "legal_or_escalation", "high_churn_risk"}:
                ticket.ai_reply_status = "agent_review"
            log_event(
                self.db,
                ticket.client_id,
                "reply_draft_skipped",
                {
                    "ticket_id": ticket.ticket_id,
                    "complaint_id": str(ticket.id),
                    "reason": reason,
                },
            )
            if commit:
                self.db.commit()
            else:
                self.db.flush()
            return DraftPreparationResult(draft=None, generation=None, skip_reason=reason)

        generation = await self.generate_auto_reply_async(
            ticket,
            customer,
            recent_messages,
            client=client,
            custom_config=custom_config,
        )
        draft = self._store_draft(ticket, customer, generation, commit=commit)
        return DraftPreparationResult(draft=draft, generation=generation)

    def generate_auto_reply(
        self,
        ticket: Complaint,
        customer: Customer | None,
        recent_messages: Sequence[UnifiedMessage | dict[str, Any]],
        *,
        client: Client | None = None,
        custom_config: dict[str, Any] | None = None,
    ) -> AutoReplyDraftResult:
        template = self._select_template(ticket)
        if template is not None:
            template.usage_count = int(template.usage_count or 0) + 1
            subject = self._default_subject(ticket, recent_messages)
            body = self._fill_template(template, ticket)
            return AutoReplyDraftResult(
                subject=subject,
                body=body,
                confidence_score=0.9,
                generation_metadata={
                    "strategy": "template_draft",
                    "template_id": str(template.id),
                    "model_confidence": 0.9,
                    "prompt_version": PROMPT_VERSION,
                    "context_messages": len(recent_messages),
                },
            )

        context = self._build_prompt_context(ticket, customer, recent_messages)
        prompt = build_auto_reply_generation_prompt(
            context,
            self._reply_config(client=client, custom_config=custom_config),
        )
        api_key = (self.settings.gemini_api_key or "").strip()
        if not api_key:
            return self._fallback_generation(ticket, customer, recent_messages)

        try:
            response = get_gemini_client().generate_content(
                prompt,
                model="gemini-2.5-flash-lite",
                max_output_tokens=700,
                temperature=0.25,
            )
            return self._normalize_generation_payload(
                response.text,
                ticket,
                customer,
                recent_messages,
                strategy="gemini_draft",
                context_messages=len(recent_messages),
            )
        except Exception:
            return self._fallback_generation(ticket, customer, recent_messages)

    async def generate_auto_reply_async(
        self,
        ticket: Complaint,
        customer: Customer | None,
        recent_messages: Sequence[UnifiedMessage | dict[str, Any]],
        *,
        client: Client | None = None,
        custom_config: dict[str, Any] | None = None,
    ) -> AutoReplyDraftResult:
        template = self._select_template(ticket)
        if template is not None:
            template.usage_count = int(template.usage_count or 0) + 1
            subject = self._default_subject(ticket, recent_messages)
            body = self._fill_template(template, ticket)
            return AutoReplyDraftResult(
                subject=subject,
                body=body,
                confidence_score=0.9,
                generation_metadata={
                    "strategy": "template_draft",
                    "template_id": str(template.id),
                    "model_confidence": 0.9,
                    "prompt_version": PROMPT_VERSION,
                    "context_messages": len(recent_messages),
                },
            )

        context = self._build_prompt_context(ticket, customer, recent_messages)
        prompt = build_auto_reply_generation_prompt(
            context,
            self._reply_config(client=client, custom_config=custom_config),
        )
        api_key = (self.settings.gemini_api_key or "").strip()
        if not api_key:
            return self._fallback_generation(ticket, customer, recent_messages)

        try:
            async with httpx.AsyncClient(timeout=20.0) as client_session:
                response = await client_session.post(
                    "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent",
                    params={"key": api_key},
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {
                            "temperature": 0.25,
                            "maxOutputTokens": 700,
                        },
                    },
                )
                response.raise_for_status()
                payload = response.json()
                raw_text = (
                    payload.get("candidates", [{}])[0]
                    .get("content", {})
                    .get("parts", [{}])[0]
                    .get("text", "")
                )
            return self._normalize_generation_payload(
                raw_text,
                ticket,
                customer,
                recent_messages,
                strategy="gemini_draft",
                context_messages=len(recent_messages),
            )
        except Exception:
            return self._fallback_generation(ticket, customer, recent_messages)

    def _is_eligible_for_generation(
        self,
        ticket: Complaint,
        *,
        customer: Customer | None,
        recent_messages: Sequence[UnifiedMessage | dict[str, Any]],
        allow_disabled: bool,
    ) -> tuple[bool, str | None]:
        if str(ticket.category or "").strip().lower() == "spam":
            return False, "spam"

        if not allow_disabled and not self._is_auto_reply_enabled(ticket):
            return False, "auto_reply_disabled"

        if int(ticket.priority or 0) >= HIGH_PRIORITY_THRESHOLD:
            return False, "high_priority"

        if self._has_legal_or_escalation_flag(ticket, recent_messages):
            return False, "legal_or_escalation"

        if customer is not None and float(customer.churn_risk_score or 0.0) >= HIGH_CHURN_RISK_THRESHOLD:
            return False, "high_churn_risk"

        return True, None

    def _is_auto_reply_enabled(self, ticket: Complaint) -> bool:
        setting = (
            self.db.query(AutomationSetting)
            .filter(
                AutomationSetting.client_id == ticket.client_id,
                AutomationSetting.channel == (ticket.source or "api"),
            )
            .first()
        )
        return bool(setting and setting.auto_reply_enabled)

    def _has_legal_or_escalation_flag(
        self,
        ticket: Complaint,
        recent_messages: Sequence[UnifiedMessage | dict[str, Any]],
    ) -> bool:
        if (ticket.status or "").strip().upper() == "ESCALATE_HIGH":
            return True
        if int(ticket.escalation_level or 0) > 0:
            return True
        if ticket.escalated_to or ticket.rbi_category_code:
            return True

        text_candidates = [_normalize_text(ticket.summary), _normalize_text(ticket.category)]
        for message in recent_messages:
            if isinstance(message, UnifiedMessage):
                text_candidates.append(_normalize_text(message.message_text))
            else:
                text_candidates.append(_normalize_text(message.get("message_text")))
        return any(LEGAL_ESCALATION_PATTERN.search(text) for text in text_candidates if text)

    def _resolve_customer(self, ticket: Complaint) -> Customer | None:
        if ticket.customer is not None:
            return ticket.customer
        if ticket.customer_id:
            return (
                self.db.query(Customer)
                .filter(
                    Customer.id == ticket.customer_id,
                    Customer.client_id == ticket.client_id,
                )
                .first()
            )
        return None

    def _load_recent_messages(self, ticket: Complaint) -> list[UnifiedMessage]:
        return list(get_thread_messages(self.db, ticket)[-MAX_RECENT_MESSAGES:])

    def _store_draft(
        self,
        ticket: Complaint,
        customer: Customer | None,
        generation: AutoReplyDraftResult,
        *,
        commit: bool,
    ) -> ReplyDraft:
        draft = (
            self.db.query(ReplyDraft)
            .filter(
                ReplyDraft.complaint_id == ticket.id,
                ReplyDraft.client_id == ticket.client_id,
            )
            .first()
        )
        if draft is None:
            draft = ReplyDraft(
                complaint_id=ticket.id,
                client_id=ticket.client_id,
                ticket_id=ticket.ticket_id,
            )
            self.db.add(draft)

        draft.ticket_id = ticket.ticket_id
        draft.customer_id = customer.id if customer is not None else None
        draft.subject = generation.subject
        draft.body = generation.body
        draft.status = "pending"
        draft.confidence_score = generation.confidence_score
        draft.prompt_version = PROMPT_VERSION
        draft.generation_metadata = generation.generation_metadata
        draft.approved_at = None
        draft.rejected_at = None
        draft.sent_at = None

        if commit:
            self.db.commit()
            self.db.refresh(draft)
        else:
            self.db.flush()
        return draft

    def _select_template(self, ticket: Complaint) -> ReplyTemplate | None:
        return (
            self.db.query(ReplyTemplate)
            .filter(
                and_(
                    ReplyTemplate.client_id == ticket.client_id,
                    ReplyTemplate.enabled == True,
                    ReplyTemplate.category.in_([ticket.category, "general", "apology"]),
                )
            )
            .order_by(desc(ReplyTemplate.usage_count))
            .first()
        )

    def _build_prompt_context(
        self,
        ticket: Complaint,
        customer: Customer | None,
        recent_messages: Sequence[UnifiedMessage | dict[str, Any]],
    ) -> dict[str, Any]:
        customer_history = self._customer_history_lines(ticket, customer)
        return {
            "ticket_number": ticket.ticket_number or ticket.ticket_id,
            "category": ticket.category or "general",
            "sentiment_label": self._sentiment_label(ticket.sentiment),
            "sentiment_score": round(float(ticket.sentiment or 0.0), 3),
            "priority": ticket.priority,
            "source": ticket.source or "api",
            "summary": _normalize_text(ticket.summary) or "No complaint summary provided",
            "customer_name": customer.full_name if customer is not None else None,
            "company_name": customer.company_name if customer is not None else None,
            "total_tickets": customer.total_tickets if customer is not None else None,
            "avg_satisfaction_score": customer.avg_satisfaction_score if customer is not None else None,
            "churn_risk_score": customer.churn_risk_score if customer is not None else None,
            "customer_history": customer_history,
            "recent_messages": self._recent_message_lines(recent_messages),
        }

    def _customer_history_lines(self, ticket: Complaint, customer: Customer | None) -> list[str]:
        if customer is None:
            return ["- No linked customer profile available."]

        recent_tickets = (
            self.db.query(Complaint)
            .filter(
                Complaint.client_id == ticket.client_id,
                Complaint.customer_id == customer.id,
                Complaint.id != ticket.id,
            )
            .order_by(Complaint.created_at.desc())
            .limit(MAX_CUSTOMER_HISTORY)
            .all()
        )
        if not recent_tickets:
            return ["- No recent customer history available."]

        lines: list[str] = []
        for row in recent_tickets:
            lines.append(
                f"- {row.ticket_number or row.ticket_id}: {row.category or 'general'} / "
                f"{row.resolution_status or 'open'} / {_normalize_text(row.summary) or 'No summary'}"
            )
        return lines

    def _recent_message_lines(self, recent_messages: Sequence[UnifiedMessage | dict[str, Any]]) -> list[str]:
        lines: list[str] = []
        for message in recent_messages[-MAX_RECENT_MESSAGES:]:
            if isinstance(message, UnifiedMessage):
                direction = (message.direction or "unknown").strip().lower()
                sender_name = _normalize_text(message.sender_name or message.sender_id) or ("Support" if direction == "outbound" else "Customer")
                timestamp = message.timestamp.isoformat() if message.timestamp else "unknown time"
                body = _normalize_text(message.message_text) or "(no message body)"
            else:
                direction = _normalize_text(message.get("direction")).lower() or "unknown"
                sender_name = _normalize_text(message.get("sender_name") or message.get("sender_id")) or (
                    "Support" if direction == "outbound" else "Customer"
                )
                timestamp = _normalize_text(message.get("timestamp")) or "unknown time"
                body = _normalize_text(message.get("message_text")) or "(no message body)"
            role = "Support" if direction == "outbound" else "Customer"
            lines.append(f"- {role} ({sender_name}, {timestamp}): {body[:500]}")
        return lines or ["- No previous conversation available."]

    def _normalize_generation_payload(
        self,
        raw_text: str,
        ticket: Complaint,
        customer: Customer | None,
        recent_messages: Sequence[UnifiedMessage | dict[str, Any]],
        *,
        strategy: str,
        context_messages: int,
    ) -> AutoReplyDraftResult:
        fallback = self._fallback_generation(ticket, customer, recent_messages)
        try:
            payload = _extract_json_payload(raw_text)
        except Exception:
            return fallback

        subject = _normalize_text(payload.get("subject")) or fallback.subject
        body = str(payload.get("body") or "").strip() or fallback.body
        confidence_score = _clamp_confidence(payload.get("confidence_score"), fallback.confidence_score)
        return AutoReplyDraftResult(
            subject=subject[:255],
            body=body,
            confidence_score=confidence_score,
            generation_metadata={
                "strategy": strategy,
                "model_confidence": confidence_score,
                "prompt_version": PROMPT_VERSION,
                "context_messages": context_messages,
            },
        )

    def _fallback_generation(
        self,
        ticket: Complaint,
        customer: Customer | None,
        recent_messages: Sequence[UnifiedMessage | dict[str, Any]],
    ) -> AutoReplyDraftResult:
        customer_name = _normalize_text(customer.full_name if customer is not None else None) or "there"
        summary = _normalize_text(ticket.summary) or "your request"
        latest_customer_message = ""
        for message in reversed(list(recent_messages)):
            direction = message.direction if isinstance(message, UnifiedMessage) else message.get("direction")
            if str(direction or "").strip().lower() != "outbound":
                latest_customer_message = _normalize_text(
                    message.message_text if isinstance(message, UnifiedMessage) else message.get("message_text")
                )
                if latest_customer_message:
                    break

        subject = self._default_subject(ticket, recent_messages)
        category_label = _normalize_text(ticket.category).replace("_", " ") or "support"
        body_lines = [
            f"Hi {customer_name},",
            (
                f"Thank you for reaching out about {summary.lower()}. "
                f"I understand how frustrating this {category_label.lower()} issue can be."
            ),
            (
                f"Our team is reviewing the details from ticket {ticket.ticket_number or ticket.ticket_id} "
                "and will follow up with the next steps shortly."
            ),
        ]
        if latest_customer_message:
            body_lines.append(
                f"For reference, we have noted your latest update: \"{latest_customer_message[:220]}\"."
            )
        body_lines.append("Best regards,\nSupport Team")
        return AutoReplyDraftResult(
            subject=subject,
            body="\n\n".join(body_lines).strip(),
            confidence_score=0.52 if recent_messages else 0.45,
            generation_metadata={
                "strategy": "contextual_fallback",
                "model_confidence": 0.45,
                "prompt_version": PROMPT_VERSION,
                "context_messages": len(recent_messages),
            },
        )

    def _default_subject(
        self,
        ticket: Complaint,
        recent_messages: Sequence[UnifiedMessage | dict[str, Any]],
    ) -> str:
        subject = self._subject_from_messages(recent_messages)
        if subject:
            return subject[:255]
        category = _normalize_text(ticket.category).replace("_", " ") or "support"
        return f"Re: Your {category.lower()} request"

    def _subject_from_messages(self, recent_messages: Sequence[UnifiedMessage | dict[str, Any]]) -> str | None:
        for message in reversed(list(recent_messages)):
            raw_payload = message.raw_payload if isinstance(message, UnifiedMessage) else message.get("raw_payload")
            if not isinstance(raw_payload, dict):
                continue
            headers = raw_payload.get("headers")
            if not isinstance(headers, dict):
                continue
            for key, value in headers.items():
                if str(key).lower() != "subject":
                    continue
                subject = _normalize_text(value)
                if subject:
                    return subject if subject.lower().startswith("re:") else f"Re: {subject}"
        return None

    def _fill_template(self, template: ReplyTemplate, ticket: Complaint) -> str:
        customer_name = ticket.customer_email or "Customer"
        if ticket.customer and ticket.customer.full_name:
            customer_name = ticket.customer.full_name
        return (
            template.template_body
            .replace("{customer_name}", customer_name)
            .replace("{ticket_number}", ticket.ticket_number or ticket.ticket_id or "")
            .replace("{summary}", ticket.summary or "")
            .replace("{category}", ticket.category or "general")
        )

    def _reply_config(self, *, client: Client | None, custom_config: dict[str, Any] | None) -> dict[str, Any]:
        return custom_config or (get_prompt_config_for_client(client) if client is not None else None) or DEFAULT_CONFIG

    @staticmethod
    def _sentiment_label(value: float | None) -> str:
        score = float(value or 0.0)
        if score <= -0.25:
            return "negative"
        if score >= 0.25:
            return "positive"
        return "neutral"


def generate_auto_reply(ticket, customer, recent_messages) -> dict[str, Any]:
    service = AutoReplyDraftService.__new__(AutoReplyDraftService)
    service.settings = get_settings()
    context = {
        "ticket_number": getattr(ticket, "ticket_number", None) or getattr(ticket, "ticket_id", None),
        "category": getattr(ticket, "category", None) or "general",
        "sentiment_label": service._sentiment_label(getattr(ticket, "sentiment", 0.0)),
        "sentiment_score": round(float(getattr(ticket, "sentiment", 0.0) or 0.0), 3),
        "priority": getattr(ticket, "priority", None),
        "source": getattr(ticket, "source", None) or "api",
        "summary": _normalize_text(getattr(ticket, "summary", None)) or "No complaint summary provided",
        "customer_name": getattr(customer, "full_name", None) if customer is not None else None,
        "company_name": getattr(customer, "company_name", None) if customer is not None else None,
        "total_tickets": getattr(customer, "total_tickets", None) if customer is not None else None,
        "avg_satisfaction_score": getattr(customer, "avg_satisfaction_score", None) if customer is not None else None,
        "churn_risk_score": getattr(customer, "churn_risk_score", None) if customer is not None else None,
        "customer_history": ["- No linked customer history available in standalone mode."],
        "recent_messages": service._recent_message_lines(recent_messages),
    }

    api_key = (service.settings.gemini_api_key or "").strip()
    if api_key:
        try:
            prompt = build_auto_reply_generation_prompt(context, DEFAULT_CONFIG)
            response = get_gemini_client().generate_content(
                prompt,
                model="gemini-2.5-flash-lite",
                max_output_tokens=700,
                temperature=0.25,
            )
            result = service._normalize_generation_payload(
                response.text,
                ticket,
                customer,
                recent_messages,
                strategy="gemini_draft",
                context_messages=len(recent_messages),
            )
        except Exception:
            result = service._fallback_generation(ticket, customer, recent_messages)
    else:
        result = service._fallback_generation(ticket, customer, recent_messages)

    return {
        "subject": result.subject,
        "body": result.body,
        "confidence_score": result.confidence_score,
    }
