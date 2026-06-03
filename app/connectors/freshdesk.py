"""Freshdesk helpdesk connector.

Auth: credentials_encrypted must contain JSON:
  {"api_key": "xxx", "domain": "yourco.freshdesk.com"}
"""
from __future__ import annotations

import base64
import json
from datetime import datetime

import httpx

from app.connectors.base import BaseConnector
from app.connectors.registry import register
from app.services.unified_ingestion import IncomingMessage
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Freshdesk priority codes: 1=Low 2=Medium 3=High 4=Urgent
_PRIORITY_URGENCY = {1: 0.2, 2: 0.45, 3: 0.75, 4: 1.0}


def _creds(connection) -> dict[str, str]:
    raw = connection.credentials_encrypted or "{}"
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return {}
    return raw if isinstance(raw, dict) else {}


@register
class FreshdeskConnector(BaseConnector):
    connector_type = "freshdesk"

    def _auth_header(self) -> str:
        token = _creds(self.connection).get("api_key", "")
        encoded = base64.b64encode(f"{token}:X".encode()).decode()
        return f"Basic {encoded}"

    def _domain(self) -> str:
        return _creds(self.connection).get("domain", "")

    async def authenticate(self) -> bool:
        domain = self._domain()
        if not domain:
            return False
        url = f"https://{domain}/api/v2/agents/me"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url, headers={"Authorization": self._auth_header()})
                return resp.status_code == 200
        except Exception:
            return False

    async def poll(self, since: datetime) -> list[IncomingMessage]:
        domain = self._domain()
        if not domain:
            return []

        since_str = since.strftime("%Y-%m-%dT%H:%M:%SZ")
        url = f"https://{domain}/api/v2/tickets"
        headers = {"Authorization": self._auth_header()}
        messages: list[IncomingMessage] = []
        page = 1

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                while True:
                    params = {
                        "order_type": "asc",
                        "updated_since": since_str,
                        "per_page": 100,
                        "page": page,
                        "include": "description",
                    }
                    resp = await client.get(url, headers=headers, params=params)
                    resp.raise_for_status()
                    tickets = resp.json()
                    if not tickets:
                        break

                    for ticket in tickets:
                        updated_str = ticket.get("updated_at") or ticket.get("created_at", "")
                        try:
                            updated_at = datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
                        except (ValueError, TypeError):
                            continue

                        body = (
                            ticket.get("description_text")
                            or ticket.get("description")
                            or ""
                        ).strip()
                        if not body:
                            continue

                        priority = ticket.get("priority", 2)
                        urgency = _PRIORITY_URGENCY.get(priority, 0.45)
                        ticket_id = ticket.get("id", "")
                        email = ticket.get("email", "") or ""

                        messages.append(self._build_message(
                            external_message_id=f"fd:{ticket_id}",
                            body=body,
                            received_at=updated_at,
                            sender_id=str(ticket.get("requester_id", "")),
                            external_thread_id=f"fd:ticket:{ticket_id}",
                            metadata={
                                "ticket_id": ticket_id,
                                "subject": ticket.get("subject", ""),
                                "priority": priority,
                                "urgency_score": urgency,
                                "status": ticket.get("status", ""),
                                "customer_email": email,
                                "ticket_url": f"https://{domain}/a/tickets/{ticket_id}",
                                "source": "freshdesk",
                            },
                        ))

                    if len(tickets) < 100:
                        break
                    page += 1

        except Exception as exc:
            logger.exception("Freshdesk poll failed connection=%s: %s", self.connection.id, exc)

        return messages

    async def send_reply(self, external_id: str, body: str) -> bool:
        domain = self._domain()
        ticket_id = external_id.replace("fd:", "").split(":")[-1]
        url = f"https://{domain}/api/v2/tickets/{ticket_id}/reply"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    url,
                    headers={
                        "Authorization": self._auth_header(),
                        "Content-Type": "application/json",
                    },
                    json={"body": body},
                )
                return resp.status_code in (200, 201)
        except Exception:
            return False
