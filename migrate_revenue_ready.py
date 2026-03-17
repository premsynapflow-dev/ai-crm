"""
Consolidated schema migration for the revenue-ready upgrade.
Run once after pulling the latest code:
    python migrate_revenue_ready.py
"""
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

database_url = os.getenv("DATABASE_URL", "").strip()
if not database_url:
    raise RuntimeError("DATABASE_URL is required")

engine = create_engine(database_url, connect_args={"sslmode": "require"})

statements = [
    "ALTER TABLE clients ADD COLUMN IF NOT EXISTS plan_id VARCHAR(50) DEFAULT 'trial';",
    "ALTER TABLE clients ADD COLUMN IF NOT EXISTS monthly_ticket_limit INTEGER DEFAULT 50;",
    "ALTER TABLE clients ADD COLUMN IF NOT EXISTS trial_ends_at TIMESTAMP WITH TIME ZONE;",
    "ALTER TABLE clients ADD COLUMN IF NOT EXISTS slack_webhook_url VARCHAR(500);",
    "ALTER TABLE complaints ADD COLUMN IF NOT EXISTS assigned_team VARCHAR(50);",
    "ALTER TABLE complaints ADD COLUMN IF NOT EXISTS response_time_seconds INTEGER;",
    "ALTER TABLE complaints ADD COLUMN IF NOT EXISTS first_response_at TIMESTAMP WITH TIME ZONE;",
    "ALTER TABLE complaints ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMP WITH TIME ZONE;",
    "ALTER TABLE complaints ADD COLUMN IF NOT EXISTS customer_satisfaction_score DOUBLE PRECISION;",
    "CREATE TABLE IF NOT EXISTS subscriptions (id UUID PRIMARY KEY, client_id UUID NOT NULL REFERENCES clients(id), plan VARCHAR(50) NOT NULL, status VARCHAR(50) NOT NULL DEFAULT 'trialing', stripe_subscription_id VARCHAR(255), razorpay_subscription_id VARCHAR(255), current_period_start TIMESTAMP WITH TIME ZONE, current_period_end TIMESTAMP WITH TIME ZONE, created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), updated_at TIMESTAMP WITH TIME ZONE DEFAULT now());",
    "CREATE TABLE IF NOT EXISTS invoices (id UUID PRIMARY KEY, client_id UUID NOT NULL REFERENCES clients(id), invoice_number VARCHAR(100) NOT NULL UNIQUE, status VARCHAR(50) NOT NULL DEFAULT 'pending', subtotal INTEGER NOT NULL DEFAULT 0, tax INTEGER NOT NULL DEFAULT 0, total INTEGER NOT NULL DEFAULT 0, payment_method VARCHAR(50), payment_id VARCHAR(255), invoice_date TIMESTAMP WITH TIME ZONE DEFAULT now(), due_date TIMESTAMP WITH TIME ZONE, paid_at TIMESTAMP WITH TIME ZONE, created_at TIMESTAMP WITH TIME ZONE DEFAULT now());",
    "CREATE TABLE IF NOT EXISTS usage_records (id UUID PRIMARY KEY, client_id UUID NOT NULL REFERENCES clients(id), tickets_processed INTEGER NOT NULL DEFAULT 0, period_start TIMESTAMP WITH TIME ZONE NOT NULL, period_end TIMESTAMP WITH TIME ZONE NOT NULL, included_in_plan INTEGER NOT NULL DEFAULT 0, overage INTEGER NOT NULL DEFAULT 0, overage_cost INTEGER NOT NULL DEFAULT 0, created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), updated_at TIMESTAMP WITH TIME ZONE DEFAULT now());",
    "CREATE TABLE IF NOT EXISTS request_audits (id UUID PRIMARY KEY, client_id UUID, request_id VARCHAR(100) NOT NULL, path VARCHAR(255) NOT NULL, method VARCHAR(20) NOT NULL, ip_address VARCHAR(100) NOT NULL, user_agent VARCHAR(500), status_code INTEGER, created_at TIMESTAMP WITH TIME ZONE DEFAULT now());",
    "CREATE TABLE IF NOT EXISTS materialized_analytics (id UUID PRIMARY KEY, client_id UUID NOT NULL, metric_key VARCHAR(100) NOT NULL, metric_value JSON NOT NULL, period_start TIMESTAMP WITH TIME ZONE, period_end TIMESTAMP WITH TIME ZONE, generated_at TIMESTAMP WITH TIME ZONE DEFAULT now());",
    "CREATE TABLE IF NOT EXISTS job_queue (id UUID PRIMARY KEY, job_type VARCHAR(100) NOT NULL, payload JSON NOT NULL, status VARCHAR(50) NOT NULL DEFAULT 'queued', retry_count INTEGER NOT NULL DEFAULT 0, last_error TEXT, created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), scheduled_for TIMESTAMP WITH TIME ZONE, processed_at TIMESTAMP WITH TIME ZONE);",
    "CREATE TABLE IF NOT EXISTS reply_cache (id UUID PRIMARY KEY, cache_key VARCHAR(255) NOT NULL UNIQUE, prompt TEXT NOT NULL, response TEXT NOT NULL, hit_count INTEGER NOT NULL DEFAULT 0, created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), updated_at TIMESTAMP WITH TIME ZONE DEFAULT now());",
    "CREATE TABLE IF NOT EXISTS monitoring_metrics (id UUID PRIMARY KEY, metric_name VARCHAR(100) NOT NULL, metric_value DOUBLE PRECISION NOT NULL DEFAULT 0, dimensions JSON, created_at TIMESTAMP WITH TIME ZONE DEFAULT now());",
    "CREATE TABLE IF NOT EXISTS waitlist_entries (id UUID PRIMARY KEY, email VARCHAR(255) NOT NULL UNIQUE, metadata JSON, created_at TIMESTAMP WITH TIME ZONE DEFAULT now());",
    "CREATE TABLE IF NOT EXISTS demo_requests (id UUID PRIMARY KEY, email VARCHAR(255) NOT NULL, name VARCHAR(255), company VARCHAR(255), metadata JSON, created_at TIMESTAMP WITH TIME ZONE DEFAULT now());",
]

with engine.begin() as conn:
    for statement in statements:
        conn.execute(text(statement))
    conn.execute(text("ALTER TABLE complaints ALTER COLUMN response_time_seconds TYPE INTEGER USING response_time_seconds::integer;"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_complaints_response_time ON complaints (response_time_seconds);"))

print("Migration complete: revenue-ready schema ensured.")
