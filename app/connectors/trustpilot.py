"""Trustpilot Reviews connector.

Polls the Trustpilot Business API for new reviews.
Auth: API key stored in ChannelConnection.access_token (Trustpilot API key).
Config in metadata_json: {business_unit_id, business_name}
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

_REVIEWS_URL = "https://api.trustpilot.com/v1/private/business-units/{unit_id}/reviews"
_RATING_URGENCY = {1: 1.0, 2: 0.75, 3: 0.45, 4: 0.15, 5: 0.0}


@register
class TrustpilotConnector(BaseConnector):
    connector_type = "trustpilot"

    async def authenticate(self) -> bool:
        return bool(self.connection.access_token)

    async def poll(self, since: datetime) -> list[IncomingMessage]:
        meta: dict[str, Any] = self.connection.metadata_json or {}
        unit_id = meta.get("business_unit_id", "")
        if not unit_id:
            logger.warning("Trustpilot missing business_unit_id for connection=%s", self.connection.id)
            return []

        api_key = self.connection.access_token or ""
        if not api_key:
            return []

        url = _REVIEWS_URL.format(unit_id=unit_id)
        messages: list[IncomingMessage] = []
        page = 1

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                while True:
                    resp = await client.get(
                        url,
                        headers={"apikey": api_key},
                        params={
                            "perPage": 100,
                            "page": page,
                            "orderBy": "createdat.desc",
                            "stars": "1,2,3",  # only fetch negative/neutral by default
                        },
                    )
                    resp.raise_for_status()
                    data = resp.json()

                    reviews = data.get("reviews", [])
                    if not reviews:
                        break

                    reached_cursor = False
                    for review in reviews:
                        created_str = review.get("createdAt", "")
                        try:
                            created_at = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                        except ValueError:
                            continue
                        if created_at <= since:
                            reached_cursor = True
                            break

                        text = review.get("text", "").strip()
                        title = review.get("title", "").strip()
                        body = f"{title}\n{text}".strip() if title else text
                        if not body:
                            continue

                        star = int(review.get("stars", 3))
                        consumer = review.get("consumer", {})
                        review_id = review.get("id", "")

                        messages.append(self._build_message(
                            external_message_id=f"tp:{unit_id}:{review_id}",
                            body=body,
                            received_at=created_at,
                            sender_name=consumer.get("displayName"),
                            metadata={
                                "rating": star,
                                "urgency_score": _RATING_URGENCY.get(star, 0.3),
                                "review_id": review_id,
                                "review_url": review.get("links", [{}])[0].get("href", ""),
                                "source": "trustpilot",
                            },
                        ))

                    total_pages = data.get("links", {})
                    if reached_cursor or page >= data.get("numberOfPages", 1):
                        break
                    page += 1

        except Exception as exc:
            logger.exception("Trustpilot poll failed connection=%s: %s", self.connection.id, exc)

        return messages
