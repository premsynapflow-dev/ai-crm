from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.billing.usage import can_process_ticket, track_ticket_usage
from app.db.models import Client, Complaint
from app.db.session import get_db
from app.intelligence.chatbot import generate_reply
from app.intelligence.classifier import classify_message, summarize_if_needed
from app.services.classification_service import build_client_classification_config
from app.services.response_tracking import mark_first_response
from app.utils.ticket import generate_thread_id, generate_ticket_id

router = APIRouter(prefix="/api", tags=["chatbot"])


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    context: dict = Field(default_factory=dict)
    conversation_history: list[dict] = Field(default_factory=list)


def _client_from_api_key(db: Session, api_key: str) -> Client:
    client = db.query(Client).filter(Client.api_key == api_key).first()
    if not client:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return client


@router.post("/chat")
def chat_endpoint(payload: ChatRequest, x_api_key: str = Header(default="", alias="x-api-key"), db: Session = Depends(get_db)):
    client = _client_from_api_key(db, x_api_key)
    if not can_process_ticket(client.id):
        raise HTTPException(status_code=402, detail="Usage limit exceeded")

    client_config = build_client_classification_config(db, client)
    classification = classify_message(payload.message, client_config)
    summary = summarize_if_needed(payload.message, classification)
    ai_result = generate_reply(
        payload.message,
        payload.context,
        payload.conversation_history,
        classification=classification,
        client_config=client_config,
    )

    complaint = Complaint(
        client_id=client.id,
        summary=summary,
        source="chatbot",
        customer_email=payload.context.get("customer_email"),
        customer_phone=payload.context.get("customer_phone"),
        intent=classification.get("intent"),
        recommended_action=classification.get("recommended_action"),
        confidence=classification.get("confidence"),
        priority=classification.get("priority"),
        category=classification.get("category", "general"),
        sentiment=classification.get("sentiment", 0.0),
        urgency_score=classification.get("urgency_score", 0.0),
        assigned_team=payload.context.get("assigned_team", "support"),
        ticket_id=payload.context.get("ticket_id") or generate_ticket_id(),
        thread_id=generate_thread_id(),
        status="CHATBOT_REPLY",
    )
    db.add(complaint)
    db.flush()
    if ai_result.get("reply"):
        mark_first_response(db, complaint)
    db.commit()
    track_ticket_usage(client.id)

    return {
        "reply": ai_result.get("reply", ""),
        "escalate": ai_result.get("escalate", False),
        "summary": summary,
        "ticket_id": complaint.ticket_id,
    }
