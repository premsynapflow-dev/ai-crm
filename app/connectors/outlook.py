"""Microsoft Outlook / Graph API email connector.

Auth: OAuth2 Authorization Code flow.
  credentials_encrypted must contain JSON:
  {"access_token": "...", "refresh_token": "...", "tenant_id": "common"}
  OR store in channel_connections.access_token / refresh_token directly.

Environment variables needed for token refresh:
  MICROSOFT_CLIENT_ID, MICROSOFT_CLIENT_SECRET

Endpoint: GET https://graph.microsoft.com/v1.0/me/mailFolders/Inbox/messages
          Uses $filter=receivedDateTime ge {cursor} for efficient polling.
          Uses $deltaLink for incremental polling after first sync.

Cursor: receivedDateTime of the last fetched message (ISO 8601).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

import httpx

from app.connectors.base import BaseConnector
from app.connectors.registry import register
from app.services.unified_ingestion import IncomingMessage
from app.utils.logging import get_logger

logger = get_logger(__name__)

_GRAPH_BASE = "https://graph.microsoft.com/v1.0"
_TOKEN_URL_TEMPLATE = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"


def _creds(connection) -> dict[str, str]:
    raw = connection.credentials_encrypted or "{}"
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return {}
    return raw if isinstance(raw, dict) else {}


async def _refresh_token(connection) -> str | None:
    """Refresh the access token using the stored refresh_token."""
    creds = _creds(connection)
    refresh_token = creds.get("refresh_token") or getattr(connection, "refresh_token", None)
    if not refresh_token:
        return getattr(connection, "access_token", None) or creds.get("access_token")

    client_id = os.environ.get("MICROSOFT_CLIENT_ID", "")
    client_secret = os.environ.get("MICROSOFT_CLIENT_SECRET", "")
    tenant = creds.get("tenant_id", "common")
    if not client_id or not client_secret:
        return getattr(connection, "access_token", None) or creds.get("access_token")

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                _TOKEN_URL_TEMPLATE.format(tenant=tenant),
                data={
                    "grant_type": "refresh_token",
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": refresh_token,
                    "scope": "https://graph.microsoft.com/Mail.Read https://graph.microsoft.com/Mail.Send offline_access",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            new_token = data.get("access_token")
            if new_token and hasattr(connection, "access_token"):
                connection.access_token = new_token
            return new_token
    except Exception as exc:
        logger.warning("Outlook token refresh failed connection=%s: %s", connection.id, exc)
        return getattr(connection, "access_token", None) or creds.get("access_token")


@register
class OutlookConnector(BaseConnector):
    connector_type = "outlook"

    async def authenticate(self) -> bool:
        token = await _refresh_token(self.connection)
        if not token:
            return False
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{_GRAPH_BASE}/me",
                    headers={"Authorization": f"Bearer {token}"},
                )
                return resp.status_code == 200
        except Exception:
            return False

    async def poll(self, since: datetime) -> list[IncomingMessage]:
        token = await _refresh_token(self.connection)
        if not token:
            return []

        since_str = since.strftime("%Y-%m-%dT%H:%M:%SZ")
        url = f"{_GRAPH_BASE}/me/mailFolders/Inbox/messages"
        params = {
            "$filter": f"receivedDateTime ge {since_str}",
            "$orderby": "receivedDateTime asc",
            "$top": 50,
            "$select": "id,subject,body,bodyPreview,receivedDateTime,from,toRecipients,conversationId",
        }
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }
        messages: list[IncomingMessage] = []

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                next_link: str | None = None
                while True:
                    req_url = next_link or url
                    req_params = {} if next_link else params
                    resp = await client.get(req_url, headers=headers, params=req_params)
                    resp.raise_for_status()
                    data = resp.json()

                    for msg in data.get("value", []):
                        received_str = msg.get("receivedDateTime", "")
                        try:
                            received_at = datetime.fromisoformat(received_str.replace("Z", "+00:00"))
                        except (ValueError, TypeError):
                            continue
                        if received_at <= since:
                            continue

                        # Prefer text body, fall back to bodyPreview
                        body_obj = msg.get("body", {})
                        if body_obj.get("contentType", "") == "text":
                            body = body_obj.get("content", "").strip()
                        else:
                            body = msg.get("bodyPreview", "").strip()
                        if not body:
                            continue

                        sender = msg.get("from", {}).get("emailAddress", {})
                        sender_email = sender.get("address", "")
                        sender_name = sender.get("name", "")
                        msg_id = msg.get("id", "")
                        conv_id = msg.get("conversationId", msg_id)

                        messages.append(self._build_message(
                            external_message_id=f"outlook:{msg_id}",
                            body=body,
                            received_at=received_at,
                            sender_id=sender_email or None,
                            sender_name=sender_name or None,
                            external_thread_id=f"outlook:conv:{conv_id}",
                            metadata={
                                "message_id": msg_id,
                                "conversation_id": conv_id,
                                "subject": msg.get("subject", ""),
                                "customer_email": sender_email,
                                "source": "outlook",
                            },
                        ))

                    next_link = data.get("@odata.nextLink")
                    if not next_link:
                        break

        except Exception as exc:
            logger.exception("Outlook poll failed connection=%s: %s", self.connection.id, exc)

        return messages

    async def send_reply(self, external_id: str, body: str) -> bool:
        token = await _refresh_token(self.connection)
        if not token:
            return False
        msg_id = external_id.replace("outlook:", "").split(":")[-1]
        url = f"{_GRAPH_BASE}/me/messages/{msg_id}/reply"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    json={"comment": body},
                )
                return resp.status_code in (200, 202)
        except Exception:
            return False
