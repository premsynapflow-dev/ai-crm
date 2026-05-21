from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import require_api_key
from app.queue.backends import queue_health

router = APIRouter(prefix="/api/v1/queue", tags=["queue-v1"])


@router.get("/health")
def get_queue_health(db: Session = Depends(get_db), current_client=Depends(require_api_key)):
    return queue_health(db)
