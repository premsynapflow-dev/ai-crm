"""Stripe revenue connector — pulls actual customer lifetime spend.

Auth: credentials_encrypted must contain JSON:
  {"api_key": "sk_live_..."}

How it works:
  1. For each SynapFlow customer email, query Stripe for matching customers.
  2. Sum all succeeded charge amounts across all Stripe customer IDs found for that email.
  3. Return a dict: {email: total_lifetime_spend_in_rupees (or base currency)}
"""
from __future__ import annotations

import json
import os
from typing import Any

import httpx

_STRIPE_BASE = "https://api.stripe.com/v1"
_PER_PAGE = 100
_MAX_CHARGES_PER_CUSTOMER = 1000

# USD → INR conversion rate used for display/risk calculations only.
# This is approximate and drifts from the live rate — set STRIPE_USD_INR_RATE in your
# environment to override.  For production accuracy, use a currency conversion API.
_USD_INR_RATE = float(os.getenv("STRIPE_USD_INR_RATE", "84.0"))


def _headers(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


def _rupees(amount_cents: int, currency: str) -> float:
    """Convert Stripe amount to INR float.

    Stripe stores amounts in the smallest unit for most currencies.
    INR is a zero-decimal currency in Stripe (amounts are in rupees directly).
    USD amounts are in cents → multiply by ~83 (approximate; use for display only).
    """
    currency = currency.lower()
    if currency == "inr":
        return float(amount_cents)
    if currency == "usd":
        return round(float(amount_cents) / 100 * _USD_INR_RATE, 2)
    # For any other currency, return raw integer value (zero-decimal) or paise→rupees
    return float(amount_cents)


def _paginate_charges(api_key: str, stripe_customer_id: str) -> list[dict]:
    """Fetch all succeeded charges for a Stripe customer."""
    charges: list[dict] = []
    params: dict[str, Any] = {
        "customer": stripe_customer_id,
        "limit": _PER_PAGE,
        "expand[]": "data.customer",
    }
    while True:
        resp = httpx.get(f"{_STRIPE_BASE}/charges", params=params, headers=_headers(api_key), timeout=15.0)
        resp.raise_for_status()
        data = resp.json()
        for charge in data.get("data", []):
            if charge.get("status") == "succeeded" and not charge.get("refunded"):
                charges.append(charge)
        if not data.get("has_more") or len(charges) >= _MAX_CHARGES_PER_CUSTOMER:
            break
        charges_list = data.get("data", [])
        if charges_list:
            params["starting_after"] = charges_list[-1]["id"]
        else:
            break
    return charges


def lookup_customer_revenue(api_key: str, email: str) -> float:
    """Return total lifetime spend (INR) for a customer email in Stripe."""
    # Find all Stripe customers with this email
    resp = httpx.get(
        f"{_STRIPE_BASE}/customers",
        params={"email": email, "limit": 10},
        headers=_headers(api_key),
        timeout=10.0,
    )
    resp.raise_for_status()
    stripe_customers = resp.json().get("data", [])
    if not stripe_customers:
        return 0.0

    total = 0.0
    for sc in stripe_customers:
        for charge in _paginate_charges(api_key, sc["id"]):
            total += _rupees(charge.get("amount", 0), charge.get("currency", "inr"))
    return round(total, 2)


def get_credentials(credentials_encrypted: str | None) -> dict[str, str]:
    try:
        return json.loads(credentials_encrypted or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}


def validate_credentials(api_key: str) -> bool:
    """Verify the API key works by hitting /v1/account."""
    try:
        resp = httpx.get(f"{_STRIPE_BASE}/account", headers=_headers(api_key), timeout=8.0)
        return resp.status_code == 200
    except Exception:
        return False
