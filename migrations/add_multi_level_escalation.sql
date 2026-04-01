-- Multi-Level Escalation System
-- Adds support for tiered escalation (L1 → L2 → IO)
-- Non-breaking additions to existing schema

-- 1. Escalation Level Definitions
-- Defines escalation levels (L1, L2, Internal Ombudsman)
-- per client with trigger thresholds
CREATE TABLE IF NOT EXISTS escalation_level_definitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL,
    level_code VARCHAR(20) NOT NULL,  -- L1, L2, IO
    level_number INTEGER NOT NULL,    -- 1, 2, 3
    trigger_after_hours INTEGER NOT NULL,  -- hours before escalating
    escalate_to_role VARCHAR(255) NOT NULL,  -- email, team, role
    description VARCHAR(500),
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
    UNIQUE (client_id, level_code),
    CHECK (level_number > 0 AND trigger_after_hours > 0)
);

CREATE INDEX idx_escalation_levels_client ON escalation_level_definitions(client_id);
CREATE INDEX idx_escalation_levels_client_number ON escalation_level_definitions(client_id, level_number);

-- 2. Extend escalation_rules table
-- Add category-based filtering and escalation level links
ALTER TABLE escalation_rules ADD COLUMN IF NOT EXISTS category_code VARCHAR(20);
ALTER TABLE escalation_rules ADD COLUMN IF NOT EXISTS escalation_level_id UUID;
ALTER TABLE escalation_rules ADD COLUMN IF NOT EXISTS trigger_after_hours INTEGER;

ALTER TABLE escalation_rules ADD CONSTRAINT fk_escalation_rules_escalation_level
    FOREIGN KEY (escalation_level_id) REFERENCES escalation_level_definitions(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_escalation_rules_category ON escalation_rules(category_code);

-- 3. Extend escalations table
-- Add metadata, escalation level tracking, and next escalation planning
ALTER TABLE escalations ADD COLUMN IF NOT EXISTS escalation_level_id UUID;
ALTER TABLE escalations ADD COLUMN IF NOT EXISTS metadata_json JSON DEFAULT '{}';
ALTER TABLE escalations ADD COLUMN IF NOT EXISTS next_escalation_at TIMESTAMP WITH TIME ZONE;

ALTER TABLE escalations ADD CONSTRAINT fk_escalations_escalation_level
    FOREIGN KEY (escalation_level_id) REFERENCES escalation_level_definitions(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_escalations_next_escalation ON escalations(next_escalation_at);

-- 4. Extend conversations table
-- Track escalation state at conversation level
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS escalation_level INTEGER NOT NULL DEFAULT 0;
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS last_escalated_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS escalation_metadata_json JSON DEFAULT '{}';

CREATE INDEX IF NOT EXISTS idx_conversations_escalation_level ON conversations(client_id, escalation_level);

-- COMMENTS FOR DOCUMENTATION
COMMENT ON TABLE escalation_level_definitions IS 'Defines multi-level escalation rules per client (L1 → L2 → IO)';
COMMENT ON COLUMN escalation_level_definitions.level_code IS 'Level identifier: L1 (Regional Manager), L2 (Ombudsman Staff), IO (Internal Ombudsman)';
COMMENT ON COLUMN escalation_level_definitions.trigger_after_hours IS 'Hours of open/pending status before auto-escalating to this level';
COMMENT ON COLUMN escalation_level_definitions.escalate_to_role IS 'Email pattern or role name for routing (group-email@bank.com)';

COMMENT ON TABLE escalations IS 'Audit trail for all escalations on tickets';
COMMENT ON COLUMN escalations.escalation_level_id IS 'Reference to escalation level that triggered this escalation';
COMMENT ON COLUMN escalations.next_escalation_at IS 'Scheduled time for next escalation (for non-breached situations)';
COMMENT ON COLUMN escalations.metadata_json IS 'Context data: previous_level, reason, triggered_by, metrics';

COMMENT ON TABLE conversations IS 'Enhanced to track escalation state';
COMMENT ON COLUMN conversations.escalation_level IS 'Current escalation level (0=not escalated, 1=L1, 2=L2, 3=IO)';
COMMENT ON COLUMN conversations.last_escalated_at IS 'Timestamp of last escalation to prevent duplicates';
COMMENT ON COLUMN conversations.escalation_metadata_json IS 'Context data: breach_reason, sla_hours_remaining, tat_status';
