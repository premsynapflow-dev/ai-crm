import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    Time,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Client(Base):
    __tablename__ = "clients"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    api_key = Column(String(255), nullable=False, unique=True, index=True)
    plan = Column(String(50), nullable=False, default="free")
    plan_id = Column(String(50), nullable=False, default="free")
    monthly_ticket_limit = Column(Integer, nullable=False, default=50)
    contact_phone = Column(String(50), nullable=True)
    business_sector = Column(String(50), nullable=False, default="not_rbi_regulated")
    is_rbi_regulated = Column(Boolean, nullable=False, default=False)
    trial_ends_at = Column(DateTime(timezone=True), nullable=True)
    slack_webhook_url = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Custom AI prompt configuration (per-client)
    custom_prompt_enabled = Column(Boolean, nullable=False, default=False)
    custom_prompt_config = Column(JSON, nullable=True)
    custom_prompt_updated_at = Column(DateTime(timezone=True), nullable=True)

    complaints = relationship("Complaint", back_populates="client", cascade="all, delete-orphan")
    customers = relationship("Customer", back_populates="client", cascade="all, delete-orphan")
    reply_drafts = relationship("ReplyDraft", back_populates="client", cascade="all, delete-orphan")
    subscriptions = relationship("Subscription", back_populates="client", cascade="all, delete-orphan")
    invoices = relationship("Invoice", back_populates="client", cascade="all, delete-orphan")
    usage_records = relationship("UsageRecord", back_populates="client", cascade="all, delete-orphan")
    automation_rules = relationship("AutomationRule", back_populates="client", cascade="all, delete-orphan")
    rbi_tat_rules = relationship("RBITATRule", back_populates="client", cascade="all, delete-orphan")
    escalation_level_definitions = relationship("EscalationLevelDefinition", back_populates="client", cascade="all, delete-orphan")
    teams = relationship("Team", back_populates="client", cascade="all, delete-orphan")
    team_members = relationship("TeamMember", back_populates="client", cascade="all, delete-orphan")
    routing_rules = relationship("RoutingRule", back_populates="client", cascade="all, delete-orphan")


