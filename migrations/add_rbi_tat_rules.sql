-- RBI TAT Rules Table
-- Allows per-client, per-category TAT configuration
-- Replaces hardcoded 30-day defaults with database-driven rules

CREATE TABLE IF NOT EXISTS rbi_tat_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL,
    category_code VARCHAR(20) NOT NULL,
    tat_days INTEGER NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
    UNIQUE (client_id, category_code),
    
    CHECK (tat_days > 0 AND tat_days <= 365)
);

-- Indexes for efficient lookups
CREATE INDEX idx_tat_rules_client ON rbi_tat_rules(client_id);
CREATE INDEX idx_tat_rules_category ON rbi_tat_rules(category_code);
CREATE INDEX idx_tat_rules_lookup ON rbi_tat_rules(client_id, category_code, is_active);

-- Comments
COMMENT ON TABLE rbi_tat_rules IS 'Configurable TAT (Turn-Around Time) rules per client and RBI category';
COMMENT ON COLUMN rbi_tat_rules.client_id IS 'Client for whom this TAT rule applies';
COMMENT ON COLUMN rbi_tat_rules.category_code IS 'RBI complaint category code (e.g., ATM, CC, LOAN)';
COMMENT ON COLUMN rbi_tat_rules.tat_days IS 'Number of days for TAT compliance';
COMMENT ON COLUMN rbi_tat_rules.is_active IS 'Whether this rule is currently active';
