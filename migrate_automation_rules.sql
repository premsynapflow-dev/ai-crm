CREATE TABLE automation_rules (

id UUID PRIMARY KEY,

client_id UUID REFERENCES clients(id),

trigger_type VARCHAR(50),

trigger_value VARCHAR(100),

action_type VARCHAR(50),

action_config JSONB,

enabled BOOLEAN DEFAULT TRUE,

created_at TIMESTAMP DEFAULT now()
);
