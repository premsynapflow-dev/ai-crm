-- SynapFlow Database Schema for Mumbai (ap-south-1) Supabase
-- Copy and paste this entire file into the Supabase SQL Editor
-- This creates all tables from scratch

-- Create extension for UUID
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Clients table
CREATE TABLE IF NOT EXISTS clients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    api_key VARCHAR(255) NOT NULL UNIQUE,
    plan VARCHAR(50) NOT NULL DEFAULT 'free',
    plan_id VARCHAR(50) NOT NULL DEFAULT 'free',
    monthly_ticket_limit INTEGER NOT NULL DEFAULT 50,
    contact_phone VARCHAR(50),
    business_sector VARCHAR(50) NOT NULL DEFAULT 'not_rbi_regulated',
    is_rbi_regulated BOOLEAN NOT NULL DEFAULT FALSE,
    trial_ends_at TIMESTAMPTZ,
    slack_webhook_url VARCHAR(500),
    custom_prompt_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    custom_prompt_config JSONB,
    custom_prompt_updated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_clients_api_key ON clients(api_key);

-- Client users table
CREATE TABLE IF NOT EXISTS client_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    role VARCHAR(50) NOT NULL DEFAULT 'agent',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(client_id, email)
);

CREATE INDEX idx_client_users_client ON client_users(client_id);
CREATE INDEX idx_client_users_email ON client_users(email);

-- Teams table
CREATE TABLE IF NOT EXISTS teams (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(client_id, name)
);

CREATE INDEX idx_teams_client ON teams(client_id);

-- Team members table
CREATE TABLE IF NOT EXISTS team_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    team_id UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES client_users(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL DEFAULT 'agent',
    capacity INTEGER NOT NULL DEFAULT 10,
    active_tasks INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(client_id, team_id, user_id)
);

CREATE INDEX idx_team_members_client ON team_members(client_id);
CREATE INDEX idx_team_members_team ON team_members(team_id);

-- Customers table
CREATE TABLE IF NOT EXISTS customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    primary_email VARCHAR(255),
    name VARCHAR(255),
    primary_phone VARCHAR(50),
    full_name VARCHAR(255),
    company_name VARCHAR(255),
    emails JSONB NOT NULL DEFAULT '[]',
    merged_emails JSONB NOT NULL DEFAULT '[]',
    phones JSONB NOT NULL DEFAULT '[]',
    customer_type VARCHAR(50) NOT NULL DEFAULT 'individual',
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    tags JSONB NOT NULL DEFAULT '[]',
    notes TEXT,
    total_messages INTEGER NOT NULL DEFAULT 0,
    total_tickets INTEGER NOT NULL DEFAULT 0,
    open_tickets INTEGER NOT NULL DEFAULT 0,
    total_interactions INTEGER NOT NULL DEFAULT 0,
    first_interaction_at TIMESTAMPTZ,
    last_interaction_at TIMESTAMPTZ,
    last_contacted_at TIMESTAMPTZ,
    avg_response_time FLOAT,
    sentiment_score FLOAT,
    sentiment_label VARCHAR(50),
    churn_risk VARCHAR(20) NOT NULL DEFAULT 'low',
    avg_satisfaction_score FLOAT,
    churn_risk_score FLOAT NOT NULL DEFAULT 0.0,
    lifetime_value FLOAT NOT NULL DEFAULT 0.0,
    enrichment_data JSONB NOT NULL DEFAULT '{}',
    custom_fields JSONB NOT NULL DEFAULT '{}',
    is_master BOOLEAN NOT NULL DEFAULT TRUE,
    merged_into UUID REFERENCES customers(id),
    confidence_score FLOAT NOT NULL DEFAULT 1.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(client_id, primary_email)
);

CREATE INDEX idx_customers_client ON customers(client_id);
CREATE INDEX idx_customers_primary_email ON customers(primary_email);
CREATE INDEX idx_customers_primary_phone ON customers(primary_phone);
CREATE INDEX idx_customers_company ON customers(client_id, company_name);
CREATE INDEX idx_customers_churn_risk ON customers(client_id, churn_risk_score);

-- Routing rules table
CREATE TABLE IF NOT EXISTS routing_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    category VARCHAR(100) NOT NULL,
    team_id UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(client_id, category)
);

CREATE INDEX idx_routing_rules_client ON routing_rules(client_id);

-- Escalation level definitions table
CREATE TABLE IF NOT EXISTS escalation_level_definitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    level_code VARCHAR(20) NOT NULL,
    level_number INTEGER NOT NULL,
    trigger_after_hours INTEGER NOT NULL,
    escalate_to_role VARCHAR(255) NOT NULL,
    description VARCHAR(500),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(client_id, level_code)
);

