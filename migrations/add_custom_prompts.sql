-- Add custom AI prompt fields to clients table
-- Run this in Supabase SQL editor

ALTER TABLE clients 
ADD COLUMN IF NOT EXISTS custom_prompt_enabled BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS custom_prompt_config JSONB DEFAULT NULL,
ADD COLUMN IF NOT EXISTS custom_prompt_updated_at TIMESTAMPTZ DEFAULT NULL;

-- Add index for quick lookups
CREATE INDEX IF NOT EXISTS idx_clients_custom_prompt 
ON clients(custom_prompt_enabled) 
WHERE custom_prompt_enabled = TRUE;

-- Add comment
COMMENT ON COLUMN clients.custom_prompt_config IS 'Template-based prompt customization: tone, focus_areas, classification_rules, reply_guidelines';
