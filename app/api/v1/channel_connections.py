import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import get_current_client
from app.db.models import ChannelConnection, Client
from app.db.session import get_db

router = APIRouter(prefix="/api/v1", tags=["channel-connections"])


class ConnectChannelRequest(BaseModel):
    channel_type: str
    account_identifier: str | None = None
    credentials: dict[str, Any] = {}
    metadata: dict[str, Any] = {}


@router.post("/channel-connections", status_code=201)
def create_channel_connection(
    body: ConnectChannelRequest,
    client: Client = Depends(get_current_client),
    db: Session = Depends(get_db),
):
    """Generic endpoint to register any connector type with its credentials."""
    conn = ChannelConnection(
        client_id=client.id,
        channel_type=body.channel_type,
        account_identifier=body.account_identifier,
        credentials_encrypted=json.dumps(body.credentials),
        metadata_json=body.metadata,
        status="active",
        poll_enabled=True,
        poll_interval_minutes=body.metadata.get("poll_interval_minutes", 60),
    )
    db.add(conn)
    db.commit()
    db.refresh(conn)
    return {
        "id": str(conn.id),
        "channel_type": conn.channel_type,
        "account_identifier": conn.account_identifier,
        "status": conn.status,
        "created_at": conn.created_at.isoformat() if conn.created_at else None,
    }


@router.get("/channel-connections")
def list_channel_connections(
    type: str | None = Query(default=None, alias="type"),
    client: Client = Depends(get_current_client),
    db: Session = Depends(get_db),
):
    q = db.query(ChannelConnection).filter(ChannelConnection.client_id == client.id)
    if type:
        q = q.filter(ChannelConnection.channel_type == type)
    conns = q.order_by(ChannelConnection.created_at.desc()).all()
    return [
        {
            "id": str(c.id),
            "channel_type": c.channel_type,
            "account_identifier": c.account_identifier,
            "status": c.status,
            "metadata": {
                k: v
                for k, v in (c.metadata_json or {}).items()
                if k not in {"access_token", "refresh_token"}
            },
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in conns
    ]


@router.delete("/channel-connections/{connection_id}", status_code=204)
def delete_channel_connection(
    connection_id: str,
    client: Client = Depends(get_current_client),
    db: Session = Depends(get_db),
):
    conn = (
        db.query(ChannelConnection)
        .filter(
            ChannelConnection.id == connection_id,
            ChannelConnection.client_id == client.id,
        )
        .first()
    )
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    db.delete(conn)
    db.commit()
