"""Intercom connector — polls conversations via REST API.

Auth: access_token stored in channel_connections.access_token (OAuth private app token).
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

import httpx

from app.connectors.base import BaseConnector
from app.connectors.registry import register
from app.services.unified_ingestion import IncomingMessage
from app.utils.logging import get_logger

logger = get_logger(__name__)

_CONVERSATIONS_URL = "https://api.intercom.io/conversations"
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return _TAG_RE.sub(" ", text).strip()


@register
class IntercomConnector(BaseConnector):
    connector_type = "intercom"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.connection.access_token or ''}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Intercom-Version": "2.10",
        }

    async def authenticate(self) -> bool:
        if not self.connection.access_token:
            return False
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get("https://api.intercom.io/me", headers=self._headers())
                return resp.status_code == 200
        except Exception:
            return False

    async def poll(self, since: datetime) -> list[IncomingMessage]:
        if not self.connection.access_token:
            return []

        since_ts = int(since.timestamp())
        messages: list[IncomingMessage] = []
        starting_after: str | None = None

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                while True:
                    payload: dict = {
                        "query": {
                            "operator": "AND",
                            "value": [
                                {"field": "created_at", "operator": ">", "value": since_ts},
                            ],
                        },
                        "pagination": {"per_page": 50},
                        "sort": {"field": "created_at", "order": "ascending"},
                    }
                    if starting_after:
                        payload["pagination"]["starting_after"] = starting_after

                    resp = await client.post(
                        f"{_CONVERSATIONS_URL}/search",
                        headers=self._headers(),
                        json=payload,
                    )
                    if resp.status_code != 200:
                        break
                    data = resp.json()

                    for conv in data.get("conversations", []):
                        created_at = datetime.fromtimestamp(
                            conv.get("created_at", 0), tz=timezone.utc
                        )
                        if created_at <= since:
                            continue

                        source = conv.get("source", {})
                        raw_body = source.get("body") or ""
                        body = _strip_html(raw_body)
                        if not body:
                            continue

                        conv_id = conv.get("id", "")
                        contacts = conv.get("contacts", {}).get("contacts") or []
                        contact_id = contacts[0].get("id", "") if contacts else ""

                        messages.append(self._build_message(
                            external_message_id=f"ic:{conv_id}",
                            body=body,
                            received_at=created_at,
                            sender_id=contact_id or None,
                            external_thread_id=f"ic:conv:{conv_id}",
                            metadata={
                                "conversation_id": conv_id,
                                "source_type": source.get("type", ""),
                                "contact_id": contact_id,
                                "source": "intercom",
                            },
                        ))

                    pages = data.get("pages", {})
                    starting_after = (pages.get("next") or {}).get("starting_after")
                    if not starting_after:
                        break

        except Exception as exc:
            logger.exception("Intercom poll failed connection=%s: %s", self.connection.id, exc)

        return messages

    async def send_reply(self, external_id: str, body: str) -> bool:
        conv_id = external_id.replace("ic:", "").split(":")[-1]
        url = f"{_CONVERSATIONS_URL}/{conv_id}/reply"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    url,
                    headers=self._headers(),
                    json={"message_type": "comment", "type": "admin", "body": body},
                )
                return resp.status_code in (200, 201)
        except Exception:
            return False
