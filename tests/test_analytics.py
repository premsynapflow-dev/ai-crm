import json
import uuid
from datetime import datetime, timezone

from app.db.models import Complaint
from app.services.analytics import analytics_overview


def test_analytics_overview_is_json_serializable(test_db, test_client_record):
    """Analytics overview should return JSON-serializable data."""
    # Create complaints with different sources
    complaints = [
        Complaint(
            id=uuid.uuid4(),
            client_id=test_client_record.id,
            ticket_id="TKT-AN-001",
            thread_id="TH-AN-001",
            summary="Issue 1",
            category="general",
            sentiment=0.1,
            priority=2,
            source="email",
            created_at=datetime.now(timezone.utc),
        ),
        Complaint(
            id=uuid.uuid4(),
            client_id=test_client_record.id,
            ticket_id="TKT-AN-002",
            thread_id="TH-AN-002",
            summary="Issue 2",
            category="general",
            sentiment=0.2,
            priority=3,
            source="web",
            created_at=datetime.now(timezone.utc),
        ),
    ]
    test_db.add_all(complaints)
    test_db.commit()

    overview = analytics_overview(test_db, test_client_record.id)

    # Ensure the overview is JSON serializable (this is what broke before)
    json.dumps(overview)

    assert "sources" in overview
    assert isinstance(overview["sources"], list)
    assert all(isinstance(item, dict) for item in overview["sources"])
