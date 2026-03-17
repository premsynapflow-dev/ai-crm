-- Performance indexes for AI Complaint Engine
-- Run this in Supabase SQL editor

-- Critical for webhook processing
CREATE INDEX IF NOT EXISTS idx_complaints_client_status 
ON complaints(client_id, status);

CREATE INDEX IF NOT EXISTS idx_complaints_client_created 
ON complaints(client_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_complaints_customer_email 
ON complaints(customer_email) 
WHERE customer_email IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_complaints_customer_phone 
ON complaints(customer_phone) 
WHERE customer_phone IS NOT NULL;

-- For usage tracking and billing
CREATE INDEX IF NOT EXISTS idx_usage_records_client_period 
ON usage_records(client_id, period_start, period_end);

-- For job queue processing
CREATE INDEX IF NOT EXISTS idx_job_queue_processing 
ON job_queue(status, scheduled_for) 
WHERE status IN ('queued', 'processing');

CREATE INDEX IF NOT EXISTS idx_job_queue_retry 
ON job_queue(status, retry_count) 
WHERE status = 'failed';

-- For analytics queries
CREATE INDEX IF NOT EXISTS idx_complaints_analytics 
ON complaints(client_id, category, created_at);

CREATE INDEX IF NOT EXISTS idx_complaints_sentiment 
ON complaints(client_id, sentiment, created_at);

CREATE INDEX IF NOT EXISTS idx_complaints_resolution 
ON complaints(client_id, resolution_status, created_at);

-- For audit log cleanup
CREATE INDEX IF NOT EXISTS idx_request_audits_created 
ON request_audits(created_at);

-- For automation rules
CREATE INDEX IF NOT EXISTS idx_automation_rules_client 
ON automation_rules(client_id, enabled);

-- For reply cache
CREATE INDEX IF NOT EXISTS idx_reply_cache_key 
ON reply_cache(cache_key);

-- Composite index for common queries
CREATE INDEX IF NOT EXISTS idx_complaints_ticket_thread 
ON complaints(ticket_id, thread_id);

-- For monitoring metrics
CREATE INDEX IF NOT EXISTS idx_monitoring_metrics_name_created 
ON monitoring_metrics(metric_name, created_at DESC);

-- Add note about index creation
COMMENT ON INDEX idx_complaints_client_status IS 'Speeds up client dashboard queries';
COMMENT ON INDEX idx_job_queue_processing IS 'Critical for worker performance';
