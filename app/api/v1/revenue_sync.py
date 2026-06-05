"""Revenue sync API — trigger Stripe/Razorpay customer value sync."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.models import ChannelConnection, Client
from app.db.session import get_db
from app.dependencies.auth import require_api_key
from app.services.revenue_sync import sync_revenue_for_client
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/revenue-sync", tags=["revenue-sync"])


class ValidateCredentialsRequest(BaseModel):
    channel_type: str
    credentials: dict


@router.post("/trigger")
def trigger_revenue_sync(
    db: Session = Depends(get_db),
    current_client: Client = Depends(require_api_key),
):
    """Run a revenue sync for all connected Stripe/Razorpay integrations.

    Fetches actual customer lifetime value from configured payment providers
    and updates Customer.actual_customer_value for matched customers.
    """
    client_id = str(current_client.id)
    try:
        result = sync_revenue_for_client(db, client_id)
        return result
    except Exception as exc:
        logger.error("Revenue sync trigger failed for client %s: %s", client_id, exc)
        raise HTTPException(status_code=500, detail=f"Sync failed: {exc}")


@router.get("/status")
def revenue_sync_status(
    db: Session = Depends(get_db),
    current_client: Client = Depends(require_api_key),
):
    """Return connected revenue integrations and customer coverage stats."""
    client_id = str(current_client.id)

    connections = (
        db.query(ChannelConnection)
        .filter(
            ChannelConnection.client_id == client_id,
            ChannelConnection.channel_type.in_(["stripe_revenue", "razorpay_revenue"]),
        )
        .all()
    )

    from app.db.models import Customer
    from sqlalchemy import func

    total_customers = (
        db.query(func.count(Customer.id))
        .filter(Customer.client_id == client_id, Customer.is_master.is_(True))
        .scalar()
        or 0
    )
    customers_with_actual = (
        db.query(func.count(Customer.id))
        .filter(
            Customer.client_id == client_id,
            Customer.is_master.is_(True),
            Customer.customer_value_source == "actual",
        )
        .scalar()
        or 0
    )

    return {
        "connections": [
            {
                "id": str(c.id),
                "channel_type": c.channel_type,
                "account_identifier": c.account_identifier,
                "status": c.status,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in connections
        ],
        "coverage": {
            "total_customers": total_customers,
            "customers_with_actual_value": customers_with_actual,
            "coverage_pct": round(customers_with_actual / max(total_customers, 1) * 100, 1),
        },
    }


@router.post("/validate")
def validate_revenue_credentials(
    body: ValidateCredentialsRequest,
    current_client: Client = Depends(require_api_key),
):
    """Validate Stripe or Razorpay credentials before saving."""
    try:
        if body.channel_type == "stripe_revenue":
            from app.connectors.stripe_revenue import validate_credentials
            ok = validate_credentials(body.credentials.get("api_key", ""))
        elif body.channel_type == "razorpay_revenue":
            from app.connectors.razorpay_revenue import validate_credentials
            ok = validate_credentials(
                body.credentials.get("key_id", ""),
                body.credentials.get("key_secret", ""),
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unknown channel_type: {body.channel_type}")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not ok:
        raise HTTPException(status_code=422, detail="Credential validation failed — check your API key")
    return {"valid": True}
