"""Zendesk helpdesk connector.

Auth: credentials_encrypted must contain JSON:
  {"email": "agent@company.com", "api_token": "xxx", "subdomain": "yourco"}
"""
from __future__ import annotations

import base64
import json
from datetime import datetime, timezone

import httpx

from app.connectors.base import BaseConnector
from app.connectors.registry import register
from app.services.unified_ingestion import IncomingMessage
from app.utils.logging import get_logger

logger = get_logger(__name__)

_PRIORITY_URGENCY = {"urgent": 1.0, "high": 0.75, "normal": 0.45, "low": 0.2}


def _creds(connection) -> dict[str, str]:
    raw = connection.credentials_encrypted or "{}"
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return {}
    return raw if isinstance(raw, dict) else {}


@register
class ZendeskConnector(BaseConnector):
    connector_type = "zendesk"

    def _auth_header(self) -> str:
        c = _creds(self.connection)
        email = c.get("email", "")
        token = c.get("api_token", "")
        encoded = base64.b64encode(f"{email}/token:{token}".encode()).decode()
        return f"Basic {encoded}"

    def _subdomain(self) -> str:
        return _creds(self.connection).get("subdomain", "")

    async def authenticate(self) -> bool:
        subdomain = self._subdomain()
        if not subdomain:
            return False
        url = f"https://{subdomain}.zendesk.com/api/v2/users/me.json"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url, headers={"Authorization": self._auth_header()})
                return resp.status_code == 200
        except Exception:
            return False

    async def poll(self, since: datetime) -> list[IncomingMessage]:
        subdomain = self._subdomain()
        if not subdomain:
            return []

        since_str = since.strftime("%Y-%m-%dT%H:%M:%SZ")
        url = f"https://{subdomain}.zendesk.com/api/v2/tickets.json"
        params: dict = {
            "sort_by": "created_at",
            "sort_order": "asc",
            "created_after": since_str,
            "per_page": 100,
        }
        headers = {"Authorization": self._auth_header()}
        messages: list[IncomingMessage] = []

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                next_url: str | None = url
                while next_url:
                    resp = await client.get(next_url, headers=headers, params=params)
                    resp.raise_for_status()
                    data = resp.json()
                    params = {}  # subsequent pages use the full next_page URL

                    for ticket in data.get("tickets", []):
                        created_str = ticket.get("created_at", "")
                        try:
                            created_at = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                        except (ValueError, TypeError):
                            continue
                        if created_at <= since:
                            continue

                        body = (ticket.get("description") or "").strip()
                        if not body:
                            continue

                        priority = (ticket.get("priority") or "normal").lower()
                        urgency = _PRIORITY_URGENCY.get(priority, 0.45)
                        ticket_id = ticket.get("id", "")
                        via = ticket.get("via", {}).get("source", {}).get("from", {})
                        email = via.get("address") or ""
                        name = via.get("name") or ""

                        messages.append(self._build_message(
                            external_message_id=f"zdsk:{ticket_id}",
                            body=body,
                            received_at=created_at,
                            sender_id=str(ticket.get("requester_id", "")),
                            sender_name=name or None,
                            external_thread_id=f"zdsk:ticket:{ticket_id}",
                            metadata={
                                "ticket_id": ticket_id,
                                "subject": ticket.get("subject", ""),
                                "priority": priority,
                                "urgency_score": urgency,
                                "status": ticket.get("status", ""),
                                "customer_email": email,
                                "ticket_url": f"https://{subdomain}.zendesk.com/agent/tickets/{ticket_id}",
                                "source": "zendesk",
                            },
                        ))

                    next_url = data.get("next_page")

        except Exception as exc:
            logger.exception("Zendesk poll failed connection=%s: %s", self.connection.id, exc)

        return messages

    async def send_reply(self, external_id: str, body: str) -> bool:
        subdomain = self._subdomain()
        ticket_id = external_id.replace("zdsk:", "").split(":")[-1]
        url = f"https://{subdomain}.zendesk.com/api/v2/tickets/{ticket_id}.json"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.put(
                    url,
                    headers={
                        "Authorization": self._auth_header(),
                        "Content-Type": "application/json",
                    },
                    json={"ticket": {"comment": {"body": body, "public": True}}},
                )
                return resp.status_code in (200, 201)
        except Exception:
            return False
