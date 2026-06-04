"""Intelligence API — customer pulse, operations signals, and cluster actions."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.analytics.customer_pulse import detect_complaint_spikes, generate_customer_pulse
from app.db.models import Client, Complaint, ComplaintCluster
from app.db.session import get_db
from app.dependencies.auth import require_api_key
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/intelligence", tags=["intelligence"])


@router.get("/pulse")
def get_customer_pulse(
    db: Session = Depends(get_db),
    current_client: Client = Depends(require_api_key),
):
    """Return the daily customer pulse: top issues, sentiment trend, churn risk customers."""
    return generate_customer_pulse(db, str(current_client.id))


@router.get("/operations")
def get_operations_intelligence(
    db: Session = Depends(get_db),
    current_client: Client = Depends(require_api_key),
):
    """Return operations intelligence: spike detection, product defect signals, top themes."""
    client_id = str(current_client.id)
    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)

    spikes = detect_complaint_spikes(db, client_id, send_alert=False)

    # Top 5 categories with complaint counts and sample summaries
    category_rows = (
        db.query(Complaint.category, func.count(Complaint.id).label("count"))
        .filter(
            Complaint.client_id == client_id,
            Complaint.created_at >= seven_days_ago,
        )
        .group_by(Complaint.category)
        .order_by(func.count(Complaint.id).desc())
        .limit(5)
        .all()
    )

    defect_signals = []
    for category, count in category_rows:
        samples = (
            db.query(Complaint.summary)
            .filter(
                Complaint.client_id == client_id,
                Complaint.category == category,
                Complaint.created_at >= seven_days_ago,
                Complaint.summary.isnot(None),
            )
            .order_by(Complaint.urgency_score.desc())
            .limit(3)
            .all()
        )
        defect_signals.append({
            "category": category or "unknown",
            "complaint_count": count,
            "sample_messages": [s.summary for s in samples if s.summary],
        })

    # Total complaints for percentage calculation
    total_7d = db.query(func.count(Complaint.id)).filter(
        Complaint.client_id == client_id,
        Complaint.created_at >= seven_days_ago,
    ).scalar() or 1

    top_themes = [
        {
            "theme": row["category"],
            "count": row["complaint_count"],
            "pct": round(row["complaint_count"] / total_7d * 100, 1),
        }
        for row in defect_signals
    ]

    return {
        "spikes": spikes,
        "defect_signals": defect_signals,
        "top_themes": top_themes,
        "period_days": 7,
        "total_complaints": total_7d,
    }


class AcknowledgeClusterRequest(BaseModel):
    action: str  # "bulk_reply" | "escalate" | "create_task"
    note: str = ""


@router.post("/clusters/{cluster_id}/acknowledge")
def acknowledge_cluster(
    cluster_id: UUID,
    body: AcknowledgeClusterRequest,
    db: Session = Depends(get_db),
    current_client: Client = Depends(require_api_key),
):
    """Acknowledge a complaint cluster and record the action taken."""
    cluster = (
        db.query(ComplaintCluster)
        .filter(
            ComplaintCluster.id == cluster_id,
            ComplaintCluster.client_id == current_client.id,
        )
        .first()
    )
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")

    allowed_actions = {"bulk_reply", "escalate", "create_task"}
    if body.action not in allowed_actions:
        raise HTTPException(status_code=422, detail=f"action must be one of {sorted(allowed_actions)}")

    meta = dict(cluster.metadata_json or {}) if hasattr(cluster, "metadata_json") else {}
    meta["acknowledged_action"] = body.action
    meta["acknowledged_note"] = body.note
    meta["acknowledged_at"] = datetime.now(timezone.utc).isoformat()
    if hasattr(cluster, "metadata_json"):
        cluster.metadata_json = meta
    db.commit()

    return {
        "cluster_id": str(cluster_id),
        "action": body.action,
        "note": body.note,
        "status": "acknowledged",
    }
