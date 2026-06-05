"""AI Executive Copilot API — natural language Q&A over complaint data (Layer 7)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.models import Client, CopilotQuery
from app.db.session import get_db
from app.dependencies.auth import require_api_key
from app.intelligence.copilot import answer_query
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/copilot", tags=["copilot"])


class CopilotRequest(BaseModel):
    question: str = Field(..., min_length=5, max_length=500)
    days: int = Field(default=30, ge=1, le=90)


@router.post("/query")
def copilot_query(
    body: CopilotRequest,
    db: Session = Depends(get_db),
    current_client: Client = Depends(require_api_key),
):
    """
    Ask an executive question about complaint data.

    Examples:
    - "What is our biggest complaint issue this week?"
    - "Why are billing complaints rising?"
    - "Which product is getting the most negative feedback?"
    """
    result = answer_query(
        db=db,
        client_id=str(current_client.id),
        question=body.question,
        user_id=None,
        days=body.days,
    )
    return result


@router.get("/history")
def copilot_history(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_client: Client = Depends(require_api_key),
):
    """Return recent copilot queries for this client."""
    queries = (
        db.query(CopilotQuery)
        .filter(CopilotQuery.client_id == current_client.id)
        .order_by(CopilotQuery.created_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "queries": [
            {
                "id": str(q.id),
                "question": q.query,
                "answer": q.response,
                "latency_ms": q.latency_ms,
                "created_at": q.created_at.isoformat() if q.created_at else None,
            }
            for q in queries
        ],
        "total": len(queries),
    }


@router.delete("/history/{query_id}")
def delete_copilot_query(
    query_id: str,
    db: Session = Depends(get_db),
    current_client: Client = Depends(require_api_key),
):
    """Permanently delete a copilot query from history."""
    try:
        qid = uuid.UUID(query_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid query id")

    row = (
        db.query(CopilotQuery)
        .filter(CopilotQuery.id == qid, CopilotQuery.client_id == current_client.id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Query not found")

    db.delete(row)
    db.commit()
    return {"success": True}