CREATE INDEX idx_escalation_levels_client ON escalation_level_definitions(client_id);

-- Complaints table
CREATE TABLE IF NOT EXISTS complaints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    customer_id UUID REFERENCES customers(id) ON DELETE SET NULL,
    summary VARCHAR(500) NOT NULL,
    source VARCHAR(50) NOT NULL DEFAULT 'api',
    customer_email VARCHAR(255),
    customer_phone VARCHAR(50),
    intent VARCHAR(100),
    recommended_action VARCHAR(100),
    confidence FLOAT,
    priority INTEGER,
    category VARCHAR(100) NOT NULL,
    sentiment FLOAT NOT NULL DEFAULT 0.0,
    sentiment_score INTEGER,
    sentiment_label VARCHAR(50),
    sentiment_indicators JSONB,
    urgency_score FLOAT NOT NULL DEFAULT 0.0,
    team_id UUID REFERENCES teams(id) ON DELETE SET NULL,
    assigned_team VARCHAR(50),
    assigned_user_id UUID REFERENCES client_users(id) ON DELETE SET NULL,
    assigned_to VARCHAR(255),
    ticket_id VARCHAR(50) NOT NULL,
    thread_id VARCHAR(50) NOT NULL,
    follow_up_status VARCHAR(20) DEFAULT 'pending',
    resolution_status VARCHAR(20) DEFAULT 'open',
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
    state VARCHAR(50) NOT NULL DEFAULT 'new',
    state_changed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ticket_number VARCHAR(50) UNIQUE,
    reopened_count INTEGER NOT NULL DEFAULT 0,
    last_reopened_at TIMESTAMPTZ,
    sla_due_at TIMESTAMPTZ,
    sla_status VARCHAR(20) NOT NULL DEFAULT 'on_track',
    escalation_level INTEGER NOT NULL DEFAULT 0,
    escalated_at TIMESTAMPTZ,
    escalated_to VARCHAR(255),
    rbi_category_code VARCHAR(20),
    tat_due_at TIMESTAMPTZ,
    tat_status VARCHAR(30) NOT NULL DEFAULT 'not_applicable',
    tat_breached_at TIMESTAMPTZ,
    response_time_seconds INTEGER,
    first_response_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    customer_satisfaction_score INTEGER,
    satisfaction_score INTEGER,
    ai_reply TEXT,
    ai_reply_confidence FLOAT,
    ai_reply_status VARCHAR(50) NOT NULL DEFAULT 'pending',
    ai_reply_sent_at TIMESTAMPTZ,
    last_replied_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_complaints_client ON complaints(client_id);
CREATE INDEX idx_complaints_customer ON complaints(customer_id);
CREATE INDEX idx_complaints_team ON complaints(client_id, team_id);
CREATE INDEX idx_complaints_assigned_user ON complaints(client_id, assigned_user_id);
CREATE INDEX idx_complaints_ticket_id ON complaints(ticket_id);
CREATE INDEX idx_complaints_thread_id ON complaints(thread_id);
CREATE INDEX idx_complaints_rbi_category ON complaints(rbi_category_code);
CREATE INDEX idx_complaints_tat_due ON complaints(tat_due_at);
CREATE INDEX idx_complaints_response_time ON complaints(response_time_seconds);
CREATE INDEX idx_complaints_status ON complaints(client_id, status);

-- Customer interactions table
CREATE TABLE IF NOT EXISTS customer_interactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    interaction_type VARCHAR(50) NOT NULL,
    interaction_channel VARCHAR(50),
    complaint_id UUID REFERENCES complaints(id) ON DELETE SET NULL,
    summary TEXT,
    sentiment_score FLOAT,
    duration_seconds INTEGER,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_customer_interactions_customer ON customer_interactions(customer_id);
CREATE INDEX idx_customer_interactions_complaint ON customer_interactions(complaint_id);

-- Customer events table (APPEND-ONLY)
CREATE TABLE IF NOT EXISTS customer_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    complaint_id UUID REFERENCES complaints(id),
    event_type VARCHAR(50) NOT NULL,
    event_data JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_customer_events_customer ON customer_events(customer_id);
CREATE INDEX idx_customer_events_complaint ON customer_events(complaint_id);
CREATE INDEX idx_customer_events_type ON customer_events(event_type);

-- Prevent updates on customer_events (append-only)
CREATE OR REPLACE FUNCTION prevent_customer_events_update() RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'customer_events is append-only and cannot be updated or deleted';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER customer_events_no_update
    BEFORE UPDATE OR DELETE ON customer_events
    FOR EACH ROW
    EXECUTE FUNCTION prevent_customer_events_update();

