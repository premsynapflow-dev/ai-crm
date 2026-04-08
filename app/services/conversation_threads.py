from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Client, Complaint, UnifiedMessage
from app.intelligence.prompt_builder import DEFAULT_CONFIG, build_thread_reply_prompt, get_prompt_config_for_client
from app.services.ai import get_gemini_client

settings = get_settings()


def _utc_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc).isoformat()
    return value.astimezone(timezone.utc).isoformat()


def _normalize_text(value: str | None) -> str:
    return " ".join(str(value or "").split()).strip()


def _excerpt(value: str | None, *, limit: int = 220) -> str:
    text = _normalize_text(value)
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3].rstrip()}..."


def _attachment_names(message: UnifiedMessage) -> list[str]:
    names: list[str] = []
    for attachment in list(message.attachments or []):
        filename = _normalize_text(attachment.get("filename")) if isinstance(attachment, dict) else ""
        if filename and filename not in names:
            names.append(filename)
    return names


def _display_sender(message: UnifiedMessage) -> str:
    if message.direction == "outbound":
        return _normalize_text(message.sender_name) or "Support team"
    return _normalize_text(message.sender_name) or _normalize_text(message.sender_id) or "Customer"


def serialize_thread_message(message: UnifiedMessage) -> dict[str, Any]:
    return {
        "id": str(message.id),
        "direction": message.direction,
        "channel": message.channel,
        "sender_name": _display_sender(message),
        "sender_id": message.sender_id,
        "message_text": message.message_text or "",
        "timestamp": _utc_iso(message.timestamp),
        "status": message.status,
        "attachments": list(message.attachments or []),
    }


def find_complaint_for_conversation(
    db: Session,
    *,
    client_id,
    channel: str,
    external_thread_id: str,
) -> Complaint | None:
    complaint = (
        db.query(Complaint)
        .filter(
            Complaint.client_id == client_id,
            Complaint.source == channel,
            Complaint.thread_id == external_thread_id,
        )
        .order_by(Complaint.created_at.desc())
        .first()
    )
    if complaint is not None:
        return complaint

    linked_messages = (
        db.query(UnifiedMessage)
        .filter(
            UnifiedMessage.client_id == client_id,
            UnifiedMessage.channel == channel,
            UnifiedMessage.external_thread_id == external_thread_id,
        )
        .order_by(UnifiedMessage.timestamp.desc())
        .all()
    )
    complaint_ids: list[str] = []
    for message in linked_messages:
        complaint_id = str((message.raw_payload or {}).get("complaint_id") or "").strip()
        if complaint_id and complaint_id not in complaint_ids:
            complaint_ids.append(complaint_id)
    for complaint_id in complaint_ids:
        try:
            normalized_complaint_id = UUID(complaint_id)
        except ValueError:
            continue
        complaint = (
            db.query(Complaint)
            .filter(
                Complaint.client_id == client_id,
                Complaint.id == normalized_complaint_id,
            )
            .first()
        )
        if complaint is not None:
            return complaint
    return None


def get_thread_messages(db: Session, complaint: Complaint) -> list[UnifiedMessage]:
    base_query = (
        db.query(UnifiedMessage)
        .filter(
            UnifiedMessage.client_id == complaint.client_id,
            UnifiedMessage.channel == complaint.source,
        )
        .order_by(UnifiedMessage.timestamp.asc(), UnifiedMessage.created_at.asc())
    )

    messages: list[UnifiedMessage] = []
    if complaint.thread_id:
        messages = base_query.filter(UnifiedMessage.external_thread_id == complaint.thread_id).all()
    if messages:
        return messages

    candidates = base_query.all()
    complaint_id = str(complaint.id)
    return [
        message
        for message in candidates
        if str((message.raw_payload or {}).get("complaint_id") or "") == complaint_id
    ]


def build_conversation_transcript(messages: list[UnifiedMessage], *, include_timestamps: bool = True) -> str:
    transcript_lines: list[str] = []
    for message in messages:
        sender_label = "Support" if message.direction == "outbound" else "Customer"
        sender_name = _display_sender(message)
        timestamp = ""
        if include_timestamps and message.timestamp is not None:
            timestamp = f" [{_utc_iso(message.timestamp)}]"
        body = (message.message_text or "").strip() or "(no message body)"
        transcript_lines.append(f"{sender_label} - {sender_name}{timestamp}:\n{body}")
        attachments = _attachment_names(message)
        if attachments:
            transcript_lines.append(f"Attachments: {', '.join(attachments)}")
    return "\n\n".join(transcript_lines).strip()


