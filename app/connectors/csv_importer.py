"""CSV bulk import: streams a CSV file and normalizes each row to IncomingMessage."""
from __future__ import annotations

import csv
import hashlib
import io
import uuid
from datetime import datetime, timezone
from typing import Any

from app.services.unified_ingestion import IncomingMessage

REQUIRED_COLUMNS = {"message"}
OPTIONAL_COLUMNS = {
    "customer_email", "customer_phone", "customer_name",
    "source", "priority", "category", "received_at", "external_id",
}
ALL_COLUMNS = REQUIRED_COLUMNS | OPTIONAL_COLUMNS


def _parse_timestamp(value: str) -> datetime:
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value.strip(), fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return datetime.now(timezone.utc)


def _dedup_key(row: dict[str, str], client_id: str) -> str:
    ext_id = row.get("external_id", "").strip()
    if ext_id:
        return f"{client_id}:csv:{ext_id}"
    msg_prefix = row.get("message", "")[:100]
    email = row.get("customer_email", "")
    return hashlib.sha256(f"{client_id}:{email}:{msg_prefix}".encode()).hexdigest()


def validate_headers(headers: list[str]) -> list[str]:
    """Return list of validation errors; empty list means headers are valid."""
    errors = []
    missing = REQUIRED_COLUMNS - {h.strip().lower() for h in headers}
    if missing:
        errors.append(f"Missing required columns: {', '.join(sorted(missing))}")
    return errors


def parse_csv_rows(
    content: bytes,
    client_id: str,
) -> tuple[list[IncomingMessage], list[dict[str, Any]]]:
    """
    Parse CSV bytes into IncomingMessage objects.
    Returns (messages, errors) where errors is a list of {row, reason} dicts.
    """
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig", errors="replace")))
    headers = [h.strip().lower() for h in (reader.fieldnames or [])]
    header_errors = validate_headers(headers)
    if header_errors:
        raise ValueError(header_errors[0])

    messages: list[IncomingMessage] = []
    errors: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    for row_num, raw_row in enumerate(reader, start=2):
        row = {k.strip().lower(): (v or "").strip() for k, v in raw_row.items() if k}
        body = row.get("message", "").strip()
        if not body:
            errors.append({"row": row_num, "reason": "Empty message field"})
            continue

        dedup_key = _dedup_key(row, client_id)
        if dedup_key in seen_keys:
            errors.append({"row": row_num, "reason": "Duplicate row within this file"})
            continue
        seen_keys.add(dedup_key)

        ext_id = row.get("external_id", "").strip() or dedup_key
        received_at_str = row.get("received_at", "")
        received_at = _parse_timestamp(received_at_str) if received_at_str else datetime.now(timezone.utc)

        msg = IncomingMessage(
            client_id=client_id,
            channel=row.get("source", "csv") or "csv",
            external_message_id=ext_id,
            external_thread_id=ext_id,
            sender_id=row.get("customer_email") or None,
            sender_name=row.get("customer_name") or None,
            message_text=body,
            timestamp=received_at,
            direction="inbound",
            status="received",
            raw_payload={
                "source": "csv_import",
                "csv_row": row_num,
                "dedup_key": dedup_key,
            },
        )
        messages.append(msg)

    return messages, errors
