from datetime import datetime, timedelta, timezone
import uuid
from typing import Any, Optional

from sqlalchemy import and_, desc
from sqlalchemy.orm import Session

from app.db.models import AIReplyQueue, AutomationSetting, Client, Complaint, ReplyFeedback, ReplyTemplate
from app.replies.send_reply import send_complaint_reply
from app.services.customer_history import get_customer_memory
from app.services.reply_confidence_scorer import ReplyConfidenceScorer


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class HardenedAutoReplyService:
    def __init__(self, db: Session):
        self.db = db
        self.confidence_scorer = ReplyConfidenceScorer()

    def generate_and_queue_reply(
        self,
        ticket: Complaint,
        force_human_review: bool = False,
        commit: bool = True,
    ) -> AIReplyQueue:
        reply_text, generation_meta = self._generate_reply(ticket)
        return self._store_queue_decision(ticket, reply_text, generation_meta, force_human_review, commit)

    async def generate_and_queue_reply_async(
        self,
        ticket: Complaint,
        force_human_review: bool = False,
        custom_config: dict[str, Any] | None = None,
        commit: bool = True,
    ) -> AIReplyQueue:
        reply_text, generation_meta = await self._generate_reply_async(ticket, custom_config=custom_config)
        return self._store_queue_decision(ticket, reply_text, generation_meta, force_human_review, commit)

    def _store_queue_decision(
        self,
        ticket: Complaint,
        reply_text: str,
        generation_meta: dict[str, Any],
        force_human_review: bool,
        commit: bool,
    ) -> AIReplyQueue:
        scoring_result = self.confidence_scorer.score_reply(
            reply_text=reply_text,
            ticket_summary=ticket.summary or "",
            generation_metadata=generation_meta,
        )

        queue_entry = (
            self.db.query(AIReplyQueue)
            .filter(AIReplyQueue.complaint_id == ticket.id)
            .first()
        )
        if queue_entry is None:
            queue_entry = AIReplyQueue(
                complaint_id=ticket.id,
                client_id=ticket.client_id,
            )
            self.db.add(queue_entry)

        queue_entry.generated_reply = reply_text
        queue_entry.confidence_score = scoring_result["confidence_score"]
        queue_entry.generation_strategy = generation_meta.get("strategy", "gemini")
        queue_entry.generation_metadata = generation_meta
        queue_entry.hallucination_check_passed = scoring_result["hallucination_check_passed"]
        queue_entry.toxicity_score = scoring_result["toxicity_score"]
        queue_entry.factual_consistency_score = scoring_result["factual_consistency_score"]
        queue_entry.expires_at = _utcnow() + timedelta(hours=24)

        ticket.ai_reply = reply_text
        ticket.ai_reply_confidence = scoring_result["confidence_score"]

        automation_setting = (
            self.db.query(AutomationSetting)
            .filter(
                AutomationSetting.client_id == ticket.client_id,
                AutomationSetting.channel == (ticket.source or "api"),
            )
            .first()
        )
        auto_reply_enabled = bool(automation_setting and automation_setting.auto_reply_enabled)
        confidence_threshold = float(automation_setting.confidence_threshold) if automation_setting else 0.8

        recommendation = "human_review" if force_human_review else scoring_result["recommendation"]
        if not auto_reply_enabled:
            recommendation = "human_review"
        elif scoring_result["confidence_score"] < confidence_threshold:
            recommendation = "human_review"
        client = self.db.query(Client).filter(Client.id == ticket.client_id).first()

        if recommendation == "auto_approve":
            queue_entry.status = "approved"
            queue_entry.reviewed_by = "system"
            queue_entry.reviewed_at = _utcnow()
            send_result = self._send_reply(ticket, reply_text, client)
            if not send_result["sent"]:
                queue_entry.status = "pending"
                queue_entry.reviewed_by = None
                queue_entry.reviewed_at = None
        elif recommendation == "human_review":
            queue_entry.status = "pending"
            queue_entry.reviewed_by = None
            queue_entry.reviewed_at = None
            queue_entry.rejection_reason = None
            ticket.ai_reply_status = "pending"
        else:
            queue_entry.status = "rejected"
            queue_entry.reviewed_by = "system"
            queue_entry.reviewed_at = _utcnow()
            queue_entry.rejection_reason = ", ".join(scoring_result["warnings"])
            ticket.ai_reply_status = "agent_review"

        self._ensure_feedback_record(ticket.id, queue_entry.id)
        if commit:
            self.db.commit()
            self.db.refresh(queue_entry)
        else:
            self.db.flush()
        return queue_entry

    def approve_reply(
        self,
        queue_id: str,
        reviewer_email: str,
        edited_reply: Optional[str] = None,
        commit: bool = True,
    ) -> bool:
        queue_entry = self.db.query(AIReplyQueue).filter(AIReplyQueue.id == self._as_uuid(queue_id)).first()
        if not queue_entry or queue_entry.status != "pending":
            return False

        complaint = self.db.query(Complaint).filter(Complaint.id == queue_entry.complaint_id).first()
        if complaint is None:
            return False
        client = self.db.query(Client).filter(Client.id == complaint.client_id).first()

        reply_to_send = (edited_reply or queue_entry.generated_reply or "").strip()
        queue_entry.status = "edited" if edited_reply else "approved"
        queue_entry.reviewed_by = reviewer_email
        queue_entry.reviewed_at = _utcnow()
        queue_entry.edited_reply = edited_reply.strip() if edited_reply else None
        queue_entry.rejection_reason = None
        complaint.ai_reply = reply_to_send
        complaint.ai_reply_confidence = queue_entry.confidence_score
        self._send_reply(complaint, reply_to_send, client)

        if commit:
            self.db.commit()
        else:
            self.db.flush()
        return True

    def reject_reply(self, queue_id: str, reviewer_email: str, reason: str, commit: bool = True) -> bool:
        queue_entry = self.db.query(AIReplyQueue).filter(AIReplyQueue.id == self._as_uuid(queue_id)).first()
        if not queue_entry or queue_entry.status != "pending":
            return False

        complaint = self.db.query(Complaint).filter(Complaint.id == queue_entry.complaint_id).first()
        if complaint is None:
            return False

        queue_entry.status = "rejected"
        queue_entry.reviewed_by = reviewer_email
        queue_entry.reviewed_at = _utcnow()
        queue_entry.rejection_reason = reason.strip()
        complaint.ai_reply_status = "agent_review"

        if commit:
            self.db.commit()
        else:
            self.db.flush()
        return True

    def record_feedback(
        self,
        complaint: Complaint,
        *,
        customer_responded: bool | None = None,
        customer_response_sentiment: float | None = None,
        ticket_reopened: bool | None = None,
        escalated_after_reply: bool | None = None,
        satisfaction_score: int | None = None,
        time_to_customer_response_seconds: int | None = None,
        commit: bool = True,
    ) -> ReplyFeedback:
        queue_entry = self.db.query(AIReplyQueue).filter(AIReplyQueue.complaint_id == complaint.id).first()
        feedback = self._ensure_feedback_record(complaint.id, queue_entry.id if queue_entry else None)

        if customer_responded is not None:
            feedback.customer_responded = customer_responded
        if customer_response_sentiment is not None:
            feedback.customer_response_sentiment = customer_response_sentiment
        if ticket_reopened is not None:
            feedback.ticket_reopened = ticket_reopened
        if escalated_after_reply is not None:
            feedback.escalated_after_reply = escalated_after_reply
        if satisfaction_score is not None:
            feedback.satisfaction_score = satisfaction_score
        if time_to_customer_response_seconds is not None:
            feedback.time_to_customer_response_seconds = time_to_customer_response_seconds

        if commit:
            self.db.commit()
            self.db.refresh(feedback)
        else:
            self.db.flush()
        return feedback

    def _generate_reply(self, ticket: Complaint) -> tuple[str, dict[str, Any]]:
        template = (
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

        if template:
            template.usage_count = (template.usage_count or 0) + 1
            return (
                self._fill_template(template, ticket),
                {
                    "strategy": "template",
                    "template_id": str(template.id),
                    "model_confidence": 0.9,
                },
            )

        from app.intelligence.reply_engine import generate_ai_reply

        customer_history = get_customer_memory(
            self.db,
            ticket.customer_email,
            limit=5,
            client_id=ticket.client_id,
        )
        generated = generate_ai_reply(ticket, customer_history)
        return (
            generated["reply_text"],
            {
                "strategy": "gemini",
                "model_confidence": float(generated.get("confidence_score", 0.7) or 0.7),
            },
        )

    async def _generate_reply_async(
        self,
        ticket: Complaint,
        custom_config: dict[str, Any] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        template = (
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
        if template:
            template.usage_count = (template.usage_count or 0) + 1
            return (
                self._fill_template(template, ticket),
                {
                    "strategy": "template",
                    "template_id": str(template.id),
                    "model_confidence": 0.9,
                },
            )

        from app.intelligence.reply_engine import generate_ai_reply_async

        customer_history = get_customer_memory(
            self.db,
            ticket.customer_email,
            limit=5,
            client_id=ticket.client_id,
        )
        generated = await generate_ai_reply_async(ticket, customer_history, custom_config=custom_config)
        return (
            generated["reply_text"],
            {
                "strategy": "gemini",
                "model_confidence": float(generated.get("confidence_score", 0.7) or 0.7),
            },
        )

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

    def _send_reply(self, ticket: Complaint, reply_text: str, client: Client | None):
        return send_complaint_reply(
            db=self.db,
            complaint=ticket,
            client=client,
            reply_text=reply_text,
        )

    def _ensure_feedback_record(self, complaint_id, reply_queue_id) -> ReplyFeedback:
        feedback = self.db.query(ReplyFeedback).filter(ReplyFeedback.complaint_id == complaint_id).first()
        if feedback is None:
            feedback = ReplyFeedback(
                complaint_id=complaint_id,
                reply_queue_id=reply_queue_id,
            )
            self.db.add(feedback)
        elif reply_queue_id and feedback.reply_queue_id is None:
            feedback.reply_queue_id = reply_queue_id
        return feedback

    @staticmethod
    def _as_uuid(value):
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))
