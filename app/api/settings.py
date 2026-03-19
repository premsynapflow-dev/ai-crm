from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_current_client, get_current_client_user, serialize_client_user
from app.db.models import Client, ClientUser
from app.db.session import get_db

router = APIRouter(prefix="/api", tags=["settings"])


@router.get("/settings")
def get_settings_summary(
    db: Session = Depends(get_db),
    user: ClientUser = Depends(get_current_client_user),
    client: Client = Depends(get_current_client),
):
    members = (
        db.query(ClientUser)
        .filter(ClientUser.client_id == client.id)
        .order_by(ClientUser.created_at.asc())
        .all()
    )

    return {
        "profile": serialize_client_user(user, client),
        "company": {
            "name": client.name,
            "plan_id": client.plan_id,
            "monthly_ticket_limit": client.monthly_ticket_limit,
            "created_at": client.created_at.isoformat() if client.created_at else None,
        },
        "api_key": client.api_key,
        "webhooks": (
            [
                {
                    "id": "slack",
                    "url": client.slack_webhook_url,
                    "events": [
                        "complaint.created",
                        "complaint.escalated",
                        "complaint.resolved",
                    ],
                    "status": "active",
                }
            ]
            if client.slack_webhook_url
            else []
        ),
        "team_members": [
            {
                "id": str(member.id),
                "name": serialize_client_user(member, client)["name"],
                "email": member.email,
                "role": "Owner" if member.id == user.id else "Member",
                "status": "active",
                "created_at": member.created_at.isoformat() if member.created_at else None,
            }
            for member in members
        ],
    }
