from __future__ import annotations

import uuid

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, Index, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.types import Uuid

from app.db.models import Base


class Inbox(Base):
    __tablename__ = "inboxes"
    __table_args__ = (
        CheckConstraint("provider_type IN ('gmail', 'imap')", name="ck_inboxes_provider_type"),
        UniqueConstraint("tenant_id", "email_address", name="uq_inboxes_tenant_email_address"),
        Index("idx_inboxes_tenant_id", "tenant_id"),
        Index("idx_inboxes_email_address", "email_address"),
        {
            "comment": "Stores tenant-scoped email inbox connections for Gmail OAuth and generic IMAP providers.",
        },
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(Uuid(as_uuid=True), nullable=False)
    email_address = Column(Text, nullable=False)
    provider_type = Column(String(20), nullable=False)
    access_token = Column(Text, nullable=True)
    refresh_token = Column(Text, nullable=True)
    token_expiry = Column(DateTime(timezone=True), nullable=True)
    imap_host = Column(Text, nullable=True)
    imap_port = Column(Integer, nullable=True)
    imap_username = Column(Text, nullable=True)
    imap_password = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

