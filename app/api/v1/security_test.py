from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_current_client
from app.db.models import Client, Complaint
from app.db.session import get_db

router = APIRouter(prefix="/api/v1/security", tags=["security-test"])


@router.get("/test-isolation")
def test_client_isolation(
    client: Client = Depends(get_current_client),
    db: Session = Depends(get_db),
):
    """
    Return a client-scoped complaint count to verify tenant isolation wiring.

    This endpoint intentionally does not expose global complaint totals because
    cross-tenant aggregates are still sensitive in a multi-tenant system.
    """
    my_complaints = (
        db.query(Complaint)
        .filter(Complaint.client_id == client.id)
        .count()
    )

    return {
        "client_id": str(client.id),
        "my_complaints_count": my_complaints,
        "isolation_scope": "client_only",
        "isolation_working": True,
        "message": f"You can only access your own {my_complaints} complaints.",
    }
