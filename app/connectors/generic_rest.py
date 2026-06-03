"""Generic configurable REST connector — covers ERP, SAP, Oracle, ServiceNow, BMC Remedy.

Full configuration lives in channel_connections.metadata_json:

{
  "base_url": "https://erp.company.com/api",
  "auth_type": "api_key|bearer|basic|none",
  "auth_config": {
      "header": "X-API-Key",            # for api_key
      "token": "secret",                # for api_key or bearer
      "username": "user",               # for basic
      "password": "pass"                # for basic
  },
  "list_endpoint": "/incidents?updatedAfter={cursor}&limit=100",
  "reply_endpoint": "/incidents/{id}/notes",
  "reply_body_template": {"note": "{body}"},
  "field_map": {
      "id": "incident_number",
      "body": "short_description",
      "customer_email": "caller_email",
      "created_at": "sys_created_on",
      "priority": "priority"
  },
  "cursor_field": "sys_created_on",
  "cursor_format": "iso|timestamp_ms|timestamp_s",
  "pagination": "none|page|cursor|offset",
  "page_param": "page",
  "page_size": 100,
  "results_key": "result",
  "next_page_key": "next_page_token",
  "priority_map": {"1": 1.0, "2": 0.75, "3": 0.45, "4": 0.2}
}
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
from typing import Any

import httpx

from app.connectors.base import BaseConnector
from app.connectors.registry import register
from app.services.unified_ingestion import IncomingMessage
from app.utils.logging import get_logger

logger = get_logger(__name__)

_DEFAULT_PRIORITY_URGENCY = {"1": 1.0, "2": 0.75, "3": 0.45, "4": 0.2, "5": 0.0}


def _build_auth_headers(auth_type: str, auth_config: dict) -> dict[str, str]:
    if auth_type == "api_key":
        header = auth_config.get("header", "X-API-Key")
        return {header: auth_config.get("token", "")}
    if auth_type == "bearer":
        return {"Authorization": f"Bearer {auth_config.get('token', '')}"}
    if auth_type == "basic":
        creds = base64.b64encode(
            f"{auth_config.get('username', '')}:{auth_config.get('password', '')}".encode()
        ).decode()
        return {"Authorization": f"Basic {creds}"}
    return {}


def _extract_field(record: dict, field_map: dict, field_name: str, default: Any = None) -> Any:
    mapped_key = field_map.get(field_name, field_name)
    # Support dot notation: "caller.email" → record["caller"]["email"]
    parts = mapped_key.split(".")
    val = record
    for part in parts:
        if not isinstance(val, dict):
            return default
        val = val.get(part, default)
    return val


def _parse_cursor(value: str | int | float | None, fmt: str) -> datetime | None:
    if value is None:
        return None
    try:
        if fmt == "timestamp_ms":
            return datetime.fromtimestamp(float(value) / 1000, tz=timezone.utc)
        if fmt == "timestamp_s":
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        # Default: ISO
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def _format_cursor(dt: datetime, fmt: str) -> str:
    if fmt == "timestamp_ms":
        return str(int(dt.timestamp() * 1000))
    if fmt == "timestamp_s":
        return str(int(dt.timestamp()))
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


@register
class GenericRestConnector(BaseConnector):
    connector_type = "generic_rest"

    def _cfg(self) -> dict[str, Any]:
        return self.connection.metadata_json or {}

    def _headers(self) -> dict[str, str]:
        cfg = self._cfg()
        return _build_auth_headers(
            cfg.get("auth_type", "none"),
            cfg.get("auth_config", {}),
        )

    async def authenticate(self) -> bool:
        cfg = self._cfg()
        base_url = cfg.get("base_url", "")
        if not base_url:
            return False
        # Just verify the base URL is reachable with auth headers
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(base_url, headers=self._headers())
                return resp.status_code < 500
        except Exception:
            return False

    async def poll(self, since: datetime) -> list[IncomingMessage]:
        cfg = self._cfg()
        base_url = cfg.get("base_url", "").rstrip("/")
        list_endpoint = cfg.get("list_endpoint", "")
        field_map: dict[str, str] = cfg.get("field_map", {})
        cursor_format: str = cfg.get("cursor_format", "iso")
        results_key: str = cfg.get("results_key", "results")
        pagination: str = cfg.get("pagination", "none")
        page_param: str = cfg.get("page_param", "page")
        page_size: int = cfg.get("page_size", 100)
        next_page_key: str = cfg.get("next_page_key", "")
        priority_map: dict = cfg.get("priority_map", _DEFAULT_PRIORITY_URGENCY)

        if not base_url or not list_endpoint:
            logger.warning("GenericRest missing base_url or list_endpoint for connection=%s", self.connection.id)
            return []

        cursor_str = _format_cursor(since, cursor_format)
        url = base_url + list_endpoint.format(cursor=cursor_str, since=cursor_str)
        messages: list[IncomingMessage] = []
        headers = {**self._headers(), "Accept": "application/json"}

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                page = 1
                offset = 0
                page_token: str | None = None

                while True:
                    params: dict[str, Any] = {}
                    if pagination == "page":
                        params[page_param] = page
                        params["limit"] = page_size
                    elif pagination == "offset":
                        params["offset"] = offset
                        params["limit"] = page_size
                    elif pagination == "cursor" and page_token:
                        params[next_page_key] = page_token

                    resp = await client.get(url, headers=headers, params=params)
                    resp.raise_for_status()
                    data = resp.json()

                    records = data if isinstance(data, list) else data.get(results_key, [])
                    if not records:
                        break

                    for record in records:
                        raw_created = _extract_field(record, field_map, "created_at")
                        created_at = _parse_cursor(raw_created, cursor_format)
                        if created_at is None or created_at <= since:
                            continue

                        body = str(_extract_field(record, field_map, "body", "") or "").strip()
                        if not body:
                            continue

                        ext_id = str(_extract_field(record, field_map, "id", "") or "")
                        email = str(_extract_field(record, field_map, "customer_email", "") or "")
                        priority = str(_extract_field(record, field_map, "priority", "3") or "3")
                        urgency = float(priority_map.get(priority, 0.45))

                        messages.append(self._build_message(
                            external_message_id=f"generic:{self.connection.id}:{ext_id}",
                            body=body,
                            received_at=created_at,
                            external_thread_id=f"generic:{self.connection.id}:{ext_id}",
                            metadata={
                                "external_id": ext_id,
                                "customer_email": email,
                                "urgency_score": urgency,
                                "priority": priority,
                                "raw": {k: v for k, v in list(record.items())[:10]},
                                "source": "generic_rest",
                            },
                        ))

                    # Pagination termination
                    if pagination == "none":
                        break
                    if pagination == "page":
                        if len(records) < page_size:
                            break
                        page += 1
                    elif pagination == "offset":
                        offset += len(records)
                        if len(records) < page_size:
                            break
                    elif pagination == "cursor":
                        page_token = data.get(next_page_key)
                        if not page_token:
                            break

        except Exception as exc:
            logger.exception("GenericRest poll failed connection=%s: %s", self.connection.id, exc)

        return messages

    async def send_reply(self, external_id: str, body: str) -> bool:
        cfg = self._cfg()
        base_url = cfg.get("base_url", "").rstrip("/")
        reply_endpoint = cfg.get("reply_endpoint", "")
        reply_body_template: dict = cfg.get("reply_body_template", {"comment": "{body}"})
        if not base_url or not reply_endpoint:
            return False

        ext_id = external_id.split(":")[-1]
        url = base_url + reply_endpoint.format(id=ext_id)
        payload = {k: v.replace("{body}", body) if isinstance(v, str) else v
                   for k, v in reply_body_template.items()}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    url,
                    headers={**self._headers(), "Content-Type": "application/json"},
                    json=payload,
                )
                return resp.status_code in (200, 201)
        except Exception:
            return False
