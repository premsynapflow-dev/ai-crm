from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import WorkflowExecution
from app.db.session import get_db
from app.dependencies.auth import require_api_key
from app.queue.backends import queue_health

router = APIRouter(prefix="/api/v1/queue", tags=["queue-v1"])


@router.get("/health")
def get_queue_health(db: Session = Depends(get_db), current_client=Depends(require_api_key)):
    health = queue_health(db)
    workflow_rows = (
        db.query(WorkflowExecution.execution_status, func.count(WorkflowExecution.id))
        .filter(WorkflowExecution.client_id == current_client.id)
        .group_by(WorkflowExecution.execution_status)
        .all()
    )
    health["workflow_executions"] = {status: int(count) for status, count in workflow_rows}
    return health
