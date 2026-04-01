"""
API endpoints for escalation status and history.
Provides real-time escalation tracking and timeline views.
"""

from uuid import UUID
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models import Complaint, Escalation
from app.db.session import get_db
from app.dependencies.auth import require_api_key
from app.middleware.feature_gate import ensure_feature_access
from app.services.escalation_engine import EscalationEngine

router = APIRouter(prefix="/api/v1/compliance", tags=["compliance"])


# ===== Request/Response Models =====

class EscalationLevelInfo(BaseModel):
    level: int
    code: str
    escalate_to: str
    trigger_after_hours: int
    eta: Optional[str] = None
    hours_remaining: float

    class Config:
        from_attributes = True


class EscalationHistoryItem(BaseModel):
    id: str
    level: int
    level_code: Optional[str] = None
    escalated_to: str
    reason: Optional[str] = None
    metadata: dict = {}
    created_at: Optional[str] = None
    next_escalation_at: Optional[str] = None

    class Config:
        from_attributes = True


class EscalationStatusResponse(BaseModel):
    ticket_id: str
    current_level: int
    current_level_name: str
    hours_open: float
    is_resolved: bool
    next_escalation_level: Optional[EscalationLevelInfo] = None
    escalation_history: List[EscalationHistoryItem] = []

    class Config:
        from_attributes = True


class EscalationTimelineItem(BaseModel):
    timestamp: str
    event_type: str  # "created", "escalated_to_L1", "escalated_to_L2", "escalated_to_IO", "resolved"
    level: Optional[int] = None
    level_code: Optional[str] = None
    escalated_to: Optional[str] = None
    reason: Optional[str] = None
    hours_since_creation: float


class EscalationTimelineResponse(BaseModel):
    ticket_id: str
    created_at: str
    timeline: List[EscalationTimelineItem] = []
    current_level: int
    current_status: str
    stage: str  # "L1", "L2", "IO", "Resolved"

    class Config:
        from_attributes = True


# ===== Endpoints =====

