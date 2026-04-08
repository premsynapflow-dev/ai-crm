from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field
from pydantic import ConfigDict


class InboxSummary(BaseModel):
    id: str
    email: str
    provider: str
    status: str
    created_at: datetime | None = None


class GmailConnectUrlResponse(BaseModel):
    connect_url: str
    url: str


class ConnectImapRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    email: str = Field(..., min_length=3)
    imap_host: str | None = Field(default=None, min_length=1)
    imap_port: int | None = Field(default=993, ge=1, le=65535)
    imap_use_ssl: bool = Field(default=True)
    username: str | None = Field(default=None, min_length=1)
    password: str = Field(..., min_length=1)

    host: str | None = Field(default=None, min_length=1, alias="host")
    port: int | None = Field(default=None, ge=1, le=65535, alias="port")
    use_ssl: bool | None = Field(default=None, alias="use_ssl")