-- Reply drafts table
CREATE TABLE IF NOT EXISTS reply_drafts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    complaint_id UUID NOT NULL REFERENCES complaints(id) ON DELETE CASCADE,
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    ticket_id VARCHAR(50) NOT NULL,
    customer_id UUID REFERENCES customers(id) ON DELETE SET NULL,
    subject VARCHAR(255) NOT NULL,
    body TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    confidence_score FLOAT,
    prompt_version VARCHAR(50) NOT NULL DEFAULT 'auto_reply_with_hitl_v1',
    generation_metadata JSONB NOT NULL DEFAULT '{}',
    approved_at TIMESTAMPTZ,
    rejected_at TIMESTAMPTZ,
    sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(complaint_id),
    UNIQUE(client_id, ticket_id)
);

CREATE INDEX idx_reply_drafts_client ON reply_drafts(client_id);
CREATE INDEX idx_reply_drafts_status ON reply_drafts(client_id, status, created_at);
CREATE INDEX idx_reply_drafts_customer ON reply_drafts(client_id, customer_id, created_at);

-- AI reply queue table
CREATE TABLE IF NOT EXISTS ai_reply_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    complaint_id UUID NOT NULL REFERENCES complaints(id) ON DELETE CASCADE,
    reply_draft_id UUID NOT NULL REFERENCES reply_drafts(id) ON DELETE CASCADE,
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    confidence_score FLOAT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(complaint_id),
    UNIQUE(reply_draft_id)
);

CREATE INDEX idx_ai_reply_queue_client ON ai_reply_queue(client_id);
CREATE INDEX idx_ai_reply_queue_status ON ai_reply_queue(client_id, status, created_at);
CREATE INDEX idx_ai_reply_queue_confidence ON ai_reply_queue(client_id, confidence_score);

-- Event logs table
CREATE TABLE IF NOT EXISTS event_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    complaint_id UUID REFERENCES complaints(id) ON DELETE SET NULL,
    event_type VARCHAR(50) NOT NULL,
    actor_email VARCHAR(255),
    actor_type VARCHAR(50),
    action VARCHAR(50) NOT NULL,
    action_details TEXT,
    changes JSONB,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_event_logs_client ON event_logs(client_id);
CREATE INDEX idx_event_logs_complaint ON event_logs(complaint_id);
CREATE INDEX idx_event_logs_type ON event_logs(event_type);

-- Model audit log table
CREATE TABLE IF NOT EXISTS model_audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    complaint_id UUID REFERENCES complaints(id) ON DELETE SET NULL,
    provider VARCHAR(50) NOT NULL,
    model VARCHAR(100) NOT NULL,
    task_type VARCHAR(50) NOT NULL,
    confidence_score FLOAT,
    latency_ms INTEGER,
    status VARCHAR(20) NOT NULL DEFAULT 'succeeded',
    error_message TEXT,
    prompt_preview TEXT,
    output_preview TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_model_audit_logs_client ON model_audit_logs(client_id);
CREATE INDEX idx_model_audit_logs_task_type ON model_audit_logs(task_type);

-- Message events table
CREATE TABLE IF NOT EXISTS message_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    complaint_id UUID REFERENCES complaints(id) ON DELETE SET NULL,
    message_id VARCHAR(255),
    thread_id VARCHAR(255),
    direction VARCHAR(20),
    source VARCHAR(50),
    sender VARCHAR(255),
    recipient VARCHAR(255),
    subject VARCHAR(500),
    body TEXT,
    external_id VARCHAR(255) UNIQUE,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_message_events_client ON message_events(client_id);
CREATE INDEX idx_message_events_complaint ON message_events(complaint_id);
CREATE INDEX idx_message_events_thread ON message_events(thread_id);

-- Escalations table
CREATE TABLE IF NOT EXISTS escalations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id UUID NOT NULL REFERENCES complaints(id) ON DELETE CASCADE,
    level INTEGER NOT NULL DEFAULT 1,
    escalated_to VARCHAR(255) NOT NULL,
    reason TEXT,
    escalation_level_id UUID REFERENCES escalation_level_definitions(id),
    metadata JSONB NOT NULL DEFAULT '{}',
    next_escalation_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_escalations_ticket ON escalations(ticket_id, created_at);
CREATE INDEX idx_escalations_next ON escalations(next_escalation_at);

