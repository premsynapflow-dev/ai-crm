"""file_mapper.py — parse CSV / Excel / JSON uploads and normalize to IncomingMessage.

Supports four data types:
  - reviews          : product/service reviews (may have star ratings)
  - support_tickets  : helpdesk ticket exports
  - complaints       : complaint/feedback exports
  - refunds          : return/refund order exports

The mapper is intentionally forgiving: it tries many column-name aliases and
degrades gracefully when expected columns are absent.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from app.services.unified_ingestion import IncomingMessage
from app.utils.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Column alias tables — order matters: first match wins
# ---------------------------------------------------------------------------

_TEXT_ALIASES = [
    "message", "body", "text", "content", "description", "details",
    "review", "review_text", "feedback", "comment", "notes",
    "complaint", "complaint_text", "reason", "return_reason", "refund_reason",
    "summary", "issue",
]

_TITLE_ALIASES = [
    "title", "subject", "headline",
]

_EMAIL_ALIASES = [
    "email", "customer_email", "user_email", "reporter_email",
    "submitter_email", "contact_email", "buyer_email",
]

_NAME_ALIASES = [
    "name", "customer_name", "user_name", "full_name", "author",
    "reviewer", "reporter", "submitter", "contact_name", "buyer_name",
]

_CATEGORY_ALIASES = [
    "category", "type", "department", "tag", "product", "product_name",
    "service", "topic",
]

_PRIORITY_ALIASES = [
    "priority", "severity", "urgency",
]

_RATING_ALIASES = [
    "rating", "stars", "score", "star_rating",
]

_DATE_ALIASES = [
    "created_at", "date", "received_at", "timestamp", "submitted_at",
    "reviewed_at", "created", "opened_at",
]

_EXTERNAL_ID_ALIASES = [
    "id", "external_id", "ticket_id", "issue_id", "number", "ref",
    "complaint_id", "order_id", "transaction_id", "reference",
]

_ORDER_ALIASES = [
    "order_id", "order_number", "transaction_id", "reference_id",
]

_AMOUNT_ALIASES = [
    "amount", "refund_amount", "price", "value", "total",
]

_PRODUCT_ALIASES = [
    "product", "product_name", "item", "item_name", "sku",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalise_headers(raw_headers: list[str]) -> dict[str, str]:
    """Return {normalized_key: original_key} for each column."""
    return {h.strip().lower().replace(" ", "_"): h for h in raw_headers if h}


def _find(row: dict[str, str], aliases: list[str]) -> str:
    for alias in aliases:
        v = row.get(alias, "").strip()
        if v:
            return v
    return ""


def _parse_timestamp(value: str) -> datetime:
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%m/%d/%Y",
    ):
        try:
            dt = datetime.strptime(value.strip(), fmt)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return datetime.now(timezone.utc)


def _priority_int(value: str) -> int | None:
    mapping = {
        "critical": 5, "p0": 5, "urgent": 5,
        "high": 4, "p1": 4,
        "medium": 3, "p2": 3, "normal": 3,
        "low": 2, "p3": 2,
        "trivial": 1, "p4": 1,
    }
    v = value.strip().lower()
    if v in mapping:
        return mapping[v]
    try:
        return max(1, min(5, int(v)))
    except ValueError:
        return None


def _rating_to_urgency(value: str) -> float:
    """Convert star rating (1–5 or 0–10) to urgency 0.0–1.0 (inverted: 1 star = high urgency)."""
    try:
        r = float(value)
        if r > 5:
            r = r / 10.0  # 0–10 scale
        r = max(0.0, min(5.0, r))
        return round(1.0 - ((r - 1.0) / 4.0), 2)
    except ValueError:
        return 0.5


def _dedup_key(text_body: str, email: str, client_id: str, row_num: int) -> str:
    prefix = (email + text_body[:80]) if email else text_body[:100]
    return hashlib.sha256(f"{client_id}:{prefix}:{row_num}".encode()).hexdigest()


def _build_message(data_type: str, row: dict[str, str], row_num: int) -> tuple[str, dict[str, Any]]:
    """
    Build the message_text and extra metadata dict from a row.
    Returns (message_text, extra) where extra carries optional fields.
    """
    text = _find(row, _TEXT_ALIASES)
    title = _find(row, _TITLE_ALIASES)
    email = _find(row, _EMAIL_ALIASES)
    name = _find(row, _NAME_ALIASES)
    category = _find(row, _CATEGORY_ALIASES)
    priority_raw = _find(row, _PRIORITY_ALIASES)
    date_raw = _find(row, _DATE_ALIASES)
    ext_id = _find(row, _EXTERNAL_ID_ALIASES)

    extra: dict[str, Any] = {}
    if email:
        extra["email"] = email
    if name:
        extra["name"] = name
    if category:
        extra["hint_category"] = category
    if priority_raw:
        p = _priority_int(priority_raw)
        if p:
            extra["hint_priority"] = p
    if date_raw:
        extra["received_at"] = _parse_timestamp(date_raw)
    if ext_id:
        extra["external_id"] = ext_id

    if data_type == "reviews":
        rating_raw = _find(row, _RATING_ALIASES)
        if rating_raw:
            urgency = _rating_to_urgency(rating_raw)
            extra["hint_urgency"] = urgency
            stars = rating_raw
            prefix = f"Customer Review ({stars} stars): " if title else f"Review ({stars} stars): "
        else:
            prefix = f"Customer Review: " if not title else ""
        if title:
            prefix = f"{prefix}{title}\n\n"
        body = (prefix + text) if text else title
        if not body:
            return "", {}
        return body.strip(), extra

    elif data_type == "support_tickets":
        if title and text:
            body = f"{title}\n\n{text}"
        elif title:
            body = title
        elif text:
            body = text
        else:
            return "", {}
        return body.strip(), extra

    elif data_type == "complaints":
        if title and text:
            body = f"{title}\n\n{text}"
        elif title:
            body = title
        elif text:
            body = text
        else:
            return "", {}
        extra.setdefault("hint_category", "general")
        return body.strip(), extra

    elif data_type == "refunds":
        order_id = _find(row, _ORDER_ALIASES)
        amount = _find(row, _AMOUNT_ALIASES)
        product = _find(row, _PRODUCT_ALIASES)

        parts = []
        if order_id:
            parts.append(f"Order #{order_id}")
        if product:
            parts.append(f"Product: {product}")
        if amount:
            parts.append(f"Amount: {amount}")

        reason = text
        if not reason and title:
            reason = title

        if parts and reason:
            body = f"Return/Refund Request — {', '.join(parts)}\n\nReason: {reason}"
        elif parts:
            body = f"Return/Refund Request — {', '.join(parts)}"
        elif reason:
            body = f"Return/Refund Request: {reason}"
        else:
            return "", {}

        extra["hint_category"] = "refund"
        extra["hint_priority"] = extra.get("hint_priority", 3)
        if order_id and not extra.get("external_id"):
            extra["external_id"] = order_id
        return body.strip(), extra

    return text.strip() if text else "", extra


# ---------------------------------------------------------------------------
# Row-dict normalisation
# ---------------------------------------------------------------------------

def _normalise_row(raw_row: dict, headers_map: dict[str, str]) -> dict[str, str]:
    """Normalise row keys to lowercase-underscored and strip values."""
    out: dict[str, str] = {}
    for raw_key, value in raw_row.items():
        if raw_key is None:
            continue
        norm = raw_key.strip().lower().replace(" ", "_").replace("-", "_")
        out[norm] = str(value or "").strip()
    return out


# ---------------------------------------------------------------------------
# Public parse functions
# ---------------------------------------------------------------------------

def parse_file(
    content: bytes,
    filename: str,
    data_type: str,
    client_id: str,
) -> tuple[list[IncomingMessage], list[dict[str, Any]]]:
    """
    Parse uploaded file bytes into IncomingMessage objects.

    Returns:
        (messages, errors) — errors is a list of {row, reason} dicts.
    """
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "csv"

    if ext == "json":
        rows = _parse_json_rows(content)
    elif ext in ("xlsx", "xls"):
        rows = _parse_excel_rows(content)
    else:
        rows = _parse_csv_rows(content)

    return _map_rows(rows, data_type, client_id)


def _parse_csv_rows(content: bytes) -> list[dict]:
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig", errors="replace")))
    return list(reader)


def _parse_excel_rows(content: bytes) -> list[dict]:
    try:
        import openpyxl  # lazy import — only used for xlsx
    except ImportError:
        raise ValueError("openpyxl is required for Excel uploads. Install it with: pip install openpyxl")

    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    headers = [str(h or "").strip() for h in rows[0]]
    result = []
    for row in rows[1:]:
        d = {}
        for h, v in zip(headers, row):
            if h:
                d[h] = str(v) if v is not None else ""
        result.append(d)
    wb.close()
    return result


def _parse_json_rows(content: bytes) -> list[dict]:
    try:
        data = json.loads(content.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"Invalid JSON: {exc}")

    if isinstance(data, list):
        return data
    # Accept {"data": [...]} or {"records": [...]} or {"items": [...]}
    for key in ("data", "records", "items", "complaints", "tickets", "reviews"):
        if isinstance(data.get(key), list):
            return data[key]
    raise ValueError(
        "JSON must be an array of objects, or an object with a "
        "'data', 'records', or 'items' array."
    )


def _map_rows(
    raw_rows: list[dict],
    data_type: str,
    client_id: str,
) -> tuple[list[IncomingMessage], list[dict[str, Any]]]:
    messages: list[IncomingMessage] = []
    errors: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    for row_num, raw_row in enumerate(raw_rows, start=2):
        if not isinstance(raw_row, dict):
            errors.append({"row": row_num, "reason": "Row is not an object"})
            continue

        row = _normalise_row(raw_row, {})

        try:
            body, extra = _build_message(data_type, row, row_num)
        except Exception as exc:
            errors.append({"row": row_num, "reason": f"Mapping error: {exc}"})
            continue

        if not body:
            errors.append({"row": row_num, "reason": "No usable text found in row"})
            continue

        email = extra.get("email")
        dedup_key = _dedup_key(body, email or "", client_id, row_num)
        if dedup_key in seen_keys:
            errors.append({"row": row_num, "reason": "Duplicate row within this file"})
            continue
        seen_keys.add(dedup_key)

        ext_id = extra.get("external_id") or dedup_key
        received_at = extra.get("received_at", datetime.now(timezone.utc))

        channel_source = {
            "reviews": "review",
            "support_tickets": "support_ticket",
            "complaints": "complaint_export",
            "refunds": "refund_export",
        }.get(data_type, "upload")

        msg = IncomingMessage(
            client_id=client_id,
            channel=channel_source,
            external_message_id=ext_id,
            external_thread_id=ext_id,
            sender_id=email or None,
            sender_name=extra.get("name") or None,
            message_text=body,
            timestamp=received_at,
            direction="inbound",
            status="received",
            raw_payload={
                "source": "upload_intelligence",
                "data_type": data_type,
                "csv_row": row_num,
                "dedup_key": dedup_key,
                "hint_category": extra.get("hint_category"),
                "hint_priority": extra.get("hint_priority"),
                "hint_urgency": extra.get("hint_urgency"),
            },
        )
        messages.append(msg)

    return messages, errors


def detect_format(filename: str) -> str:
    """Return 'csv', 'xlsx', or 'json' based on filename extension."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext == "json":
        return "json"
    if ext in ("xlsx", "xls"):
        return "xlsx"
    return "csv"
