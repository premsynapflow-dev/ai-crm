import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Client(Base):
    __tablename__ = "clients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    api_key = Column(String(255), nullable=False, unique=True, index=True)
    plan = Column(String(50), nullable=False, default="basic")
    slack_webhook_url = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    complaints = relationship("Complaint", back_populates="client", cascade="all, delete-orphan")


class Complaint(Base):
    __tablename__ = "complaints"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True)
    summary = Column(String(500), nullable=False)
    source = Column(String(50), nullable=False, default="api")
    customer_email = Column(String(255), nullable=True)
    customer_phone = Column(String(50), nullable=True)
    intent = Column(String(100), nullable=True)
    recommended_action = Column(String(100), nullable=True)
    confidence = Column(Float, nullable=True)
    priority = Column(Integer, nullable=True)
    category = Column(String(100), nullable=False)
    sentiment = Column(Float, nullable=False, default=0.0)
    urgency_score = Column(Float, nullable=False, default=0.0)
    ticket_id = Column(String(50), nullable=False, index=True)
    thread_id = Column(String(50), nullable=False, index=True)
    follow_up_status = Column(String(20), default="pending")
    resolution_status = Column(String(20), default="open")
    status = Column(String(50), nullable=False, default="PENDING")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    client = relationship("Client", back_populates="complaints")


class ClientUser(Base):
    __tablename__ = "client_users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class EventLog(Base):
    __tablename__ = "event_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), nullable=False)
    event_type = Column(String(100), nullable=False)
    payload = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AutomationRule(Base):
    __tablename__ = "automation_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False)
    trigger_type = Column(String(50), nullable=False)
    trigger_value = Column(String(100), nullable=False)
    action_type = Column(String(50), nullable=False)
    action_config = Column(JSON, nullable=True)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