-- Workflow executions table
CREATE TABLE IF NOT EXISTS workflow_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    complaint_id UUID REFERENCES complaints(id) ON DELETE SET NULL,
    workflow_type VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    execution_metadata JSONB NOT NULL DEFAULT '{}',
    error_message TEXT,
    down_revision VARCHAR(50),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_workflow_executions_client ON workflow_executions(client_id);
CREATE INDEX idx_workflow_executions_complaint ON workflow_executions(complaint_id);
CREATE INDEX idx_workflow_executions_status ON workflow_executions(status);

-- Agent correction table
CREATE TABLE IF NOT EXISTS agent_corrections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    complaint_id UUID REFERENCES complaints(id) ON DELETE SET NULL,
    correction_type VARCHAR(50),
    original_value TEXT,
    corrected_value TEXT,
    field_name VARCHAR(100),
    correction_reason TEXT,
    corrected_by VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_agent_corrections_client ON agent_corrections(client_id);
CREATE INDEX idx_agent_corrections_complaint ON agent_corrections(complaint_id);

-- Subscriptions table
CREATE TABLE IF NOT EXISTS subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    plan_id VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    billing_cycle VARCHAR(20),
    amount FLOAT,
    currency VARCHAR(10) DEFAULT 'INR',
    start_date TIMESTAMPTZ,
    end_date TIMESTAMPTZ,
    auto_renew BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_subscriptions_client ON subscriptions(client_id);
CREATE INDEX idx_subscriptions_status ON subscriptions(status);

-- Invoices table
CREATE TABLE IF NOT EXISTS invoices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    invoice_number VARCHAR(50) UNIQUE,
    amount FLOAT NOT NULL,
    currency VARCHAR(10) DEFAULT 'INR',
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    issued_at TIMESTAMPTZ,
    due_at TIMESTAMPTZ,
    paid_at TIMESTAMPTZ,
    payment_method VARCHAR(50),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_invoices_client ON invoices(client_id);
CREATE INDEX idx_invoices_status ON invoices(status);

-- Usage records table
CREATE TABLE IF NOT EXISTS usage_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    metric_type VARCHAR(50) NOT NULL,
    metric_value INTEGER,
    billing_period_start TIMESTAMPTZ,
    billing_period_end TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_usage_records_client ON usage_records(client_id);
CREATE INDEX idx_usage_records_period ON usage_records(billing_period_start, billing_period_end);

-- Queue jobs table (for background job queue)
CREATE TABLE IF NOT EXISTS queue_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID REFERENCES clients(id) ON DELETE SET NULL,
    job_type VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}',
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    priority INTEGER DEFAULT 0,
    retry_count INTEGER DEFAULT 0,
    last_error TEXT,
    scheduled_for TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_queue_jobs_status ON queue_jobs(status);
CREATE INDEX idx_queue_jobs_client ON queue_jobs(client_id);
CREATE INDEX idx_queue_jobs_scheduled ON queue_jobs(scheduled_for);

-- RBI TAT rules table
CREATE TABLE IF NOT EXISTS rbi_tat_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    category_code VARCHAR(20) NOT NULL,
    tat_days INTEGER NOT NULL DEFAULT 30,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(client_id, category_code)
);

CREATE INDEX idx_rbi_tat_rules_client ON rbi_tat_rules(client_id);

-- Automation rules table
CREATE TABLE IF NOT EXISTS automation_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    rule_name VARCHAR(255) NOT NULL,
    trigger_event VARCHAR(100) NOT NULL,
    conditions JSONB NOT NULL DEFAULT '{}',
    actions JSONB NOT NULL DEFAULT '[]',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_automation_rules_client ON automation_rules(client_id);
CREATE INDEX idx_automation_rules_event ON automation_rules(trigger_event);

-- RBI complaint table
CREATE TABLE IF NOT EXISTS rbi_complaints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    complaint_id UUID REFERENCES complaints(id) ON DELETE SET NULL,
    rbi_category_code VARCHAR(20) NOT NULL,
    tat_due_at TIMESTAMPTZ,
    tat_breached_at TIMESTAMPTZ,
    mis_reported_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_rbi_complaints_client ON rbi_complaints(client_id);
CREATE INDEX idx_rbi_complaints_complaint ON rbi_complaints(complaint_id);
CREATE INDEX idx_rbi_complaints_category ON rbi_complaints(rbi_category_code);

-- Unified messages table
CREATE TABLE IF NOT EXISTS unified_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    customer_id UUID REFERENCES customers(id) ON DELETE SET NULL,
    complaint_id UUID REFERENCES complaints(id) ON DELETE SET NULL,
    direction VARCHAR(20),
    source VARCHAR(50),
    sender VARCHAR(255),
    recipient VARCHAR(255),
    subject VARCHAR(500),
    body TEXT,
    external_id VARCHAR(255) UNIQUE,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_unified_messages_client ON unified_messages(client_id);
