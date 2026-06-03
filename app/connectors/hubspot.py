"""HubSpot CRM connector — polls support tickets via CRM API v3.

Auth: Private app token stored in channel_connections.access_token.
"""
from __future__ import annotations

from datetime import datetime, timezone

import httpx

from app.connectors.base import BaseConnector
from app.connectors.registry import register
from app.services.unified_ingestion import IncomingMessage
from app.utils.logging import get_logger

logger = get_logger(__name__)

_BASE_URL = "https://api.hubapi.com"
_PRIORITY_URGENCY = {"URGENT": 1.0, "HIGH": 0.75, "MEDIUM": 0.45, "LOW": 0.2}


@register
class HubSpotConnector(BaseConnector):
    connector_type = "hubspot"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.connection.access_token or ''}",
            "Content-Type": "application/json",
        }

    async def authenticate(self) -> bool:
        if not self.connection.access_token:
            return False
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{_BASE_URL}/crm/v3/objects/tickets",
                    headers=self._headers(),
                    params={"limit": 1},
                )
                return resp.status_code == 200
        except Exception:
            return False

    async def poll(self, since: datetime) -> list[IncomingMessage]:
        if not self.connection.access_token:
            return []

        since_ms = int(since.timestamp() * 1000)
        url = f"{_BASE_URL}/crm/v3/objects/tickets/search"
        messages: list[IncomingMessage] = []
        after: str | None = None

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                while True:
                    payload: dict = {
                        "filterGroups": [
                            {
                                "filters": [
                                    {
                                        "propertyName": "createdate",
                                        "operator": "GT",
                                        "value": str(since_ms),
                                    }
                                ]
                            }
                        ],
                        "properties": [
                            "subject",
                            "content",
                            "createdate",
                            "hs_ticket_priority",
                            "hs_pipeline_stage",
                        ],
                        "sorts": [{"propertyName": "createdate", "direction": "ASCENDING"}],
                        "limit": 100,
                    }
                    if after:
                        payload["after"] = after

                    resp = await client.post(url, headers=self._headers(), json=payload)
                    resp.raise_for_status()
                    data = resp.json()

                    for ticket in data.get("results", []):
                        props = ticket.get("properties", {})
                        created_str = props.get("createdate", "")
                        try:
                            created_at = datetime.fromisoformat(
                                created_str.replace("Z", "+00:00")
                            )
                        except (ValueError, TypeError):
                            continue
                        if created_at <= since:
                            continue

                        subject = (props.get("subject") or "").strip()
                        body_text = (props.get("content") or "").strip()
                        full_body = f"{subject}\n\n{body_text}".strip() if subject else body_text
                        if not full_body:
                            continue

                        priority = str(props.get("hs_ticket_priority") or "MEDIUM").upper()
                        urgency = _PRIORITY_URGENCY.get(priority, 0.45)
                        ticket_id = ticket.get("id", "")

                        messages.append(self._build_message(
                            external_message_id=f"hs:{ticket_id}",
                            body=full_body,
                            received_at=created_at,
                            external_thread_id=f"hs:ticket:{ticket_id}",
                            metadata={
                                "ticket_id": ticket_id,
                                "subject": subject,
                                "priority": priority,
                                "urgency_score": urgency,
                                "pipeline_stage": props.get("hs_pipeline_stage", ""),
                                "source": "hubspot",
                            },
                        ))

                    paging = data.get("paging", {})
                    after = (paging.get("next") or {}).get("after")
                    if not after:
                        break

        except Exception as exc:
            logger.exception("HubSpot poll failed connection=%s: %s", self.connection.id, exc)

        return messages

    async def send_reply(self, external_id: str, body: str) -> bool:
        ticket_id = external_id.replace("hs:", "").split(":")[-1]
        url = f"{_BASE_URL}/crm/v3/objects/notes"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    url,
                    headers=self._headers(),
                    json={
                        "properties": {
                            "hs_note_body": body,
                            "hs_timestamp": datetime.now(timezone.utc).strftime(
                                "%Y-%m-%dT%H:%M:%S.000Z"
                            ),
                        },
                        "associations": [
                            {
                                "to": {"id": ticket_id},
                                "types": [
                                    {
                                        "associationCategory": "HUBSPOT_DEFINED",
                                        "associationTypeId": 16,
                                    }
                                ],
                            }
                        ],
                    },
                )
                return resp.status_code in (200, 201)
        except Exception:
            return False
