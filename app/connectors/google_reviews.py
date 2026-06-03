"""Google My Business Reviews connector.

Polls the Google My Business API for new/updated reviews.
Auth: stored access_token + refresh_token in ChannelConnection.
Config in metadata_json: {account_id, location_id, location_name}
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

_REVIEWS_URL = "https://mybusiness.googleapis.com/v4/accounts/{account}/locations/{location}/reviews"
_TOKEN_REFRESH_URL = "https://oauth2.googleapis.com/token"

# Star rating → urgency_score (1★ = critical, 5★ = none)
_RATING_URGENCY = {1: 1.0, 2: 0.75, 3: 0.45, 4: 0.15, 5: 0.0}


def _rating_label(star: int) -> str:
    return {1: "very_negative", 2: "negative", 3: "neutral", 4: "positive", 5: "very_positive"}.get(star, "neutral")


@register
class GoogleReviewsConnector(BaseConnector):
    connector_type = "google_reviews"

    async def authenticate(self) -> bool:
        return bool(self.connection.access_token)

    async def _refresh_token_if_needed(self) -> str | None:
        conn = self.connection
        if conn.token_expiry and conn.token_expiry > datetime.now(timezone.utc):
            return conn.access_token
        if not conn.refresh_token:
            return conn.access_token
        try:
            from app.config import get_settings
            settings = get_settings()
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    _TOKEN_REFRESH_URL,
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": conn.refresh_token,
                        "client_id": getattr(settings, "google_client_id", ""),
                        "client_secret": getattr(settings, "google_client_secret", ""),
                    },
                )
                resp.raise_for_status()
                token_data = resp.json()
                conn.access_token = token_data["access_token"]
                return conn.access_token
        except Exception as exc:
            logger.warning("GoogleReviews token refresh failed connection=%s: %s", self.connection.id, exc)
            return conn.access_token

    async def poll(self, since: datetime) -> list[IncomingMessage]:
        meta: dict[str, Any] = self.connection.metadata_json or {}
        account_id = meta.get("account_id", "")
        location_id = meta.get("location_id", "")
        if not account_id or not location_id:
            logger.warning("GoogleReviews missing account_id/location_id for connection=%s", self.connection.id)
            return []

        token = await self._refresh_token_if_needed()
        if not token:
            return []

        url = _REVIEWS_URL.format(account=account_id, location=location_id)
        messages: list[IncomingMessage] = []

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                params: dict[str, Any] = {"pageSize": 50}
                while True:
                    resp = await client.get(url, headers={"Authorization": f"Bearer {token}"}, params=params)
                    resp.raise_for_status()
                    data = resp.json()

                    for review in data.get("reviews", []):
                        update_time_str = review.get("updateTime", "")
                        try:
                            update_time = datetime.fromisoformat(update_time_str.replace("Z", "+00:00"))
                        except ValueError:
                            continue
                        if update_time <= since:
                            continue

                        comment = review.get("comment", "").strip()
                        if not comment:
                            continue

                        star = review.get("starRating", {})
                        star_int = {"ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5}.get(
                            star if isinstance(star, str) else "", 3
                        )
                        reviewer = review.get("reviewer", {})
                        review_id = review.get("reviewId", review.get("name", ""))

                        messages.append(self._build_message(
                            external_message_id=f"gmb:{location_id}:{review_id}",
                            body=comment,
                            received_at=update_time,
                            sender_name=reviewer.get("displayName"),
                            metadata={
                                "rating": star_int,
                                "rating_label": _rating_label(star_int),
                                "urgency_score": _RATING_URGENCY.get(star_int, 0.3),
                                "review_id": review_id,
                                "location_id": location_id,
                                "source": "google_reviews",
                            },
                        ))

                    next_page = data.get("nextPageToken")
                    if not next_page:
                        break
                    params["pageToken"] = next_page

        except Exception as exc:
            logger.exception("GoogleReviews poll failed connection=%s: %s", self.connection.id, exc)

        return messages

    async def send_reply(self, external_id: str, body: str) -> bool:
        meta: dict[str, Any] = self.connection.metadata_json or {}
        account_id = meta.get("account_id", "")
        location_id = meta.get("location_id", "")
        review_id = external_id.split(":")[-1]
        token = await self._refresh_token_if_needed()
        if not token or not account_id or not location_id:
            return False
        url = f"https://mybusiness.googleapis.com/v4/accounts/{account_id}/locations/{location_id}/reviews/{review_id}/reply"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.put(
                    url,
                    headers={"Authorization": f"Bearer {token}"},
                    json={"comment": body},
                )
                return resp.status_code in (200, 201)
        except Exception:
            return False
