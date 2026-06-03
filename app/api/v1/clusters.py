"""Complaint clustering API — Layer 3 semantic grouping."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.orm import Session

from app.db.models import Client, Complaint, ComplaintCluster
from app.db.session import get_db
from app.dependencies.auth import require_api_key
from app.services.complaint_clustering import cluster_complaints, generate_embeddings_batch
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/clusters", tags=["clustering"])


@router.get("")
def list_clusters(
    days: int = Query(30, ge=1, le=90),
    db: Session = Depends(get_db),
    current_client: Client = Depends(require_api_key),
):
    """List complaint clusters for the past N days, ordered by size descending."""
    from datetime import date, timedelta

    cutoff = date.today() - timedelta(days=days)
    clusters = (
        db.query(ComplaintCluster)
        .filter(
            ComplaintCluster.client_id == current_client.id,
            ComplaintCluster.period_end >= cutoff,
        )
        .order_by(ComplaintCluster.cluster_size.desc())
        .all()
    )

    return {
        "clusters": [
            {
                "id": str(c.id),
                "cluster_label": c.cluster_label,
                "size": c.cluster_size,
                "summary": c.summary,
                "top_category": c.top_category,
                "top_entities": c.top_entities,
                "period_start": str(c.period_start),
                "period_end": str(c.period_end),
            }
            for c in clusters
        ],
        "total": len(clusters),
    }


@router.get("/{cluster_id}/complaints")
def cluster_complaints_list(
    cluster_id: UUID,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_client: Client = Depends(require_api_key),
):
    """List complaints belonging to a specific cluster."""
    cluster = (
        db.query(ComplaintCluster)
        .filter(
            ComplaintCluster.id == cluster_id,
            ComplaintCluster.client_id == current_client.id,
        )
        .first()
    )
    if not cluster:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Cluster not found")

    complaints = (
        db.query(Complaint)
        .filter(Complaint.cluster_id == cluster_id)
        .order_by(Complaint.created_at.desc())
        .limit(limit)
        .all()
    )

    return {
        "cluster": {
            "id": str(cluster.id),
            "summary": cluster.summary,
            "size": cluster.cluster_size,
        },
        "complaints": [
            {
                "id": str(c.id),
                "ticket_id": c.ticket_id,
                "summary": c.summary,
                "category": c.category,
                "urgency_score": c.urgency_score,
                "status": c.status,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in complaints
        ],
        "total": len(complaints),
    }


@router.post("/run")
def run_clustering(
    background_tasks: BackgroundTasks,
    days: int = Query(30, ge=7, le=90),
    db: Session = Depends(get_db),
    current_client: Client = Depends(require_api_key),
):
    """
    Trigger embedding generation + DBSCAN clustering as a background task.
    Returns immediately with a job confirmation.
    """
    client_id = str(current_client.id)

    def _run():
        from app.db.session import SessionLocal as SL
        _db = SL()
        try:
            embedded = generate_embeddings_batch(_db, client_id, batch_size=100, days=days)
            result = cluster_complaints(_db, client_id, days=days)
            logger.info(
                "Clustering complete client=%s embedded=%s clusters=%s",
                client_id, embedded, result.get("clusters_created"),
            )
        except Exception as exc:
            logger.exception("Clustering failed client=%s: %s", client_id, exc)
        finally:
            _db.close()

    background_tasks.add_task(_run)

    return {
        "status": "started",
        "message": f"Clustering job queued for last {days} days of complaints.",
    }
