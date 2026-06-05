"""Revenue sync orchestration — pulls actual customer value from Stripe / Razorpay.

Sync flow per client:
  1. Load all ChannelConnections with channel_type in ("stripe_revenue", "razorpay_revenue").
  2. For Razorpay: do one bulk payment fetch → build email→INR map.
  3. For Stripe: per-customer lookup by email (Stripe supports email search).
  4. For each Customer, set actual_customer_value and customer_value_source = "actual".
  5. Persist changes and refresh churn/revenue-risk metrics.

Legal: This module only calls payment processors to retrieve revenue data about
the client's *own* customers. No PII is sent to third-party AI services here.
Customer emails are used solely as lookup keys against the client's own accounts.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import ChannelConnection, Customer
from app.utils.logging import get_logger

logger = get_logger(__name__)


def _load_creds(conn: ChannelConnection) -> dict[str, str]:
    try:
        return json.loads(conn.credentials_encrypted or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}


def _sync_stripe(
    db: Session,
    client_id: str,
    conn: ChannelConnection,
) -> dict[str, Any]:
    """Sync customer revenue values from a Stripe connection."""
    from app.connectors.stripe_revenue import get_credentials, lookup_customer_revenue, validate_credentials

    creds = get_credentials(conn.credentials_encrypted)
    api_key = creds.get("api_key", "")
    if not api_key:
        return {"error": "No Stripe api_key in credentials", "updated": 0}

    if not validate_credentials(api_key):
        return {"error": "Invalid Stripe credentials", "updated": 0}

    customers = (
        db.query(Customer)
        .filter(
            Customer.client_id == client_id,
            Customer.is_master.is_(True),
            Customer.primary_email.isnot(None),
        )
        .all()
    )

    updated = 0
    errors = 0
    for customer in customers:
        try:
            revenue = lookup_customer_revenue(api_key, customer.primary_email)
            if revenue > 0:
                customer.actual_customer_value = revenue
                customer.customer_value_source = "actual"
                customer.revenue_risk_confidence = "high"
                customer.lifetime_value = revenue
                updated += 1
        except Exception as exc:
            logger.debug("Stripe lookup failed for %s: %s", customer.primary_email, exc)
            errors += 1

    db.flush()
    return {"updated": updated, "skipped": len(customers) - updated, "errors": errors}


def _sync_razorpay(
    db: Session,
    client_id: str,
    conn: ChannelConnection,
) -> dict[str, Any]:
    """Sync customer revenue values from a Razorpay connection."""
    from app.connectors.razorpay_revenue import (
        fetch_payments_bulk,
        get_credentials,
        validate_credentials,
    )

    creds = get_credentials(conn.credentials_encrypted)
    key_id = creds.get("key_id", "")
    key_secret = creds.get("key_secret", "")
    if not key_id or not key_secret:
        return {"error": "Missing key_id or key_secret in credentials", "updated": 0}

    if not validate_credentials(key_id, key_secret):
        return {"error": "Invalid Razorpay credentials", "updated": 0}

    # Bulk fetch: one API call series covers all customers
    try:
        bulk_cache = fetch_payments_bulk(key_id, key_secret)
    except Exception as exc:
        return {"error": f"Razorpay bulk fetch failed: {exc}", "updated": 0}

    customers = (
        db.query(Customer)
        .filter(
            Customer.client_id == client_id,
            Customer.is_master.is_(True),
            Customer.primary_email.isnot(None),
        )
        .all()
    )

    updated = 0
    for customer in customers:
        email_key = (customer.primary_email or "").lower().strip()
        revenue = bulk_cache.get(email_key, 0.0)
        if revenue > 0:
            customer.actual_customer_value = revenue
            customer.customer_value_source = "actual"
            customer.revenue_risk_confidence = "high"
            customer.lifetime_value = revenue
            updated += 1

    db.flush()
    return {
        "updated": updated,
        "skipped": len(customers) - updated,
        "bulk_emails_found": len(bulk_cache),
    }


def sync_revenue_for_client(db: Session, client_id: str) -> dict[str, Any]:
    """Run all configured revenue syncs for a client.

    Returns a summary of what was done.
    """
    connections = (
        db.query(ChannelConnection)
        .filter(
            ChannelConnection.client_id == client_id,
            ChannelConnection.channel_type.in_(["stripe_revenue", "razorpay_revenue"]),
            ChannelConnection.status == "active",
        )
        .all()
    )

    if not connections:
        return {
            "status": "no_connections",
            "message": "No revenue integrations connected. Add Stripe or Razorpay in Settings → Connections.",
            "results": [],
        }

    results = []
    total_updated = 0

    for conn in connections:
        try:
            if conn.channel_type == "stripe_revenue":
                result = _sync_stripe(db, client_id, conn)
            elif conn.channel_type == "razorpay_revenue":
                result = _sync_razorpay(db, client_id, conn)
            else:
                continue
            result["provider"] = conn.channel_type
            result["connection_id"] = str(conn.id)
            results.append(result)
            total_updated += result.get("updated", 0)
        except Exception as exc:
            logger.warning("Revenue sync failed for %s connection %s: %s", conn.channel_type, conn.id, exc)
            results.append({
                "provider": conn.channel_type,
                "connection_id": str(conn.id),
                "error": str(exc),
                "updated": 0,
            })

    if total_updated > 0:
        try:
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.error("Revenue sync commit failed: %s", exc)
            return {"status": "error", "message": str(exc), "results": results}

    return {
        "status": "ok",
        "synced_at": datetime.now(timezone.utc).isoformat(),
        "total_customers_updated": total_updated,
        "results": results,
    }