def build_conversation_summary(complaint: Complaint, messages: list[UnifiedMessage]) -> dict[str, Any]:
    inbound_messages = [message for message in messages if message.direction == "inbound"]
    outbound_messages = [message for message in messages if message.direction == "outbound"]
    latest_message = messages[-1] if messages else None
    first_customer_message = inbound_messages[0] if inbound_messages else None
    latest_customer_message = inbound_messages[-1] if inbound_messages else None
    latest_support_message = outbound_messages[-1] if outbound_messages else None

    attachments: list[str] = []
    for message in messages:
        for filename in _attachment_names(message):
            if filename not in attachments:
                attachments.append(filename)

    key_points: list[str] = []
    if complaint.summary:
        key_points.append(_excerpt(complaint.summary))
    if latest_customer_message and latest_customer_message is not first_customer_message:
        latest_excerpt = _excerpt(latest_customer_message.message_text)
        if latest_excerpt:
            key_points.append(f"Latest customer update: {latest_excerpt}")
    if latest_support_message:
        support_excerpt = _excerpt(latest_support_message.message_text)
        if support_excerpt:
            key_points.append(f"Latest support reply: {support_excerpt}")
    if attachments:
        key_points.append(f"Attachments shared: {', '.join(attachments)}")
    if not key_points and first_customer_message:
        first_excerpt = _excerpt(first_customer_message.message_text)
        if first_excerpt:
            key_points.append(first_excerpt)

    waiting_on = "support"
    if latest_message and latest_message.direction == "outbound":
        waiting_on = "customer"

    return {
        "headline": complaint.summary,
        "waiting_on": waiting_on,
        "message_count": len(messages),
        "customer_message_count": len(inbound_messages),
        "support_message_count": len(outbound_messages),
        "last_updated_at": _utc_iso(latest_message.timestamp if latest_message else complaint.created_at),
        "attachments": attachments,
        "key_points": key_points,
    }


def _reply_config(client: Client | None, custom_config: dict[str, Any] | None = None) -> dict[str, Any]:
    return custom_config or (get_prompt_config_for_client(client) if client is not None else None) or DEFAULT_CONFIG


def _fallback_reply() -> dict[str, Any]:
    return {
        "reply_text": "Thank you for your message. We are reviewing the full conversation and will get back to you shortly.",
        "confidence_score": 0.35,
    }


def generate_thread_reply(
    db: Session,
    complaint: Complaint,
    *,
    client: Client | None = None,
    custom_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    api_key = (settings.gemini_api_key or "").strip()
    messages = get_thread_messages(db, complaint)
    transcript = build_conversation_transcript(messages, include_timestamps=True)
    prompt = build_thread_reply_prompt(complaint.summary or complaint.category or "Customer complaint", transcript, _reply_config(client, custom_config))

    if not api_key:
        return {
            **_fallback_reply(),
            "context_messages": len(messages),
        }

    try:
        response = get_gemini_client().generate_content(
            prompt,
            model="gemini-2.5-flash-lite",
            max_output_tokens=500,
            temperature=0.35,
        )
        return {
            "reply_text": response.text.strip() or _fallback_reply()["reply_text"],
            "confidence_score": 0.88 if len(messages) >= 2 else 0.76,
            "context_messages": len(messages),
        }
    except Exception:
        return {
            **_fallback_reply(),
            "context_messages": len(messages),
        }


async def generate_thread_reply_async(
    db: Session,
    complaint: Complaint,
    *,
    client: Client | None = None,
    custom_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    api_key = (settings.gemini_api_key or "").strip()
    messages = get_thread_messages(db, complaint)
    transcript = build_conversation_transcript(messages, include_timestamps=True)
    prompt = build_thread_reply_prompt(complaint.summary or complaint.category or "Customer complaint", transcript, _reply_config(client, custom_config))

    if not api_key:
        return {
            **_fallback_reply(),
            "context_messages": len(messages),
        }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client_session:
            response = await client_session.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent",
                params={"key": api_key},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.35,
                        "maxOutputTokens": 500,
                    },
                },
            )
            response.raise_for_status()
            payload = response.json()
            reply_text = (
                payload.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
            ).strip()
        return {
            "reply_text": reply_text or _fallback_reply()["reply_text"],
            "confidence_score": 0.88 if len(messages) >= 2 else 0.76,
            "context_messages": len(messages),
        }
    except Exception:
        return {
            **_fallback_reply(),
            "context_messages": len(messages),
        }
