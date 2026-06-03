"""Google Play Store Reviews connector — polls via Android Publisher API v3.

Auth: Service account JSON key stored in credentials_encrypted.
Config in metadata_json: {package_name: "com.yourapp"}
Cursor: lastModified timestamp of the most-recently-fetched review.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any

import httpx

from app.connectors.base import BaseConnector
from app.connectors.registry import register
from app.services.unified_ingestion import IncomingMessage
from app.utils.logging import get_logger

logger = get_logger(__name__)

_TOKEN_URL = "https://oauth2.googleapis.com/token"
_REVIEWS_URL = "https://androidpublisher.googleapis.com/androidpublisher/v3/applications/{pkg}/reviews"
_RATING_URGENCY = {1: 1.0, 2: 0.75, 3: 0.45, 4: 0.15, 5: 0.0}


def _jwt_header_b64(data: dict) -> str:
    import base64
    raw = json.dumps(data, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


async def _get_access_token(service_account: dict) -> str | None:
    """Obtain a short-lived OAuth2 token from a service account JSON."""
    try:
        import base64
        import hashlib
        # Build JWT manually using RS256 (requires cryptography or rsa package)
        # Fallback: if cryptography not available, return None gracefully
        try:
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import padding
            from cryptography.hazmat.backends import default_backend
        except ImportError:
            logger.warning("PlayStore: 'cryptography' package not installed — skipping")
            return None

        now = int(time.time())
        claim = {
            "iss": service_account.get("client_email", ""),
            "scope": "https://www.googleapis.com/auth/androidpublisher",
            "aud": _TOKEN_URL,
            "exp": now + 3600,
            "iat": now,
        }
        header = {"alg": "RS256", "typ": "JWT"}
        header_b64 = _jwt_header_b64(header)
        claim_b64 = _jwt_header_b64(claim)
        signing_input = f"{header_b64}.{claim_b64}".encode()

        key_pem = service_account.get("private_key", "").encode()
        private_key = serialization.load_pem_private_key(key_pem, password=None, backend=default_backend())
        signature = private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
        import base64
        sig_b64 = base64.urlsafe_b64encode(signature).rstrip(b"=").decode()
        jwt_token = f"{header_b64}.{claim_b64}.{sig_b64}"

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                _TOKEN_URL,
                data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": jwt_token},
            )
            resp.raise_for_status()
            return resp.json().get("access_token")
    except Exception as exc:
        logger.warning("PlayStore token error: %s", exc)
        return None


@register
class PlayStoreConnector(BaseConnector):
    connector_type = "play_store"

    def _service_account(self) -> dict:
        raw = self.connection.credentials_encrypted or "{}"
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except Exception:
                return {}
        return raw if isinstance(raw, dict) else {}

    def _package_name(self) -> str:
        meta = self.connection.metadata_json or {}
        return meta.get("package_name", "")

    async def authenticate(self) -> bool:
        sa = self._service_account()
        return bool(sa.get("client_email") and sa.get("private_key"))

    async def poll(self, since: datetime) -> list[IncomingMessage]:
        pkg = self._package_name()
        if not pkg:
            return []

        token = await _get_access_token(self._service_account())
        if not token:
            return []

        url = _REVIEWS_URL.format(pkg=pkg)
        messages: list[IncomingMessage] = []
        since_ms = int(since.timestamp() * 1000)

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                params: dict[str, Any] = {"maxResults": 100, "translationLanguage": "en"}
                token_param: str | None = None
                while True:
                    if token_param:
                        params["token"] = token_param
                    resp = await client.get(
                        url,
                        headers={"Authorization": f"Bearer {token}"},
                        params=params,
                    )
                    resp.raise_for_status()
                    data = resp.json()

                    for review in data.get("reviews", []):
                        comments = review.get("comments", [])
                        if not comments:
                            continue
                        user_comment = comments[0].get("userComment", {})
                        last_modified_ms = user_comment.get("lastModified", {}).get("seconds", 0)
                        last_modified_ms = int(last_modified_ms) * 1000
                        if last_modified_ms <= since_ms:
                            continue

                        text = user_comment.get("text", "").strip()
                        if not text:
                            continue

                        star = user_comment.get("starRating", 3)
                        urgency = _RATING_URGENCY.get(star, 0.3)
                        review_id = review.get("reviewId", "")
                        author = review.get("authorName", "")
                        received_at = datetime.fromtimestamp(
                            int(user_comment.get("lastModified", {}).get("seconds", 0)),
                            tz=timezone.utc,
                        )

                        messages.append(self._build_message(
                            external_message_id=f"playstore:{pkg}:{review_id}",
                            body=text,
                            received_at=received_at,
                            sender_name=author or None,
                            metadata={
                                "rating": star,
                                "urgency_score": urgency,
                                "package_name": pkg,
                                "review_id": review_id,
                                "source": "play_store",
                            },
                        ))

                    token_param = data.get("tokenPagination", {}).get("nextPageToken")
                    if not token_param:
                        break

        except Exception as exc:
            logger.exception("PlayStore poll failed connection=%s: %s", self.connection.id, exc)

        return messages

    async def send_reply(self, external_id: str, body: str) -> bool:
        pkg = self._package_name()
        review_id = external_id.split(":")[-1]
        token = await _get_access_token(self._service_account())
        if not token:
            return False
        url = f"{_REVIEWS_URL.format(pkg=pkg)}/{review_id}:reply"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    url,
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    json={"replyText": body},
                )
                return resp.status_code in (200, 201)
        except Exception:
            return False