CREATE INDEX idx_unified_messages_customer ON unified_messages(customer_id);
CREATE INDEX idx_unified_messages_complaint ON unified_messages(complaint_id);

-- Ticket state transitions table
CREATE TABLE IF NOT EXISTS ticket_state_transitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    complaint_id UUID NOT NULL REFERENCES complaints(id) ON DELETE CASCADE,
    from_state VARCHAR(50),
    to_state VARCHAR(50) NOT NULL,
    transitioned_by VARCHAR(255) NOT NULL,
    transition_reason TEXT,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_ticket_state_transitions_complaint ON ticket_state_transitions(complaint_id);

-- Ticket comments table
CREATE TABLE IF NOT EXISTS ticket_comments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    complaint_id UUID NOT NULL REFERENCES complaints(id) ON DELETE CASCADE,
    author_email VARCHAR(255) NOT NULL,
    author_name VARCHAR(255),
    comment_type VARCHAR(20) NOT NULL DEFAULT 'note',
    content TEXT NOT NULL,
    is_internal BOOLEAN NOT NULL DEFAULT FALSE,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_ticket_comments_complaint ON ticket_comments(complaint_id);

-- Reply templates table
CREATE TABLE IF NOT EXISTS reply_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    category VARCHAR(50),
    template_body TEXT NOT NULL,
    variables JSONB NOT NULL DEFAULT '[]',
    usage_count INTEGER DEFAULT 0,
    avg_satisfaction FLOAT,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(client_id, name)
);

CREATE INDEX idx_reply_templates_client ON reply_templates(client_id);

-- SLA policies table
CREATE TABLE IF NOT EXISTS sla_policies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    priority_level VARCHAR(20) NOT NULL,
    first_response_minutes INTEGER NOT NULL,
    resolution_minutes INTEGER NOT NULL,
    escalation_threshold_minutes INTEGER,
    business_hours_only BOOLEAN DEFAULT FALSE,
    timezone VARCHAR(50) DEFAULT 'UTC',
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_sla_policies_client ON sla_policies(client_id);

-- Business hours table
CREATE TABLE IF NOT EXISTS business_hours (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    day_of_week INTEGER NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    timezone VARCHAR(50) DEFAULT 'UTC',
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_business_hours_client ON business_hours(client_id);

-- Escalation rules table
CREATE TABLE IF NOT EXISTS escalation_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    rule_name VARCHAR(100) NOT NULL,
    trigger_condition VARCHAR(50) NOT NULL,
    escalation_level INTEGER NOT NULL,
    escalate_to_team VARCHAR(100),
    escalate_to_email VARCHAR(255),
    notification_template TEXT,
    category_code VARCHAR(20),
    escalation_level_id UUID REFERENCES escalation_level_definitions(id),
    trigger_after_hours INTEGER,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_escalation_rules_client ON escalation_rules(client_id);

-- Customer merge history table
CREATE TABLE IF NOT EXISTS customer_merge_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    master_customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    merged_customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    merge_reason TEXT,
    confidence_score FLOAT,
    merged_by VARCHAR(255),
    auto_merged BOOLEAN DEFAULT FALSE,
    merge_strategy VARCHAR(50),
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_customer_merge_history_client ON customer_merge_history(client_id);

-- Customer notes table
CREATE TABLE IF NOT EXISTS customer_notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    author_email VARCHAR(255) NOT NULL,
    note_type VARCHAR(50) DEFAULT 'general',
    content TEXT NOT NULL,
    pinned BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_customer_notes_customer ON customer_notes(customer_id);

-- Customer relationships table
CREATE TABLE IF NOT EXISTS customer_relationships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    parent_customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    child_customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    relationship_type VARCHAR(50) NOT NULL,
    role_title VARCHAR(100),
    is_primary_contact BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(parent_customer_id, child_customer_id)
);

CREATE INDEX idx_customer_relationships_parent ON customer_relationships(parent_customer_id);
CREATE INDEX idx_customer_relationships_child ON customer_relationships(child_customer_id);

-- Ticket assignments table
CREATE TABLE IF NOT EXISTS ticket_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    complaint_id UUID NOT NULL REFERENCES complaints(id) ON DELETE CASCADE,
    assigned_to VARCHAR(255) NOT NULL,
    assigned_by VARCHAR(255),
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    unassigned_at TIMESTAMPTZ,
    assignment_reason TEXT
);

CREATE INDEX idx_ticket_assignments_complaint ON ticket_assignments(complaint_id);

COMMIT;
