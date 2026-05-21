from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.models import ModelAuditLog
from app.db.session import get_db
from app.dependencies.auth import require_api_key

router = APIRouter(prefix="/api/v1/model-audit", tags=["model-audit-v1"])


@router.get("")
def list_model_audit_logs(limit: int = 50, db: Session = Depends(get_db), current_client=Depends(require_api_key)):
    rows = (
        db.query(ModelAuditLog)
        .filter(ModelAuditLog.client_id == current_client.id)
        .order_by(ModelAuditLog.created_at.desc())
        .limit(max(1, min(limit, 100)))
        .all()
    )
    return {
        "items": [
            {
                "id": str(row.id),
                "provider": row.provider,
                "model": row.model,
                "task_type": row.task_type,
                "complaint_id": str(row.complaint_id) if row.complaint_id else None,
                "customer_id": str(row.customer_id) if row.customer_id else None,
                "confidence_score": row.confidence_score,
                "latency_ms": row.latency_ms,
                "status": row.status,
                "error_message": row.error_message,
                "prompt_preview": row.prompt_preview,
                "output_preview": row.output_preview,
                "metadata": row.metadata_json or {},
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]
    }
