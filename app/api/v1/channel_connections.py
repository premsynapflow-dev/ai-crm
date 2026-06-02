from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import get_current_client
from app.db.models import ChannelConnection, Client
from app.db.session import get_db

router = APIRouter(prefix="/api/v1", tags=["channel-connections"])


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
