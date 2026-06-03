"""Named entity extraction from complaint text via Gemini structured output."""
from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx

from app.utils.logging import get_logger

logger = get_logger(__name__)

_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.5-flash-lite:generateContent"
)

_ORDER_ID_RE = re.compile(r"\b[A-Z]{2,5}[-_]?\d{4,12}\b")

_PROMPT_TEMPLATE = """Extract named entities from the following customer complaint text.
Return ONLY a valid JSON object with these exact keys:
- "products": list of product or service names mentioned (strings)
- "locations": list of cities, regions, or countries mentioned (strings)
- "employees": list of staff or agent names mentioned (strings)
- "order_ids": list of order numbers, ticket IDs, or reference numbers (strings)
- "dates": list of dates mentioned, normalized to YYYY-MM-DD format where possible (strings)

Rules:
- Return empty lists [] for categories with no entities found
- Do not include generic words like "product", "order", "service" — only specific names
- Normalize dates relative to today ({today})
- Extract only entities explicitly mentioned, not inferred

Complaint text:
{text}

JSON:"""


def _parse_entity_response(raw: dict[str, Any]) -> dict[str, list[str]]:
    try:
        text = raw["candidates"][0]["content"]["parts"][0]["text"].strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = re.sub(r"^```[a-z]*\n?", "", text)
            text = re.sub(r"\n?```$", "", text)
        data = json.loads(text)
    except Exception:
        return {"products": [], "locations": [], "employees": [], "order_ids": [], "dates": []}

    result: dict[str, list[str]] = {}
    for key in ("products", "locations", "employees", "order_ids", "dates"):
        val = data.get(key, [])
        result[key] = [str(v).strip() for v in val if v and str(v).strip()] if isinstance(val, list) else []
    return result


def _enrich_order_ids(text: str, order_ids: list[str]) -> list[str]:
    """Also run a regex pass to catch order IDs the LLM might have missed."""
    regex_hits = _ORDER_ID_RE.findall(text)
    combined = list({oid.upper() for oid in order_ids + regex_hits})
    return combined


def extract_entities_sync(text: str, api_key: str | None = None) -> dict[str, list[str]]:
    """
    Synchronous extraction — calls Gemini and returns entity dict.
    Returns empty lists on any failure (never raises).
    """
    api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
    if not api_key or not text.strip():
        return {"products": [], "locations": [], "employees": [], "order_ids": [], "dates": []}

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    prompt = _PROMPT_TEMPLATE.format(text=text[:3000], today=today)

    try:
        resp = httpx.post(
            _GEMINI_URL,
            params={"key": api_key},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0, "maxOutputTokens": 512},
            },
            timeout=8.0,
        )
        resp.raise_for_status()
        entities = _parse_entity_response(resp.json())
    except Exception as exc:
        logger.warning("Entity extraction failed: %s", exc)
        entities = {"products": [], "locations": [], "employees": [], "order_ids": [], "dates": []}

    entities["order_ids"] = _enrich_order_ids(text, entities.get("order_ids", []))
    return entities


def store_entities(db, complaint_id: uuid.UUID, entities: dict[str, list[str]]) -> int:
    """Persist extracted entities to complaint_entities table. Returns count stored."""
    from app.db.models import ComplaintEntity

    stored = 0
    for entity_type, values in entities.items():
        for value in values:
            if not value.strip():
                continue
            existing = (
                db.query(ComplaintEntity)
                .filter(
                    ComplaintEntity.complaint_id == complaint_id,
                    ComplaintEntity.entity_type == entity_type,
                    ComplaintEntity.entity_value == value,
                )
                .first()
            )
            if existing:
                continue
            ent = ComplaintEntity(
                complaint_id=complaint_id,
                entity_type=entity_type,
                entity_value=value,
                confidence=0.85,
            )
            db.add(ent)
            stored += 1
    return stored


def extract_and_store(db, complaint_id: uuid.UUID, text: str) -> dict[str, list[str]]:
    """Extract entities from text and persist them. Returns the entity dict."""
    from app.config import get_settings
    api_key = get_settings().gemini_api_key if hasattr(get_settings(), "gemini_api_key") else os.environ.get("GEMINI_API_KEY", "")
    entities = extract_entities_sync(text, api_key=api_key)
    store_entities(db, complaint_id, entities)
    db.flush()
    return entities