class Complaint(Base):
    __tablename__ = "complaints"
    __table_args__ = (
        Index("idx_complaints_response_time", "response_time_seconds"),
        Index("idx_complaints_team", "client_id", "team_id"),
        Index("idx_complaints_assigned_user", "client_id", "assigned_user_id"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(Uuid(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True)
    customer_id = Column(Uuid(as_uuid=True), ForeignKey("customers.id"), nullable=True, index=True)
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
    team_id = Column(Uuid(as_uuid=True), ForeignKey("teams.id"), nullable=True, index=True)
    assigned_team = Column(String(50), nullable=True)
    assigned_user_id = Column(Uuid(as_uuid=True), ForeignKey("client_users.id"), nullable=True, index=True)
    assigned_to = Column(String(255), nullable=True)
    ticket_id = Column(String(50), nullable=False, index=True)
    thread_id = Column(String(50), nullable=False, index=True)
    follow_up_status = Column(String(20), default="pending")
    resolution_status = Column(String(20), default="open")
    status = Column(String(50), nullable=False, default="PENDING")
    state = Column(String(50), nullable=False, default="new")
    state_changed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ticket_number = Column(String(50), unique=True, nullable=True)
    reopened_count = Column(Integer, nullable=False, default=0)
    last_reopened_at = Column(DateTime(timezone=True), nullable=True)
    sla_due_at = Column(DateTime(timezone=True), nullable=True)
    sla_status = Column(String(20), nullable=False, default="on_track")
    escalation_level = Column(Integer, nullable=False, default=0)
    escalated_at = Column(DateTime(timezone=True), nullable=True)
    escalated_to = Column(String(255), nullable=True)
    rbi_category_code = Column(String(20), nullable=True, index=True)
    tat_due_at = Column(DateTime(timezone=True), nullable=True, index=True)
    tat_status = Column(String(30), nullable=False, default="not_applicable")
    tat_breached_at = Column(DateTime(timezone=True), nullable=True)
    response_time_seconds = Column(Integer, nullable=True)
    first_response_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    customer_satisfaction_score = Column(Integer, nullable=True)
    satisfaction_score = Column(Integer, nullable=True)
    ai_reply = Column(Text, nullable=True)
    ai_reply_confidence = Column(Float, nullable=True)
    ai_reply_status = Column(String(50), nullable=False, default="pending")
    ai_reply_sent_at = Column(DateTime(timezone=True), nullable=True)
    last_replied_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=func.now(), server_default=func.now(), nullable=False)

    client = relationship("Client", back_populates="complaints")
    customer = relationship("Customer", back_populates="complaints")
    team = relationship("Team", back_populates="complaints")
    assigned_user = relationship("ClientUser", foreign_keys=[assigned_user_id], back_populates="assigned_complaints")
    reply_queue = relationship("AIReplyQueue", back_populates="complaint", uselist=False)
    reply_draft = relationship("ReplyDraft", back_populates="complaint", uselist=False)
    rbi_complaint = relationship("RBIComplaint", back_populates="complaint", uselist=False)
    escalations = relationship("Escalation", back_populates="ticket", cascade="all, delete-orphan")


class Team(Base):
    __tablename__ = "teams"
    __table_args__ = (
        UniqueConstraint("client_id", "name", name="uq_teams_client_name"),
        Index("idx_teams_client_name", "client_id", "name"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(Uuid(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    client = relationship("Client", back_populates="teams")
    complaints = relationship("Complaint", back_populates="team")
    members = relationship("TeamMember", back_populates="team", cascade="all, delete-orphan")
    routing_rules = relationship("RoutingRule", back_populates="team", cascade="all, delete-orphan")


class TeamMember(Base):
    __tablename__ = "team_members"
    __table_args__ = (
        UniqueConstraint("client_id", "team_id", "user_id", name="uq_team_members_client_team_user"),
        Index("idx_team_members_lookup", "client_id", "team_id", "role", "is_active"),
        Index("idx_team_members_capacity", "team_id", "is_active", "role", "active_tasks", "updated_at"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(Uuid(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True)
    team_id = Column(Uuid(as_uuid=True), ForeignKey("teams.id"), nullable=False, index=True)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("client_users.id"), nullable=False, index=True)
    role = Column(String(20), nullable=False, default="agent")
    capacity = Column(Integer, nullable=False, default=10)
    active_tasks = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    client = relationship("Client", back_populates="team_members")
    team = relationship("Team", back_populates="members")
    user = relationship("ClientUser", back_populates="team_memberships")


class RoutingRule(Base):
    __tablename__ = "routing_rules"
    __table_args__ = (
        UniqueConstraint("client_id", "category", name="uq_routing_rules_client_category"),
        Index("idx_routing_rules_client_category", "client_id", "category"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(Uuid(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True)
    category = Column(String(100), nullable=False)
    team_id = Column(Uuid(as_uuid=True), ForeignKey("teams.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    client = relationship("Client", back_populates="routing_rules")
    team = relationship("Team", back_populates="routing_rules")


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("client_id", "primary_email", name="uq_customers_client_primary_email"),
        Index("idx_customers_client", "client_id", postgresql_where=text("is_master = true")),
        Index("idx_customers_company", "client_id", "company_name"),
        Index("idx_customers_churn_risk", "client_id", "churn_risk_score"),
        Index("idx_customers_name", "client_id", "full_name"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(Uuid(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True)
    primary_email = Column(String(255), nullable=True, index=True)
    name = Column(String(255), nullable=True)
    primary_phone = Column(String(50), nullable=True, index=True)
    full_name = Column(String(255), nullable=True)
    company_name = Column(String(255), nullable=True)
    emails = Column(JSON, nullable=False, default=list)
    merged_emails = Column(JSON, nullable=False, default=list)
    phones = Column(JSON, nullable=False, default=list)
    customer_type = Column(String(50), nullable=False, default="individual")
    status = Column(String(50), nullable=False, default="active")
    tags = Column(JSON, nullable=False, default=list)
    notes = Column(Text, nullable=True)
    total_messages = Column(Integer, nullable=False, default=0)
    total_tickets = Column(Integer, nullable=False, default=0)
    open_tickets = Column(Integer, nullable=False, default=0)
    total_interactions = Column(Integer, nullable=False, default=0)
    first_interaction_at = Column(DateTime(timezone=True), nullable=True)
    last_interaction_at = Column(DateTime(timezone=True), nullable=True)
    last_contacted_at = Column(DateTime(timezone=True), nullable=True)
    avg_response_time = Column(Float, nullable=True)
    sentiment_score = Column(Float, nullable=True)
    sentiment_label = Column(String(50), nullable=True)
    churn_risk = Column(String(20), nullable=False, default="low")
    avg_satisfaction_score = Column(Float, nullable=True)
    churn_risk_score = Column(Float, nullable=False, default=0.0)
    lifetime_value = Column(Float, nullable=False, default=0.0)
    enrichment_data = Column(JSON, nullable=False, default=dict)
    custom_fields = Column(JSON, nullable=False, default=dict)
    is_master = Column(Boolean, nullable=False, default=True)
    merged_into = Column(Uuid(as_uuid=True), ForeignKey("customers.id"), nullable=True)
    confidence_score = Column(Float, nullable=False, default=1.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    client = relationship("Client", back_populates="customers")
    complaints = relationship("Complaint", back_populates="customer")
    reply_drafts = relationship("ReplyDraft", back_populates="customer")
    messages = relationship("UnifiedMessage", back_populates="customer")


class CustomerMergeHistory(Base):
    __tablename__ = "customer_merge_history"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(Uuid(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True)
    master_customer_id = Column(Uuid(as_uuid=True), ForeignKey("customers.id"), nullable=False, index=True)
    merged_customer_id = Column(Uuid(as_uuid=True), ForeignKey("customers.id"), nullable=False, index=True)
    merge_reason = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=True)
    merged_by = Column(String(255), nullable=True)
    auto_merged = Column(Boolean, nullable=False, default=False)
    merge_strategy = Column(String(50), nullable=True)
    metadata_json = Column("metadata", JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CustomerInteraction(Base):
    __tablename__ = "customer_interactions"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(Uuid(as_uuid=True), ForeignKey("customers.id"), nullable=False, index=True)
    client_id = Column(Uuid(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True)
    interaction_type = Column(String(50), nullable=False)
    interaction_channel = Column(String(50), nullable=True)
    complaint_id = Column(Uuid(as_uuid=True), ForeignKey("complaints.id"), nullable=True, index=True)
    summary = Column(Text, nullable=True)
    sentiment_score = Column(Float, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    metadata_json = Column("metadata", JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CustomerNote(Base):
    __tablename__ = "customer_notes"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(Uuid(as_uuid=True), ForeignKey("customers.id"), nullable=False, index=True)
    author_email = Column(String(255), nullable=False)
    note_type = Column(String(50), nullable=False, default="general")
    content = Column(Text, nullable=False)
    pinned = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class CustomerRelationship(Base):
    __tablename__ = "customer_relationships"
    __table_args__ = (
        Index("idx_relationships_parent", "parent_customer_id"),
        Index("idx_relationships_child", "child_customer_id"),
        UniqueConstraint("parent_customer_id", "child_customer_id", name="unique_parent_child"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(Uuid(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True)
    parent_customer_id = Column(Uuid(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    child_customer_id = Column(Uuid(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    relationship_type = Column(String(50), nullable=False)
    role_title = Column(String(100), nullable=True)
    is_primary_contact = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SLAPolicy(Base):
    __tablename__ = "sla_policies"
    __table_args__ = (Index("idx_sla_policies_client", "client_id"),)

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(Uuid(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    priority_level = Column(String(20), nullable=False)
    first_response_minutes = Column(Integer, nullable=False)
    resolution_minutes = Column(Integer, nullable=False)
    escalation_threshold_minutes = Column(Integer, nullable=True)
    business_hours_only = Column(Boolean, nullable=False, default=False)
    timezone = Column(String(50), nullable=False, default="UTC")
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class BusinessHours(Base):
    __tablename__ = "business_hours"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(Uuid(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True)
    day_of_week = Column(Integer, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    timezone = Column(String(50), nullable=False, default="UTC")
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class EscalationRule(Base):
    __tablename__ = "escalation_rules"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(Uuid(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True)
    rule_name = Column(String(100), nullable=False)
    trigger_condition = Column(String(50), nullable=False)
    escalation_level = Column(Integer, nullable=False)
    escalate_to_team = Column(String(100), nullable=True)
    escalate_to_email = Column(String(255), nullable=True)
    notification_template = Column(Text, nullable=True)
    category_code = Column(String(20), nullable=True, index=True)
    escalation_level_id = Column(Uuid(as_uuid=True), ForeignKey("escalation_level_definitions.id"), nullable=True)
    trigger_after_hours = Column(Integer, nullable=True)
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class EscalationLevelDefinition(Base):
    __tablename__ = "escalation_level_definitions"
    __table_args__ = (
        UniqueConstraint("client_id", "level_code", name="unique_client_level_code"),
        Index("idx_escalation_levels_client", "client_id"),
        Index("idx_escalation_levels_client_number", "client_id", "level_number"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(Uuid(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True)
    level_code = Column(String(20), nullable=False)  # L1, L2, IO
    level_number = Column(Integer, nullable=False)   # 1, 2, 3
    trigger_after_hours = Column(Integer, nullable=False)  # hours to escalate
    escalate_to_role = Column(String(255), nullable=False)  # email or role
    description = Column(String(500), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    client = relationship("Client", back_populates="escalation_level_definitions")


class Escalation(Base):
    __tablename__ = "escalations"
    __table_args__ = (
        Index("idx_escalations_ticket_created", "ticket_id", "created_at"),
        Index("idx_escalations_next_escalation", "next_escalation_at"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id = Column(Uuid(as_uuid=True), ForeignKey("complaints.id"), nullable=False, index=True)
    level = Column(Integer, nullable=False, default=1)
    escalated_to = Column(String(255), nullable=False)
    reason = Column(Text, nullable=True)
    escalation_level_id = Column(Uuid(as_uuid=True), ForeignKey("escalation_level_definitions.id"), nullable=True)
    metadata_json = Column(JSON, nullable=False, default=dict)
    next_escalation_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    ticket = relationship("Complaint", back_populates="escalations")


class TicketStateTransition(Base):
    __tablename__ = "ticket_state_transitions"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    complaint_id = Column(Uuid(as_uuid=True), ForeignKey("complaints.id"), nullable=False, index=True)
    from_state = Column(String(50), nullable=True)
    to_state = Column(String(50), nullable=False)
    transitioned_by = Column(String(255), nullable=False)
    transition_reason = Column(Text, nullable=True)
    metadata_json = Column("metadata", JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class TicketComment(Base):
    __tablename__ = "ticket_comments"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    complaint_id = Column(Uuid(as_uuid=True), ForeignKey("complaints.id"), nullable=False, index=True)
    author_email = Column(String(255), nullable=False)
    author_name = Column(String(255), nullable=True)
    comment_type = Column(String(20), nullable=False, default="note")
    content = Column(Text, nullable=False)
    is_internal = Column(Boolean, nullable=False, default=False)
    metadata_json = Column("metadata", JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class TicketAssignment(Base):
    __tablename__ = "ticket_assignments"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    complaint_id = Column(Uuid(as_uuid=True), ForeignKey("complaints.id"), nullable=False, index=True)
    assigned_to = Column(String(255), nullable=False)
    assigned_by = Column(String(255), nullable=True)
    assigned_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    unassigned_at = Column(DateTime(timezone=True), nullable=True)
    assignment_reason = Column(Text, nullable=True)


class ReplyTemplate(Base):
    __tablename__ = "reply_templates"
    __table_args__ = (
        UniqueConstraint("client_id", "name", name="unique_client_template"),
        Index("idx_templates_client_category", "client_id", "category"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(Uuid(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    category = Column(String(50), nullable=True)
    template_body = Column(Text, nullable=False)
    variables = Column(JSON, nullable=False, default=list)
    usage_count = Column(Integer, nullable=False, default=0)
    avg_satisfaction = Column(Float, nullable=True)
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ReplyDraft(Base):
    __tablename__ = "reply_drafts"
    __table_args__ = (
        UniqueConstraint("complaint_id", name="uq_reply_drafts_complaint"),
        UniqueConstraint("client_id", "ticket_id", name="uq_reply_drafts_client_ticket"),
        Index("idx_reply_drafts_status", "client_id", "status", "created_at"),
        Index("idx_reply_drafts_customer", "client_id", "customer_id", "created_at"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    complaint_id = Column(Uuid(as_uuid=True), ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False, index=True)
    client_id = Column(Uuid(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True)
    ticket_id = Column(String(50), nullable=False, index=True)
    customer_id = Column(Uuid(as_uuid=True), ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True)
    subject = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    confidence_score = Column(Float, nullable=True)
    prompt_version = Column(String(50), nullable=False, default="auto_reply_with_hitl_v1")
    generation_metadata = Column(JSON, nullable=False, default=dict)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    rejected_at = Column(DateTime(timezone=True), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    complaint = relationship("Complaint", back_populates="reply_draft")
    client = relationship("Client", back_populates="reply_drafts")
    customer = relationship("Customer", back_populates="reply_drafts")
    queue_entry = relationship("AIReplyQueue", back_populates="reply_draft", uselist=False)


class AIReplyQueue(Base):
    __tablename__ = "ai_reply_queue"
    __table_args__ = (
        UniqueConstraint("complaint_id", name="unique_complaint_queue"),
        UniqueConstraint("reply_draft_id", name="uq_ai_reply_queue_draft"),
        Index("idx_reply_queue_status", "client_id", "status", "created_at"),
        Index("idx_reply_queue_confidence", "client_id", "confidence_score"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    complaint_id = Column(Uuid(as_uuid=True), ForeignKey("complaints.id"), nullable=False, index=True)
    client_id = Column(Uuid(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True)
    reply_draft_id = Column(Uuid(as_uuid=True), ForeignKey("reply_drafts.id", ondelete="SET NULL"), nullable=True, index=True)
    generated_reply = Column(Text, nullable=False)
    confidence_score = Column(Float, nullable=False)
    generation_strategy = Column(String(50), nullable=True)
    generation_metadata = Column(JSON, nullable=False, default=dict)
    status = Column(String(50), nullable=False, default="pending")
    reviewed_by = Column(String(255), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    edited_reply = Column(Text, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    hallucination_check_passed = Column(Boolean, nullable=False, default=True)
    toxicity_score = Column(Float, nullable=False, default=0.0)
    factual_consistency_score = Column(Float, nullable=False, default=0.8)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    complaint = relationship("Complaint", back_populates="reply_queue")
    reply_draft = relationship("ReplyDraft", back_populates="queue_entry")


class ReplyFeedback(Base):
    __tablename__ = "reply_feedback"
    __table_args__ = (
        UniqueConstraint("complaint_id", name="unique_complaint_feedback"),
        Index("idx_feedback_queue", "reply_queue_id"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    complaint_id = Column(Uuid(as_uuid=True), ForeignKey("complaints.id"), nullable=False, index=True)
    reply_queue_id = Column(Uuid(as_uuid=True), ForeignKey("ai_reply_queue.id"), nullable=True, index=True)
    customer_responded = Column(Boolean, nullable=False, default=False)
    customer_response_sentiment = Column(Float, nullable=True)
    ticket_reopened = Column(Boolean, nullable=False, default=False)
    escalated_after_reply = Column(Boolean, nullable=False, default=False)
    satisfaction_score = Column(Integer, nullable=True)
    time_to_customer_response_seconds = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ReplyABTest(Base):
    __tablename__ = "reply_ab_tests"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(Uuid(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True)
    test_name = Column(String(100), nullable=False)
    variant_a_strategy = Column(String(100), nullable=True)
    variant_b_strategy = Column(String(100), nullable=True)
    traffic_split = Column(Float, nullable=False, default=0.5)
    status = Column(String(20), nullable=False, default="active")
    start_date = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=True)
    winner = Column(String(10), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ReplyQualityMetric(Base):
    __tablename__ = "reply_quality_metrics"
    __table_args__ = (
        UniqueConstraint("client_id", "period_start", "period_end", name="unique_client_period"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(Uuid(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True)
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    total_replies_generated = Column(Integer, nullable=False, default=0)
    auto_approved_count = Column(Integer, nullable=False, default=0)
    human_approved_count = Column(Integer, nullable=False, default=0)
    rejected_count = Column(Integer, nullable=False, default=0)
    avg_confidence_score = Column(Float, nullable=True)
    avg_satisfaction_score = Column(Float, nullable=True)
    hallucination_rate = Column(Float, nullable=True)
    reopened_rate = Column(Float, nullable=True)
    escalation_rate = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class RBIComplaintCategory(Base):
    __tablename__ = "rbi_complaint_categories"
    __table_args__ = (
        UniqueConstraint("category_code", "subcategory_code", name="unique_rbi_category_subcategory"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category_code = Column(String(20), nullable=False, index=True)
    category_name = Column(String(100), nullable=False)
    subcategory_code = Column(String(20), nullable=False, index=True)
    subcategory_name = Column(String(100), nullable=True)
    tat_days = Column(Integer, nullable=False, default=30)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class RBICategory(Base):
    __tablename__ = "rbi_categories"
    __table_args__ = (
        UniqueConstraint("category_code", "subcategory_code", name="unique_rbi_categories_category_subcategory"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category_code = Column(String(20), nullable=False, index=True)
    category_name = Column(String(100), nullable=False)
    subcategory_code = Column(String(20), nullable=False, index=True)
    subcategory_name = Column(String(100), nullable=True)
    tat_days = Column(Integer, nullable=False, default=30)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class RBIComplaint(Base):
    __tablename__ = "rbi_complaints"
    __table_args__ = (
        UniqueConstraint("complaint_id", name="unique_complaint_rbi"),
        Index("idx_rbi_complaints_client", "client_id", "created_at"),
        Index("idx_rbi_complaints_category", "category_code", "subcategory_code"),
        Index("idx_rbi_reference", "rbi_reference_number"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    complaint_id = Column(Uuid(as_uuid=True), ForeignKey("complaints.id"), nullable=False, index=True)
    client_id = Column(Uuid(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True)
    rbi_category_id = Column(Uuid(as_uuid=True), ForeignKey("rbi_complaint_categories.id"), nullable=True, index=True)
    category_code = Column(String(20), nullable=True)
    subcategory_code = Column(String(20), nullable=True)
    rbi_reference_number = Column(String(50), nullable=True, unique=True)
    escalation_level = Column(Integer, nullable=False, default=0)
    escalated_to_rbi = Column(Boolean, nullable=False, default=False)
    rbi_escalation_date = Column(DateTime(timezone=True), nullable=True)
    tat_due_date = Column(DateTime(timezone=True), nullable=False)
    tat_status = Column(String(20), nullable=False, default="within_tat")
    tat_breach_hours = Column(Integer, nullable=True)
    resolution_date = Column(DateTime(timezone=True), nullable=True)
    resolution_summary = Column(Text, nullable=True)
    customer_satisfied = Column(Boolean, nullable=True)
    audit_log = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    complaint = relationship("Complaint", back_populates="rbi_complaint")


class RBIEscalationLog(Base):
    __tablename__ = "rbi_escalation_log"
    __table_args__ = (
        Index("idx_escalation_log_complaint", "rbi_complaint_id", "escalated_at"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rbi_complaint_id = Column(Uuid(as_uuid=True), ForeignKey("rbi_complaints.id"), nullable=False, index=True)
    from_level = Column(Integer, nullable=False)
    to_level = Column(Integer, nullable=False)
    escalation_reason = Column(Text, nullable=False)
    escalated_by = Column(String(255), nullable=False)
    escalated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    metadata_json = Column("metadata", JSON, nullable=False, default=dict)


class RBIMISReport(Base):
    __tablename__ = "rbi_mis_reports"
    __table_args__ = (
        UniqueConstraint("client_id", "report_month", name="unique_client_month"),
        Index("idx_mis_reports_client_month", "client_id", "report_month"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(Uuid(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True)
    report_month = Column(Date, nullable=False)
    total_complaints = Column(Integer, nullable=False, default=0)
    complaints_by_category = Column(JSON, nullable=False, default=dict)
    resolved_within_tat = Column(Integer, nullable=False, default=0)
    tat_breach_count = Column(Integer, nullable=False, default=0)
    avg_resolution_days = Column(Float, nullable=True)
    pending_complaints = Column(Integer, nullable=False, default=0)
    escalated_to_regional = Column(Integer, nullable=False, default=0)
    escalated_to_nodal = Column(Integer, nullable=False, default=0)
    escalated_to_ombudsman = Column(Integer, nullable=False, default=0)
    satisfaction_rate = Column(Float, nullable=True)
    generated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    report_data = Column(JSON, nullable=False, default=dict)


class RBITATRule(Base):
    __tablename__ = "rbi_tat_rules"
    __table_args__ = (
        UniqueConstraint("client_id", "category_code", name="unique_client_tat_rule"),
        Index("idx_tat_rules_client", "client_id"),
        Index("idx_tat_rules_category", "category_code"),
        Index("idx_tat_rules_lookup", "client_id", "category_code", "is_active"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(Uuid(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True)
    category_code = Column(String(20), nullable=False)
    tat_days = Column(Integer, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    client = relationship("Client", back_populates="rbi_tat_rules")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("idx_audit_logs_entity", "entity_type", "entity_id", "timestamp"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type = Column(String(50), nullable=False, index=True)
    entity_id = Column(Uuid(as_uuid=True), nullable=False, index=True)
    action = Column(String(100), nullable=False, index=True)
    performed_by = Column(String(255), nullable=True)
    old_value = Column(JSON().with_variant(JSONB(astext_type=Text()), "postgresql"), nullable=True)
    new_value = Column(JSON().with_variant(JSONB(astext_type=Text()), "postgresql"), nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)


class PlanFeature(Base):
    __tablename__ = "plan_features"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_name = Column(String(50), nullable=False, unique=True, index=True)
    features = Column(JSON().with_variant(JSONB(astext_type=Text()), "postgresql"), nullable=False, default=dict)
    limits = Column(JSON().with_variant(JSONB(astext_type=Text()), "postgresql"), nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class TenantUsageTracking(Base):
    __tablename__ = "tenant_usage_tracking"
    __table_args__ = (
        UniqueConstraint("client_id", "resource_type", "period_start", name="unique_client_resource_period"),
        Index("idx_usage_tracking_client", "client_id", "period_start"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(Uuid(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True)
    resource_type = Column(String(50), nullable=False)
    usage_count = Column(Integer, nullable=False, default=0)
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ClientUser(Base):
    __tablename__ = "client_users"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(Uuid(as_uuid=True), ForeignKey("clients.id"), nullable=False)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    team_memberships = relationship("TeamMember", back_populates="user")
    assigned_complaints = relationship("Complaint", foreign_keys="Complaint.assigned_user_id", back_populates="assigned_user")


class EventLog(Base):
    __tablename__ = "event_logs"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(Uuid(as_uuid=True), nullable=True)
    event_type = Column(String(100), nullable=False)
    payload = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AutomationRule(Base):
    __tablename__ = "automation_rules"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(Uuid(as_uuid=True), ForeignKey("clients.id"), nullable=False)
    trigger_type = Column(String(50), nullable=False)
    trigger_value = Column(String(100), nullable=False)
    action_type = Column(String(50), nullable=False)
    action_config = Column(JSON, nullable=True)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    client = relationship("Client", back_populates="automation_rules")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(Uuid(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True)
    plan = Column("plan_id", String(50), nullable=False)
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

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(Uuid(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True)
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

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(Uuid(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True)
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

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(Uuid(as_uuid=True), nullable=True)
    request_id = Column(String(100), nullable=False, index=True)
    path = Column(String(255), nullable=False, index=True)
    method = Column(String(20), nullable=False)
    ip_address = Column(String(100), nullable=False, index=True)
    user_agent = Column(String(500), nullable=True)
    status_code = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MaterializedAnalytics(Base):
    __tablename__ = "materialized_analytics"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(Uuid(as_uuid=True), nullable=False, index=True)
    metric_key = Column(String(100), nullable=False, index=True)
    metric_value = Column(JSON, nullable=False)
    period_start = Column(DateTime(timezone=True), nullable=True)
    period_end = Column(DateTime(timezone=True), nullable=True)
    generated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class JobQueue(Base):
    __tablename__ = "job_queue"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
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

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cache_key = Column(String(255), nullable=False, unique=True, index=True)
    prompt = Column(Text, nullable=False)
    response = Column(Text, nullable=False)
    hit_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class MonitoringMetric(Base):
    __tablename__ = "monitoring_metrics"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    metric_name = Column(String(100), nullable=False, index=True)
    metric_value = Column(Float, nullable=False, default=0.0)
    dimensions = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class WaitlistEntry(Base):
    __tablename__ = "waitlist_entries"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), nullable=False, unique=True)
    details = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DemoRequest(Base):
    __tablename__ = "demo_requests"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), nullable=False)
    name = Column(String(255), nullable=True)
    company = Column(String(255), nullable=True)
    details = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ChannelConnection(Base):
    __tablename__ = "channel_connections"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(Uuid(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True)
    channel_type = Column(String(50), nullable=False, index=True)
    account_identifier = Column(String(255), nullable=True)
    access_token = Column(Text, nullable=True)
    refresh_token = Column(Text, nullable=True)
    token_expiry = Column(DateTime(timezone=True), nullable=True)
    metadata_json = Column("metadata", JSON().with_variant(JSONB(astext_type=Text()), "postgresql"), nullable=False, default=dict)
    status = Column(String(20), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class UnifiedMessage(Base):
    __tablename__ = "unified_messages"
    __table_args__ = (
        UniqueConstraint("channel", "external_message_id", name="uq_unified_messages_channel_external_message"),
        Index("idx_unified_messages_client_channel", "client_id", "channel"),
        Index("idx_unified_messages_external_message_id", "external_message_id"),
        Index("idx_unified_messages_status", "status"),
        Index("idx_unified_messages_next_retry_at", "next_retry_at"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(Uuid(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True)
    customer_id = Column(Uuid(as_uuid=True), ForeignKey("customers.id"), nullable=True, index=True)
    channel = Column(String(50), nullable=False)
    external_message_id = Column(String(255), nullable=False)
    external_thread_id = Column(String(255), nullable=True)
    sender_id = Column(String(255), nullable=True)
    sender_name = Column(String(255), nullable=True)
    message_text = Column(Text, nullable=True)
    attachments = Column(JSON().with_variant(JSONB(astext_type=Text()), "postgresql"), nullable=False, default=list)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    direction = Column(String(20), nullable=False)
    status = Column(String(50), nullable=False)
    raw_payload = Column(JSON().with_variant(JSONB(astext_type=Text()), "postgresql"), nullable=False, default=dict)
    retry_count = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)
    next_retry_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    customer = relationship("Customer", back_populates="messages")


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        Index("idx_conversations_client_external_thread", "client_id", "external_thread_id"),
        Index("idx_conversations_last_message_at", "last_message_at"),
        Index("idx_conversations_escalation_level", "client_id", "escalation_level"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(Uuid(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True)
    channel = Column(String(50), nullable=False)
    external_thread_id = Column(String(255), nullable=False)
    customer_id = Column(String(255), nullable=True)
    last_message_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(50), nullable=False, default="open")
    assigned_to = Column(Uuid(as_uuid=True), nullable=True)
    escalation_level = Column(Integer, nullable=False, default=0)
    last_escalated_at = Column(DateTime(timezone=True), nullable=True)
    escalation_metadata_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AutomationSetting(Base):
    __tablename__ = "automation_settings"
    __table_args__ = (
        UniqueConstraint("client_id", "channel", name="uq_automation_settings_client_channel"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(Uuid(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True)
    channel = Column(String(50), nullable=False)
    auto_reply_enabled = Column(Boolean, nullable=False, default=False)
    confidence_threshold = Column(Float, nullable=False, default=0.8)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MessageEvent(Base):
    __tablename__ = "message_events"
    __table_args__ = (
        Index("idx_message_events_message_id", "message_id"),
        Index("idx_message_events_event_type", "event_type"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id = Column(Uuid(as_uuid=True), nullable=True, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    payload = Column(JSON().with_variant(JSONB(astext_type=Text()), "postgresql"), nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
