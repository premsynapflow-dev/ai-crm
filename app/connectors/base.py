from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from app.db.models import ChannelConnection
from app.services.unified_ingestion import IncomingMessage


class BaseConnector(ABC):
    connector_type: str = ""

    def __init__(self, connection: ChannelConnection) -> None:
        self.connection = connection
        self.client_id = str(connection.client_id)

    @abstractmethod
    async def authenticate(self) -> bool:
        """Validate stored credentials. Returns True if credentials are valid."""

    @abstractmethod
    async def poll(self, since: datetime) -> list[IncomingMessage]:
        """Fetch new inbound messages created/updated after *since*."""

    async def send_reply(self, external_id: str, body: str) -> bool:
        """Send a reply back to the source system. Returns True on success."""
        return False

    def _build_message(
        self,
        *,
        external_message_id: str,
        body: str,
        received_at: datetime | None = None,
        sender_id: str | None = None,
        sender_name: str | None = None,
        external_thread_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> IncomingMessage:
        return IncomingMessage(
            client_id=self.client_id,
            channel=self.connector_type,
            external_message_id=external_message_id,
            external_thread_id=external_thread_id or external_message_id,
            sender_id=sender_id,
            sender_name=sender_name,
            message_text=body or "",
            timestamp=received_at or datetime.now(timezone.utc),
            direction="inbound",
            status="received",
            raw_payload=metadata or {},
        )
