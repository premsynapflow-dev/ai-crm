"""Facebook Page Reviews connector — polls via Facebook Graph API.

Auth: Page access token stored in channel_connections.access_token.
Config in metadata_json: {page_id: "123456789"}
Cursor: created_time of last fetched rating.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from app.connectors.base import BaseConnector
from app.connectors.registry import register
from app.services.unified_ingestion import IncomingMessage
from app.utils.logging import get_logger

logger = get_logger(__name__)

_GRAPH_BASE = "https://graph.facebook.com/v18.0"
_RATING_URGENCY = {1: 1.0, 2: 0.75, 3: 0.45, 4: 0.15, 5: 0.0}


@register
class FacebookConnector(BaseConnector):
    connector_type = "facebook"

    def _token(self) -> str:
        return self.connection.access_token or ""

    def _page_id(self) -> str:
        meta: dict[str, Any] = self.connection.metadata_json or {}
        return meta.get("page_id", "")

    async def authenticate(self) -> bool:
        token = self._token()
        page_id = self._page_id()
        if not token or not page_id:
            return False
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{_GRAPH_BASE}/{page_id}",
                    params={"access_token": token, "fields": "id,name"},
                )
                return resp.status_code == 200
        except Exception:
            return False

    async def poll(self, since: datetime) -> list[IncomingMessage]:
        token = self._token()
        page_id = self._page_id()
        if not token or not page_id:
            return []

        url = f"{_GRAPH_BASE}/{page_id}/ratings"
        messages: list[IncomingMessage] = []
        after: str | None = None

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                while True:
                    params: dict[str, Any] = {
                        "access_token": token,
                        "fields": "reviewer,rating,review_text,created_time",
                        "limit": 50,
                    }
                    if after:
                        params["after"] = after

                    resp = await client.get(url, params=params)
                    if resp.status_code != 200:
                        break
                    data = resp.json()

                    reached_cursor = False
                    for rating in data.get("data", []):
                        created_str = rating.get("created_time", "")
                        try:
                            created_at = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                        except (ValueError, TypeError):
                            continue
                        if created_at <= since:
                            reached_cursor = True
                            break

                        review_text = (rating.get("review_text") or "").strip()
                        star = rating.get("rating", 3)
                        if not review_text and star >= 4:
                            continue  # Skip positive reviews without text

                        urgency = _RATING_URGENCY.get(star, 0.3)
                        reviewer = rating.get("reviewer", {})
                        reviewer_id = reviewer.get("id", "")
                        reviewer_name = reviewer.get("name", "")
                        rating_id = rating.get("open_graph_story", {}).get("id", reviewer_id)

                        body = review_text or f"{star}-star review (no text)"

                        messages.append(self._build_message(
                            external_message_id=f"fb:{page_id}:{reviewer_id}:{created_str}",
                            body=body,
                            received_at=created_at,
                            sender_id=reviewer_id or None,
                            sender_name=reviewer_name or None,
                            metadata={
                                "rating": star,
                                "urgency_score": urgency,
                                "page_id": page_id,
                                "reviewer_id": reviewer_id,
                                "source": "facebook",
                            },
                        ))

                    if reached_cursor:
                        break

                    paging = data.get("paging", {})
                    cursors = paging.get("cursors", {})
                    after = cursors.get("after")
                    if not after or not paging.get("next"):
                        break

        except Exception as exc:
            logger.exception("Facebook poll failed connection=%s: %s", self.connection.id, exc)

        return messages
