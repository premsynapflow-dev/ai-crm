"""Entity extraction API endpoints."""
from __future__ import annotations

import uuid
from collections import Counter
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import get_current_client_user
from app.db.models import Client, Complaint, ComplaintEntity
from app.db.session import get_db
from app.dependencies.auth import require_api_key
from app.intelligence.entity_extractor import extract_and_store

router = APIRouter(prefix="/api/v1/entities", tags=["entities"])


@router.get("/complaints/{complaint_id}")
async def get_complaint_entities(
    complaint_id: str,
    client: Client = Depends(require_api_key),
    db: Session = Depends(get_db),
):
    try:
        cid = uuid.UUID(complaint_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid complaint_id")

    complaint = db.query(Complaint).filter(
        Complaint.id == cid,
        Complaint.client_id == client.id,
    ).first()
    if complaint is None:
        raise HTTPException(status_code=404, detail="Complaint not found")

    entities = db.query(ComplaintEntity).filter(
        ComplaintEntity.complaint_id == cid
    ).all()

    if not entities and complaint.summary:
        # Extract on-demand if not yet done
        extracted = extract_and_store(db, cid, complaint.summary)
        db.commit()
        entities = db.query(ComplaintEntity).filter(ComplaintEntity.complaint_id == cid).all()

    grouped: dict[str, list[dict]] = {}
    for ent in entities:
        grouped.setdefault(ent.entity_type, []).append({
            "value": ent.entity_value,
            "confidence": ent.confidence,
        })

    return {"complaint_id": complaint_id, "entities": grouped}


@router.get("/top")
async def get_top_entities(
    entity_type: str | None = Query(None, description="Filter by type: product, location, employee, order_id, date"),
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(20, ge=1, le=100),
    client: Client = Depends(require_api_key),
    db: Session = Depends(get_db),
):
    since = datetime.now(timezone.utc) - timedelta(days=days)

    q = (
        db.query(ComplaintEntity)
        .join(Complaint, Complaint.id == ComplaintEntity.complaint_id)
        .filter(
            Complaint.client_id == client.id,
            ComplaintEntity.extracted_at >= since,
        )
    )
    if entity_type:
        q = q.filter(ComplaintEntity.entity_type == entity_type)

    rows = q.all()
    counter: Counter = Counter()
    by_type: dict[str, Counter] = {}
    for row in rows:
        counter[(row.entity_type, row.entity_value)] += 1
        by_type.setdefault(row.entity_type, Counter())[row.entity_value] += 1

    if entity_type:
        top = [
            {"entity_type": entity_type, "entity_value": val, "count": cnt}
            for val, cnt in by_type.get(entity_type, Counter()).most_common(limit)
        ]
    else:
        top = [
            {"entity_type": etype, "entity_value": val, "count": cnt}
            for (etype, val), cnt in counter.most_common(limit)
        ]

    return {
        "days": days,
        "entity_type_filter": entity_type,
        "total_entities": len(rows),
        "top": top,
    }
