from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class InboxSummary(BaseModel):
    id: str
    email: str
    provider: str
    status: str
    created_at: datetime | None = None


class GmailConnectUrlResponse(BaseModel):
    connect_url: str


class ConnectImapRequest(BaseModel):
    email: str = Field(..., min_length=3)
    imap_host: str = Field(..., min_length=1)
    imap_port: int = Field(..., ge=1, le=65535)
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)

