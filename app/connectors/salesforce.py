"""Salesforce Cases connector — polls via REST API using SOQL.

Auth: OAuth2 password flow. credentials_encrypted must contain JSON:
  {"client_id": "...", "client_secret": "...", "username": "...",
   "password": "...", "security_token": "...", "instance_url": "..."}
   OR pre-fetched: {"access_token": "...", "instance_url": "..."}

Cursor: Case CreatedDate (ISO timestamp).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import httpx

from app.connectors.base import BaseConnector
from app.connectors.registry import register
from app.services.unified_ingestion import IncomingMessage
from app.utils.logging import get_logger

logger = get_logger(__name__)

_LOGIN_URL = "https://login.salesforce.com/services/oauth2/token"
_PRIORITY_URGENCY = {"High": 0.75, "Medium": 0.45, "Low": 0.2}


def _creds(connection) -> dict[str, str]:
    raw = connection.credentials_encrypted or "{}"
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return {}
    return raw if isinstance(raw, dict) else {}


async def _get_token(creds: dict) -> tuple[str, str] | tuple[None, None]:
    """Return (access_token, instance_url) via password flow or from stored token."""
    if creds.get("access_token") and creds.get("instance_url"):
        return creds["access_token"], creds["instance_url"]

    # Try password + security_token flow
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                _LOGIN_URL,
                data={
                    "grant_type": "password",
                    "client_id": creds.get("client_id", ""),
                    "client_secret": creds.get("client_secret", ""),
                    "username": creds.get("username", ""),
                    "password": creds.get("password", "") + creds.get("security_token", ""),
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["access_token"], data["instance_url"]
    except Exception as exc:
        logger.warning("Salesforce auth failed: %s", exc)
        return None, None


@register
class SalesforceConnector(BaseConnector):
    connector_type = "salesforce"

    async def authenticate(self) -> bool:
        creds = _creds(self.connection)
        token, _ = await _get_token(creds)
        return token is not None

    async def poll(self, since: datetime) -> list[IncomingMessage]:
        creds = _creds(self.connection)
        token, instance_url = await _get_token(creds)
        if not token or not instance_url:
            return []

        since_str = since.strftime("%Y-%m-%dT%H:%M:%SZ")
        soql = (
            "SELECT Id, Subject, Description, ContactEmail, CreatedDate, Priority, Status "
            f"FROM Case WHERE CreatedDate > {since_str} ORDER BY CreatedDate ASC LIMIT 200"
        )
        url = f"{instance_url}/services/data/v58.0/query"
        messages: list[IncomingMessage] = []

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                next_url: str | None = None
                params: dict[str, str] = {"q": soql}
                while True:
                    req_url = f"{instance_url}{next_url}" if next_url else url
                    req_params = {} if next_url else params
                    resp = await client.get(
                        req_url,
                        headers={"Authorization": f"Bearer {token}"},
                        params=req_params,
                    )
                    resp.raise_for_status()
                    data = resp.json()

                    for case in data.get("records", []):
                        created_str = case.get("CreatedDate", "")
                        try:
                            created_at = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                        except (ValueError, TypeError):
                            continue
                        if created_at <= since:
                            continue

                        subject = (case.get("Subject") or "").strip()
                        description = (case.get("Description") or "").strip()
                        body = f"{subject}\n\n{description}".strip() if subject else description
                        if not body:
                            continue

                        priority = case.get("Priority") or "Medium"
                        urgency = _PRIORITY_URGENCY.get(priority, 0.45)
                        case_id = case.get("Id", "")
                        email = case.get("ContactEmail", "") or ""

                        messages.append(self._build_message(
                            external_message_id=f"sf:{case_id}",
                            body=body,
                            received_at=created_at,
                            external_thread_id=f"sf:case:{case_id}",
                            metadata={
                                "case_id": case_id,
                                "subject": subject,
                                "priority": priority,
                                "urgency_score": urgency,
                                "status": case.get("Status", ""),
                                "customer_email": email,
                                "case_url": f"{instance_url}/{case_id}",
                                "source": "salesforce",
                            },
                        ))

                    next_url = data.get("nextRecordsUrl")
                    if not next_url:
                        break

        except Exception as exc:
            logger.exception("Salesforce poll failed connection=%s: %s", self.connection.id, exc)

        return messages

    async def send_reply(self, external_id: str, body: str) -> bool:
        creds = _creds(self.connection)
        token, instance_url = await _get_token(creds)
        if not token or not instance_url:
            return False
        case_id = external_id.replace("sf:", "").split(":")[-1]
        url = f"{instance_url}/services/data/v58.0/sobjects/CaseComment/"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    json={"ParentId": case_id, "CommentBody": body, "IsPublished": True},
                )
                return resp.status_code in (200, 201)
        except Exception:
            return False
