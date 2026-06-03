"""Instagram DMs connector — polls via Instagram Graph API.

Auth: Page access token stored in channel_connections.access_token.
Config in metadata_json: {page_id: "..."}  (Instagram Professional Account page)
Cursor: ISO timestamp of last fetched message.

Prerequisite: Facebook App with instagram_manage_messages permission.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import httpx

from app.connectors.base import BaseConnector
from app.connectors.registry import register
from app.services.unified_ingestion import IncomingMessage
from app.utils.logging import get_logger

logger = get_logger(__name__)

_GRAPH_BASE = "https://graph.facebook.com/v18.0"
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return _TAG_RE.sub(" ", text).strip()


@register
class InstagramConnector(BaseConnector):
    connector_type = "instagram"

    def _token(self) -> str:
        return self.connection.access_token or ""

    def _page_id(self) -> str:
        meta: dict[str, Any] = self.connection.metadata_json or {}
        return meta.get("page_id", "")

    async def authenticate(self) -> bool:
        if not self._token():
            return False
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{_GRAPH_BASE}/me",
                    params={"access_token": self._token(), "fields": "id,name"},
                )
                return resp.status_code == 200
        except Exception:
            return False

    async def poll(self, since: datetime) -> list[IncomingMessage]:
        token = self._token()
        page_id = self._page_id()
        if not token or not page_id:
            return []

        # Fetch recent conversations (DMs)
        messages: list[IncomingMessage] = []
        since_unix = int(since.timestamp())

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                # Get conversations list
                conv_resp = await client.get(
                    f"{_GRAPH_BASE}/{page_id}/conversations",
                    params={
                        "access_token": token,
                        "fields": "id,updated_time,participants",
                        "platform": "instagram",
                    },
                )
                if conv_resp.status_code != 200:
                    return []

                conversations = conv_resp.json().get("data", [])
                for conv in conversations:
                    updated_str = conv.get("updated_time", "")
                    try:
                        updated_at = datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
                    except (ValueError, TypeError):
                        continue
                    if updated_at <= since:
                        continue

                    conv_id = conv.get("id", "")
                    # Get messages in this conversation
                    msg_resp = await client.get(
                        f"{_GRAPH_BASE}/{conv_id}/messages",
                        params={
                            "access_token": token,
                            "fields": "id,message,created_time,from",
                        },
                    )
                    if msg_resp.status_code != 200:
                        continue

                    for msg in msg_resp.json().get("data", []):
                        created_str = msg.get("created_time", "")
                        try:
                            created_at = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                        except (ValueError, TypeError):
                            continue
                        if created_at <= since:
                            continue

                        body = _strip_html(msg.get("message", "") or "")
                        if not body:
                            continue

                        sender = msg.get("from", {})
                        sender_id = sender.get("id", "")
                        # Skip messages sent by the page itself
                        if sender_id == page_id:
                            continue
                        sender_name = sender.get("name", "")
                        msg_id = msg.get("id", "")

                        messages.append(self._build_message(
                            external_message_id=f"ig:{msg_id}",
                            body=body,
                            received_at=created_at,
                            sender_id=sender_id or None,
                            sender_name=sender_name or None,
                            external_thread_id=f"ig:conv:{conv_id}",
                            metadata={
                                "conversation_id": conv_id,
                                "message_id": msg_id,
                                "page_id": page_id,
                                "source": "instagram",
                            },
                        ))

        except Exception as exc:
            logger.exception("Instagram poll failed connection=%s: %s", self.connection.id, exc)

        return messages

    async def send_reply(self, external_id: str, body: str) -> bool:
        token = self._token()
        page_id = self._page_id()
        # external_id is the conversation thread id
        conv_id = external_id.replace("ig:conv:", "").replace("ig:", "")
        url = f"{_GRAPH_BASE}/{page_id}/messages"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    url,
                    params={"access_token": token},
                    json={
                        "recipient": {"thread_key": conv_id},
                        "message": {"text": body},
                        "messaging_type": "RESPONSE",
                    },
                )
                return resp.status_code in (200, 201)
        except Exception:
            return False
