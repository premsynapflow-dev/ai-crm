from datetime import datetime, timedelta, timezone
import uuid
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.db.models import AIReplyQueue, Client, Complaint, ReplyFeedback
from app.replies.send_reply import send_complaint_reply
from app.services.auto_reply_drafts import AutoReplyDraftService
from app.services.event_logger import log_event
from app.services.reply_confidence_scorer import ReplyConfidenceScorer


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class HardenedAutoReplyService:
    def __init__(self, db: Session):
        self.db = db
        self.confidence_scorer = ReplyConfidenceScorer()
        self.draft_service = AutoReplyDraftService(db)

    def generate_and_queue_reply(
        self,
        ticket: Complaint,
        force_human_review: bool = False,
        custom_config: dict[str, Any] | None = None,
        commit: bool = True,
    ) -> AIReplyQueue | None:
        client = self.db.query(Client).filter(Client.id == ticket.client_id).first()
        draft_result = self.draft_service.prepare_draft(
            ticket,
            client=client,
            custom_config=custom_config,
            allow_disabled=force_human_review,
            commit=False,
        )
        if draft_result.draft is None or draft_result.generation is None:
            if commit:
                self.db.commit()
            else:
                self.db.flush()
            return None
        return self._store_queue_decision(
            ticket,
            draft_result.draft,
            draft_result.generation.generation_metadata,
            commit=commit,
        )

    async def generate_and_queue_reply_async(
        self,
        ticket: Complaint,
        force_human_review: bool = False,
        custom_config: dict[str, Any] | None = None,
        commit: bool = True,
    ) -> AIReplyQueue | None:
        client = self.db.query(Client).filter(Client.id == ticket.client_id).first()
        draft_result = await self.draft_service.prepare_draft_async(
            ticket,
            client=client,
            custom_config=custom_config,
            allow_disabled=force_human_review,
            commit=False,
        )
        if draft_result.draft is None or draft_result.generation is None:
            if commit:
                self.db.commit()
            else:
                self.db.flush()
            return None
        return self._store_queue_decision(
            ticket,
            draft_result.draft,
            draft_result.generation.generation_metadata,
            commit=commit,
        )

    def _store_queue_decision(
        self,
        ticket: Complaint,
        draft,
        generation_meta: dict[str, Any],
        *,
        commit: bool,
    ) -> AIReplyQueue:
        now = _utcnow()
        scoring_result = self.confidence_scorer.score_reply(
            reply_text=draft.body,
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

        queue_entry.reply_draft_id = draft.id
        queue_entry.generated_reply = draft.body
        queue_entry.confidence_score = scoring_result["confidence_score"]
        queue_entry.generation_strategy = generation_meta.get("strategy", "ai_draft")
        queue_entry.generation_metadata = {
            **(generation_meta or {}),
            "draft_id": str(draft.id),
            "draft_subject": draft.subject,
            "prompt_version": draft.prompt_version,
        }
        queue_entry.hallucination_check_passed = scoring_result["hallucination_check_passed"]
        queue_entry.toxicity_score = scoring_result["toxicity_score"]
        queue_entry.factual_consistency_score = scoring_result["factual_consistency_score"]
        queue_entry.status = "pending"
        queue_entry.reviewed_by = None
        queue_entry.reviewed_at = None
        queue_entry.edited_reply = None
        queue_entry.rejection_reason = None
        queue_entry.expires_at = now + timedelta(hours=24)
        queue_entry.created_at = now

        ticket.ai_reply = draft.body
        ticket.ai_reply_confidence = scoring_result["confidence_score"]
        ticket.ai_reply_status = "pending"

        self.db.flush()
        self._ensure_feedback_record(ticket.id, queue_entry.id)
        log_event(
            self.db,
            ticket.client_id,
            "reply_draft_generated",
            {
                "ticket_id": ticket.ticket_id,
                "complaint_id": str(ticket.id),
                "draft_id": str(draft.id),
                "customer_id": str(draft.customer_id) if draft.customer_id else None,
                "queue_id": str(queue_entry.id) if queue_entry.id else None,
                "confidence_score": queue_entry.confidence_score,
                "subject": draft.subject,
            },
        )
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
        edited_subject: Optional[str] = None,
        commit: bool = True,
    ) -> bool:
        queue_entry = self.db.query(AIReplyQueue).filter(AIReplyQueue.id == self._as_uuid(queue_id)).first()
        if not queue_entry or queue_entry.status != "pending":
            return False

        complaint = self.db.query(Complaint).filter(Complaint.id == queue_entry.complaint_id).first()
        if complaint is None:
            return False
        client = self.db.query(Client).filter(Client.id == complaint.client_id).first()
        draft = queue_entry.reply_draft

        reply_to_send = (edited_reply or (draft.body if draft else None) or queue_entry.generated_reply or "").strip()
        subject_to_send = (edited_subject or (draft.subject if draft else None) or "").strip() or None
        reviewed_at = _utcnow()

        queue_entry.status = "edited" if edited_reply or edited_subject else "approved"
        queue_entry.reviewed_by = reviewer_email
        queue_entry.reviewed_at = reviewed_at
        queue_entry.edited_reply = edited_reply.strip() if edited_reply else None
        queue_entry.rejection_reason = None
        complaint.ai_reply = reply_to_send
        complaint.ai_reply_confidence = queue_entry.confidence_score

        if draft is not None:
            if edited_subject:
                draft.subject = edited_subject.strip()
            if edited_reply:
                draft.body = edited_reply.strip()
            draft.status = "approved"
            draft.approved_at = reviewed_at
            draft.rejected_at = None

        send_result = self._send_reply(
            complaint,
            reply_to_send,
            client,
            reply_subject=subject_to_send,
        )
        if not send_result.get("sent"):
            queue_entry.status = "pending"
            queue_entry.reviewed_by = None
            queue_entry.reviewed_at = None
            if draft is not None:
                draft.status = "pending"
                draft.approved_at = None
                draft.sent_at = None
            if commit:
                self.db.commit()
            else:
                self.db.flush()
            return False

        if draft is not None:
            draft.status = "approved"
            draft.sent_at = complaint.ai_reply_sent_at or reviewed_at
        log_event(
            self.db,
            complaint.client_id,
            "reply_draft_approved",
            {
                "ticket_id": complaint.ticket_id,
                "complaint_id": str(complaint.id),
                "draft_id": str(draft.id) if draft else None,
                "queue_id": str(queue_entry.id),
                "reviewed_by": reviewer_email,
                "time_to_approval_seconds": self._approval_latency_seconds(queue_entry, reviewed_at),
            },
        )

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
        draft = queue_entry.reply_draft
        reviewed_at = _utcnow()

        queue_entry.status = "rejected"
        queue_entry.reviewed_by = reviewer_email
        queue_entry.reviewed_at = reviewed_at
        queue_entry.rejection_reason = reason.strip()
        complaint.ai_reply_status = "agent_review"
        if draft is not None:
            draft.status = "rejected"
            draft.rejected_at = reviewed_at
            draft.approved_at = None
            draft.sent_at = None

        log_event(
            self.db,
            complaint.client_id,
            "reply_draft_rejected",
            {
                "ticket_id": complaint.ticket_id,
                "complaint_id": str(complaint.id),
                "draft_id": str(draft.id) if draft else None,
                "queue_id": str(queue_entry.id),
                "reviewed_by": reviewer_email,
                "reason": reason.strip(),
                "time_to_approval_seconds": self._approval_latency_seconds(queue_entry, reviewed_at),
            },
        )

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

    def _send_reply(
        self,
        ticket: Complaint,
        reply_text: str,
        client: Client | None,
        *,
        reply_subject: str | None = None,
    ):
        return send_complaint_reply(
            db=self.db,
            complaint=ticket,
            client=client,
            reply_text=reply_text,
            reply_subject=reply_subject,
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
    def _approval_latency_seconds(queue_entry: AIReplyQueue, reviewed_at: datetime) -> int | None:
        created_at = queue_entry.created_at
        if created_at is None:
            return None
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        return max(0, int((reviewed_at - created_at).total_seconds()))

    @staticmethod
    def _as_uuid(value):
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))