@router.get("/escalations/{ticket_id}")
def get_escalation_history(
    ticket_id: str,
    db: Session = Depends(get_db),
    current_client=Depends(require_api_key),
):
    """
    Get complete escalation history for a ticket.

    Returns all escalations in reverse chronological order with context.
    
    Example:
    ```
    GET /api/v1/compliance/escalations/550e8400-e29b-41d4-a716-446655440000
    ```

    Response:
    ```json
    {
      "ticket_id": "550e8400-e29b-41d4-a716-446655440000",
      "count": 2,
      "items": [
        {
          "id": "esc-id-1",
          "level": 2,
          "level_code": "L2",
          "escalated_to": "ombudsman_staff@rbi",
          "reason": "time_threshold",
          "metadata": {
            "previous_level": 1,
            "hours_open": 48.5
          },
          "created_at": "2026-04-01T15:30:00Z",
          "next_escalation_at": "2026-05-01T15:30:00Z"
        }
      ]
    }
    ```
    """
    try:
        ticket_uuid = UUID(ticket_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ticket_id format")

    complaint = db.query(Complaint).filter(
        Complaint.id == ticket_uuid,
        Complaint.client_id == current_client.id,
    ).first()

    if not complaint:
        raise HTTPException(status_code=404, detail="Ticket not found")

    engine = EscalationEngine(db)
    history = engine.get_escalation_history(ticket_uuid)

    return {
        "ticket_id": str(ticket_uuid),
        "count": len(history),
        "items": history,
    }


@router.get("/status/{ticket_id}")
def get_escalation_status(
    ticket_id: str,
    db: Session = Depends(get_db),
    current_client=Depends(require_api_key),
):
    """
    Get current escalation status and next escalation ETA.

    Includes:
    - Current escalation level
    - Hours ticket has been open
    - Next escalation level and ETA
    - Time remaining until next escalation
    - Full escalation history

    Example:
    ```
    GET /api/v1/compliance/status/550e8400-e29b-41d4-a716-446655440000
    ```

    Response:
    ```json
    {
      "ticket_id": "550e8400-e29b-41d4-a716-446655440000",
      "current_level": 1,
      "current_level_name": "L1",
      "hours_open": 10.5,
      "is_resolved": false,
      "next_escalation_level": {
        "level": 2,
        "code": "L2",
        "escalate_to": "ombudsman_staff@rbi",
        "trigger_after_hours": 48,
        "eta": "2026-04-03T15:30:00Z",
        "hours_remaining": 37.5
      },
      "escalation_history": [...]
    }
    ```
    """
    try:
        ticket_uuid = UUID(ticket_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ticket_id format")

    complaint = db.query(Complaint).filter(
        Complaint.id == ticket_uuid,
        Complaint.client_id == current_client.id,
    ).first()

    if not complaint:
        raise HTTPException(status_code=404, detail="Ticket not found")

    engine = EscalationEngine(db)
    status = engine.get_escalation_status(ticket_uuid)

    return status


@router.get("/timeline/{ticket_id}")
def get_escalation_timeline(
    ticket_id: str,
    db: Session = Depends(get_db),
    current_client=Depends(require_api_key),
):
    """
    Get escalation timeline for UI visualization.

    Returns chronological timeline of escalation events with durations.

    Example:
    ```
    GET /api/v1/compliance/timeline/550e8400-e29b-41d4-a716-446655440000
    ```

    Response:
    ```json
    {
      "ticket_id": "550e8400-e29b-41d4-a716-446655440000",
      "created_at": "2026-04-01T00:00:00Z",
      "current_level": 1,
      "current_status": "open",
      "stage": "L1",
      "timeline": [
        {
          "timestamp": "2026-04-01T00:00:00Z",
          "event_type": "created",
          "hours_since_creation": 0,
          "stage": "Created"
        },
        {
          "timestamp": "2026-04-02T00:00:00Z",
          "event_type": "escalated_to_L1",
          "level": 1,
          "level_code": "L1",
          "escalated_to": "regional_manager@rbi",
          "reason": "time_threshold",
          "hours_since_creation": 24
        }
      ]
    }
    ```
    """
    try:
        ticket_uuid = UUID(ticket_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ticket_id format")

    complaint = db.query(Complaint).filter(
        Complaint.id == ticket_uuid,
        Complaint.client_id == current_client.id,
    ).first()

    if not complaint:
        raise HTTPException(status_code=404, detail="Ticket not found")

    engine = EscalationEngine(db)
    status = engine.get_escalation_status(ticket_uuid)
    
    # Build timeline
    timeline = []
    
    # Add creation event
    if complaint.created_at:
        timeline.append(
            EscalationTimelineItem(
                timestamp=complaint.created_at.isoformat(),
                event_type="created",
                hours_since_creation=0,
            )
        )
    
    # Add escalation events
    hours_open = engine.calculate_hours_since_creation(complaint)
    for esc_history in status["escalation_history"]:
        timeline.append(
            EscalationTimelineItem(
                timestamp=esc_history["created_at"],
                event_type=f"escalated_to_{esc_history.get('level_code', 'UNKNOWN')}",
                level=esc_history["level"],
                level_code=esc_history.get("level_code"),
                escalated_to=esc_history["escalated_to"],
                reason=esc_history.get("reason"),
                hours_since_creation=hours_open,
            )
        )
    
    # Add resolution event if resolved
    if complaint.resolved_at or complaint.status in ("RESOLVED", "CLOSED"):
        timeline.append(
            EscalationTimelineItem(
                timestamp=(complaint.resolved_at or datetime.utcnow()).isoformat(),
                event_type="resolved",
                hours_since_creation=hours_open,
            )
        )
    
    # Sort by timestamp
    timeline.sort(key=lambda x: x.timestamp)
    
    return EscalationTimelineResponse(
        ticket_id=str(ticket_uuid),
        created_at=complaint.created_at.isoformat() if complaint.created_at else None,
        timeline=timeline,
        current_level=status["current_level"],
        current_status="resolved" if status["is_resolved"] else "open",
        stage=status["current_level_name"],
    )


@router.post("/escalations/{ticket_id}/manual")
def manual_escalation(
    ticket_id: str,
    reason: str = "manual",
    db: Session = Depends(get_db),
    current_client=Depends(require_api_key),
):
    """
    Manually escalate a ticket to the next level.

    Allowed only for authorized users.
    Stores escalation reason for audit trail.

    Example:
    ```
    POST /api/v1/compliance/escalations/550e8400-e29b-41d4-a716-446655440000/manual
    {
      "reason": "customer_escalation"
    }
    ```

    Response:
    ```json
    {
      "success": true,
      "escalation": {
        "id": "esc-id-1",
        "level": 2,
        "escalated_to": "ombudsman_staff@rbi",
        "created_at": "2026-04-01T15:30:00Z"
      }
    }
    ```
    """
    try:
        ticket_uuid = UUID(ticket_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ticket_id format")

    complaint = db.query(Complaint).filter(
        Complaint.id == ticket_uuid,
        Complaint.client_id == current_client.id,
    ).first()

    if not complaint:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if complaint.resolution_status == "resolved" or complaint.status in ("RESOLVED", "CLOSED"):
        raise HTTPException(status_code=400, detail="Cannot escalate resolved ticket")

    try:
        engine = EscalationEngine(db)
        escalation = engine.escalate(
            complaint,
            reason="manual",
            escalated_by=f"{current_client.name}",
            metadata={"user_reason": reason},
        )

        return {
            "success": True,
            "escalation": {
                "id": str(escalation.id),
                "level": escalation.level,
                "escalated_to": escalation.escalated_to,
                "created_at": escalation.created_at.isoformat() if escalation.created_at else None,
            },
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
