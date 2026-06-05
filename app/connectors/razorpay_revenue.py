"""Razorpay revenue connector — pulls actual customer lifetime payments.

Auth: credentials_encrypted must contain JSON:
  {"key_id": "rzp_live_...", "key_secret": "..."}

Strategy:
  Razorpay doesn't offer a "sum all payments for email X" query in one call.
  We fetch recent payments in batches (up to 2 years) and group by email.
  This one-time bulk fetch is cached per sync run, so per-customer lookups
  reuse the in-memory map.

  For ongoing syncs (daily), only the delta since last sync is fetched
  using the `from` timestamp parameter.

Returns: dict {email: total_captured_amount_inr}
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

_RAZORPAY_BASE = "https://api.razorpay.com/v1"
_PER_PAGE = 100
_MAX_PAGES = 50  # 50 × 100 = 5,000 payments per sync run


def _auth(key_id: str, key_secret: str):
    return (key_id, key_secret)


def fetch_payments_bulk(
    key_id: str,
    key_secret: str,
    since: datetime | None = None,
) -> dict[str, float]:
    """Return {email: total_captured_inr} by fetching recent Razorpay payments.

    `since` defaults to 2 years ago if not provided.
    """
    if since is None:
        since = datetime.now(timezone.utc) - timedelta(days=730)

    from_ts = int(since.timestamp())
    email_totals: dict[str, float] = {}
    params: dict[str, Any] = {
        "count": _PER_PAGE,
        "from": from_ts,
    }

    pages = 0
    while pages < _MAX_PAGES:
        resp = httpx.get(
            f"{_RAZORPAY_BASE}/payments",
            params=params,
            auth=_auth(key_id, key_secret),
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("items", [])

        for payment in items:
            if payment.get("status") != "captured":
                continue
            email = (payment.get("email") or "").strip().lower()
            if not email:
                continue
            # Razorpay amounts are in paise (1/100 rupee)
            amount_paise = payment.get("amount", 0)
            amount_inr = round(amount_paise / 100.0, 2)
            email_totals[email] = round(email_totals.get(email, 0.0) + amount_inr, 2)

        pages += 1
        # Razorpay uses count + skip for pagination
        if len(items) < _PER_PAGE:
            break
        params["skip"] = params.get("skip", 0) + _PER_PAGE

    return email_totals


def lookup_customer_revenue(
    key_id: str,
    key_secret: str,
    email: str,
    bulk_cache: dict[str, float] | None = None,
) -> float:
    """Return total captured payments (INR) for a customer email.

    `bulk_cache` is a pre-computed {email: amount} dict from fetch_payments_bulk.
    Pass it to avoid making repeated API calls for each customer.
    """
    if bulk_cache is not None:
        return bulk_cache.get(email.lower().strip(), 0.0)
    # Fallback: run bulk fetch and look up
    cache = fetch_payments_bulk(key_id, key_secret)
    return cache.get(email.lower().strip(), 0.0)


def get_credentials(credentials_encrypted: str | None) -> dict[str, str]:
    try:
        return json.loads(credentials_encrypted or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}


def validate_credentials(key_id: str, key_secret: str) -> bool:
    """Verify credentials work by calling the Razorpay account endpoint."""
    try:
        resp = httpx.get(
            f"{_RAZORPAY_BASE}/payments",
            params={"count": 1},
            auth=_auth(key_id, key_secret),
            timeout=8.0,
        )
        return resp.status_code in (200, 400)  # 400 = bad params but auth OK
    except Exception:
        return False
