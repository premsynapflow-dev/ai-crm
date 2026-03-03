from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.models import Client, Complaint
from app.db.session import get_db
from app.intelligence.classifier import classify_complaint
from app.intelligence.sentiment import analyze_sentiment
from app.intelligence.urgency import compute_urgency_score
from app.utils.logging import get_logger
from app.workflow.dispatcher import dispatch_action
from app.workflow.rule_engine import decide_action

router = APIRouter(prefix="/webhook", tags=["webhook"])
logger = get_logger(__name__)


class ComplaintRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000)


@router.post("/complaint")
def process_complaint(
    payload: ComplaintRequest,
    x_api_key: str = Header(default="", alias="x-api-key"),
    db: Session = Depends(get_db),
) -> dict:
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing x-api-key header",
        )

    try:
        client = db.query(Client).filter(Client.api_key == x_api_key).first()
        if client is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
            )

        complaint = Complaint(
            client_id=client.id,
            message=payload.message,
            category="unclassified",
            sentiment=0.0,
            urgency_score=0.0,
            status="PENDING",
        )
        db.add(complaint)
        db.flush()

        category = classify_complaint(payload.message)
        sentiment = analyze_sentiment(payload.message)
        urgency = compute_urgency_score(payload.message, category, sentiment)
        action = decide_action(category=category, sentiment=sentiment, urgency=urgency)

        complaint.category = category
        complaint.sentiment = sentiment
        complaint.urgency_score = urgency
        complaint.status = action

        dispatch_action(
            action=action,
            client_name=client.name,
            complaint_id=str(complaint.id),
            message=payload.message,
            category=category,
            sentiment=sentiment,
            urgency=urgency,
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
