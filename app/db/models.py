import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Client(Base):
    __tablename__ = "clients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    api_key = Column(String(255), nullable=False, unique=True, index=True)
    plan = Column(String(50), nullable=False, default="starter")
    plan_id = Column(String(50), nullable=False, default="starter")
    monthly_ticket_limit = Column(Integer, nullable=False, default=50)
    trial_ends_at = Column(DateTime(timezone=True), nullable=True)
    slack_webhook_url = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Custom AI prompt configuration (per-client)
    custom_prompt_enabled = Column(Boolean, nullable=False, default=False)
    custom_prompt_config = Column(JSON, nullable=True)
    custom_prompt_updated_at = Column(DateTime(timezone=True), nullable=True)

    complaints = relationship("Complaint", back_populates="client", cascade="all, delete-orphan")
    subscriptions = relationship("Subscription", back_populates="client", cascade="all, delete-orphan")
    invoices = relationship("Invoice", back_populates="client", cascade="all, delete-orphan")
    usage_records = relationship("UsageRecord", back_populates="client", cascade="all, delete-orphan")
    automation_rules = relationship("AutomationRule", back_populates="client", cascade="all, delete-orphan")


class Complaint(Base):
    __tablename__ = "complaints"
    __table_args__ = (Index("idx_complaints_response_time", "response_time_seconds"),)

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
    sentiment_score = Column(Integer, nullable=True)
    sentiment_label = Column(String(50), nullable=True)
    sentiment_indicators = Column(JSON, nullable=True)
    urgency_score = Column(Float, nullable=False, default=0.0)
    assigned_team = Column(String(50), nullable=True)
    assigned_to = Column(String(255), nullable=True)
    ticket_id = Column(String(50), nullable=False, index=True)
    thread_id = Column(String(50), nullable=False, index=True)
    follow_up_status = Column(String(20), default="pending")
    resolution_status = Column(String(20), default="open")
    status = Column(String(50), nullable=False, default="PENDING")
    response_time_seconds = Column(Integer, nullable=True)
    first_response_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    customer_satisfaction_score = Column(Integer, nullable=True)
    satisfaction_score = Column(Integer, nullable=True)
    ai_reply = Column(Text, nullable=True)
    ai_reply_confidence = Column(Float, nullable=True)
    ai_reply_status = Column(String(50), nullable=False, default="pending")
    ai_reply_sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=func.now(), server_default=func.now(), nullable=False)

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
    client_id = Column(UUID(as_uuid=True), nullable=True)
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

    client = relationship("Client", back_populates="automation_rules")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True)
    plan = Column(String(50), nullable=False)
    status = Column(String(50), nullable=False, default="trialing")
    stripe_subscription_id = Column(String(255), nullable=True)
    razorpay_subscription_id = Column(String(255), nullable=True)
    current_period_start = Column(DateTime(timezone=True), nullable=True)
    current_period_end = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    client = relationship("Client", back_populates="subscriptions")


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True)
    invoice_number = Column(String(100), nullable=False, unique=True)
    status = Column(String(50), nullable=False, default="pending")
    subtotal = Column(Integer, nullable=False, default=0)
    tax = Column(Integer, nullable=False, default=0)
    total = Column(Integer, nullable=False, default=0)
    payment_method = Column(String(50), nullable=True)
    payment_id = Column(String(255), nullable=True)
    invoice_date = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    due_date = Column(DateTime(timezone=True), nullable=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    client = relationship("Client", back_populates="invoices")


class UsageRecord(Base):
    __tablename__ = "usage_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True)
    tickets_processed = Column(Integer, nullable=False, default=0)
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    included_in_plan = Column(Integer, nullable=False, default=0)
    overage = Column(Integer, nullable=False, default=0)
    overage_cost = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    client = relationship("Client", back_populates="usage_records")


class RequestAudit(Base):
    __tablename__ = "request_audits"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), nullable=True)
    request_id = Column(String(100), nullable=False, index=True)
    path = Column(String(255), nullable=False, index=True)
    method = Column(String(20), nullable=False)
    ip_address = Column(String(100), nullable=False, index=True)
    user_agent = Column(String(500), nullable=True)
    status_code = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MaterializedAnalytics(Base):
    __tablename__ = "materialized_analytics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    metric_key = Column(String(100), nullable=False, index=True)
    metric_value = Column(JSON, nullable=False)
    period_start = Column(DateTime(timezone=True), nullable=True)
    period_end = Column(DateTime(timezone=True), nullable=True)
    generated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class JobQueue(Base):
    __tablename__ = "job_queue"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_type = Column(String(100), nullable=False, index=True)
    payload = Column(JSON, nullable=False)
    status = Column(String(50), nullable=False, default="queued", index=True)
    retry_count = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    scheduled_for = Column(DateTime(timezone=True), nullable=True)
    processed_at = Column(DateTime(timezone=True), nullable=True)


class ReplyCache(Base):
    __tablename__ = "reply_cache"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cache_key = Column(String(255), nullable=False, unique=True, index=True)
    prompt = Column(Text, nullable=False)
    response = Column(Text, nullable=False)
    hit_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class MonitoringMetric(Base):
    __tablename__ = "monitoring_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    metric_name = Column(String(100), nullable=False, index=True)
    metric_value = Column(Float, nullable=False, default=0.0)
    dimensions = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class WaitlistEntry(Base):
    __tablename__ = "waitlist_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), nullable=False, unique=True)
    details = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DemoRequest(Base):
    __tablename__ = "demo_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), nullable=False)
    name = Column(String(255), nullable=True)
    company = Column(String(255), nullable=True)
    details = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
