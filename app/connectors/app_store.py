"""Apple App Store Reviews connector — polls the public iTunes RSS JSON feed.

Auth: None required (public feed).
Config in metadata_json: {app_id: "123456789", country: "us"}
Cursor: ISO timestamp of the most-recently-fetched review.
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

_RATING_URGENCY = {1: 1.0, 2: 0.75, 3: 0.45, 4: 0.15, 5: 0.0}


@register
class AppStoreConnector(BaseConnector):
    connector_type = "app_store"

    def _meta(self) -> dict[str, Any]:
        return self.connection.metadata_json or {}

    async def authenticate(self) -> bool:
        meta = self._meta()
        return bool(meta.get("app_id"))

    async def poll(self, since: datetime) -> list[IncomingMessage]:
        meta = self._meta()
        app_id = meta.get("app_id", "")
        country = meta.get("country", "us").lower()
        if not app_id:
            logger.warning("AppStore missing app_id for connection=%s", self.connection.id)
            return []

        url = (
            f"https://itunes.apple.com/{country}/rss/customerreviews/"
            f"id={app_id}/sortBy=mostRecent/json"
        )
        messages: list[IncomingMessage] = []

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url, headers={"Accept": "application/json"})
                resp.raise_for_status()
                data = resp.json()

                feed = data.get("feed", {})
                entries = feed.get("entry", [])
                if not isinstance(entries, list):
                    entries = [entries]

                for entry in entries:
                    # Skip the first entry which is the app info
                    if "im:rating" not in entry:
                        continue

                    updated_str = (
                        entry.get("updated", {}).get("label", "") if isinstance(entry.get("updated"), dict)
                        else str(entry.get("updated", ""))
                    )
                    try:
                        updated_at = datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
                    except (ValueError, TypeError):
                        continue
                    if updated_at <= since:
                        continue

                    title_raw = entry.get("title", {})
                    title = title_raw.get("label", "") if isinstance(title_raw, dict) else str(title_raw)
                    content_raw = entry.get("content", {})
                    body_text = content_raw.get("label", "") if isinstance(content_raw, dict) else str(content_raw)
                    full_body = f"{title}\n\n{body_text}".strip() if title else body_text.strip()
                    if not full_body:
                        continue

                    rating_raw = entry.get("im:rating", {})
                    try:
                        star = int(rating_raw.get("label", 3) if isinstance(rating_raw, dict) else rating_raw)
                    except (ValueError, TypeError):
                        star = 3
                    urgency = _RATING_URGENCY.get(star, 0.3)

                    author_raw = entry.get("author", {})
                    author_name = author_raw.get("name", {}).get("label", "") if isinstance(author_raw, dict) else ""

                    id_raw = entry.get("id", {})
                    review_id = id_raw.get("label", "") if isinstance(id_raw, dict) else str(id_raw)

                    messages.append(self._build_message(
                        external_message_id=f"appstore:{app_id}:{review_id}",
                        body=full_body,
                        received_at=updated_at,
                        sender_name=author_name or None,
                        metadata={
                            "rating": star,
                            "urgency_score": urgency,
                            "app_id": app_id,
                            "country": country,
                            "review_id": review_id,
                            "source": "app_store",
                        },
                    ))

        except Exception as exc:
            logger.exception("AppStore poll failed connection=%s: %s", self.connection.id, exc)

        return messages
