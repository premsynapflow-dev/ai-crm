from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.models import Client, Complaint
from app.db.session import get_db
from app.intelligence.classifier import classify_message
from app.utils.logging import get_logger
from app.workflow.dispatcher import dispatch_action
from app.workflow.rule_engine import decide_action

router = APIRouter(prefix="/webhook", tags=["webhook"])
logger = get_logger(__name__)


class ComplaintRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000)
    source: str = Field(default="api", min_length=1, max_length=50)
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None


class EmailWebhookRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(..., alias="from")
    subject: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)


class WhatsAppWebhookRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(..., alias="From")
    body: str = Field(..., alias="Body", min_length=1)


def _process_complaint_for_client(
    db: Session,
    client: Client,
    message: str,
    source: str,
    customer_email: Optional[str],
    customer_phone: Optional[str],
) -> str:
    # Single unified AI classification call (Gemini - free tier)
    classification = classify_message(message)

    intent = classification["intent"]
    recommended_action = classification["recommended_action"]
    confidence = classification["confidence"]
    priority = classification["priority"]
    category = classification["category"]
    sentiment_score = classification["sentiment"]
    urgency = classification["urgency_score"]

    # Decide final workflow action (ESCALATE_HIGH or AUTO_REPLY)
    action = decide_action(
        category=category,
        sentiment=sentiment_score,
        urgency=urgency,
    )

    complaint = Complaint(
        client_id=client.id,
        message=message,
        source=source or "api",
        customer_email=customer_email,
        customer_phone=customer_phone,
        intent=intent,
        recommended_action=recommended_action,
        confidence=confidence,
        priority=priority,
        category=category,
        sentiment=sentiment_score,
        urgency_score=urgency,
        status=action,
    )
    db.add(complaint)
    db.flush()

    dispatch_action(
        action=action,
        client_name=client.name,
        complaint_id=str(complaint.id),
        message=message,
        category=category,
        sentiment=sentiment_score,
        urgency=urgency,
        intent=intent,
        recommended_action=recommended_action,
    )

    return action


def _authenticate_client(db: Session, x_api_key: str) -> Client:
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing x-api-key header",
        )

    client = db.query(Client).filter(Client.api_key == x_api_key).first()
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    return client


@router.post("/complaint")
def process_complaint(
    payload: ComplaintRequest,
    x_api_key: str = Header(default="", alias="x-api-key"),
    db: Session = Depends(get_db),
) -> dict:
    try:
        client = _authenticate_client(db, x_api_key)
        action = _process_complaint_for_client(
            db=db,
            client=client,
            message=payload.message,
            source=payload.source,
            customer_email=payload.customer_email,
            customer_phone=payload.customer_phone,
        )
        db.commit()
    except HTTPException:
        raise
    except OperationalError:
        db.rollback()
        logger.error("Database unavailable while processing complaint.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporarily unavailable",
        )
    except Exception as exc:
        db.rollback()
        logger.exception("Complaint processing failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Complaint processing failed",
        ) from exc

    return {"status": "processed", "action": action}


@router.post("/email")
def process_email_webhook(
    payload: EmailWebhookRequest,
    x_api_key: str = Header(default="", alias="x-api-key"),
    db: Session = Depends(get_db),
) -> dict:
    try:
        client = _authenticate_client(db, x_api_key)
        message = f"{payload.subject} {payload.text}".strip()
        action = _process_complaint_for_client(
            db=db,
            client=client,
            message=message,
            source="email",
            customer_email=payload.from_,
            customer_phone=None,
        )
        db.commit()
    except HTTPException:
        raise
    except OperationalError:
        db.rollback()
        logger.error("Database unavailable while processing email webhook.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporarily unavailable",
        )
    except Exception as exc:
        db.rollback()
        logger.exception("Email webhook processing failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Complaint processing failed",
        ) from exc

    return {"status": "processed", "action": action}


@router.post("/whatsapp")
def process_whatsapp_webhook(
    payload: WhatsAppWebhookRequest,
    x_api_key: str = Header(default="", alias="x-api-key"),
    db: Session = Depends(get_db),
) -> dict:
    try:
        client = _authenticate_client(db, x_api_key)
        action = _process_complaint_for_client(
            db=db,
            client=client,
            message=payload.body,
            source="whatsapp",
            customer_email=None,
            customer_phone=payload.from_,
        )
        db.commit()
    except HTTPException:
        raise
    except OperationalError:
        db.rollback()
        logger.error("Database unavailable while processing whatsapp webhook.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporarily unavailable",
        )
    except Exception as exc:
        db.rollback()
        logger.exception("WhatsApp webhook processing failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Complaint processing failed",
        ) from exc

    return {"status": "processed", "action": action}
