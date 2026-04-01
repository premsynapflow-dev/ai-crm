"""Add multi-level escalation system.

Revision ID: 20260401_02
Revises: 20260401_01
Create Date: 2026-04-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import uuid


# revision identifiers, used by Alembic
revision = "20260401_02"
down_revision = "20260401_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import text
    
    connection = op.get_bind()
    
    # 1. Create escalation_level_definitions table if not exists
    try:
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS escalation_level_definitions (
                id UUID NOT NULL PRIMARY KEY,
                client_id UUID NOT NULL,
                level_code VARCHAR(20) NOT NULL,
                level_number INTEGER NOT NULL,
                trigger_after_hours INTEGER NOT NULL,
                escalate_to_role VARCHAR(255) NOT NULL,
                description VARCHAR(500),
                is_active BOOLEAN NOT NULL DEFAULT true,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                CONSTRAINT fk_escalation_levels_client FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
                CONSTRAINT unique_client_level_code UNIQUE (client_id, level_code)
            )
        """))
        connection.execute(text("CREATE INDEX IF NOT EXISTS idx_escalation_levels_client ON escalation_level_definitions(client_id)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS idx_escalation_levels_client_number ON escalation_level_definitions(client_id, level_number)"))
    except Exception as e:
        print(f"Warning: Error creating escalation_level_definitions: {e}")
    
    # 2. Add columns to escalation_rules (if not already present)
    try:
        connection.execute(text("ALTER TABLE escalation_rules ADD COLUMN IF NOT EXISTS category_code VARCHAR(20)"))
    except Exception:
        pass
        
    try:
        connection.execute(text("ALTER TABLE escalation_rules ADD COLUMN IF NOT EXISTS escalation_level_id UUID"))
    except Exception:
        pass
        
    try:
        connection.execute(text("ALTER TABLE escalation_rules ADD COLUMN IF NOT EXISTS trigger_after_hours INTEGER"))
    except Exception:
        pass
    
    # Add FK and index if they don't exist
    try:
        connection.execute(text("""
            ALTER TABLE escalation_rules 
            ADD CONSTRAINT fk_escalation_rules_escalation_level 
            FOREIGN KEY (escalation_level_id) REFERENCES escalation_level_definitions(id) ON DELETE SET NULL
        """))
    except Exception:
        pass
    
    try:
        connection.execute(text("CREATE INDEX IF NOT EXISTS idx_escalation_rules_category ON escalation_rules(category_code)"))
    except Exception:
        pass

    # 3. Add columns to escalations (if not already present)
    try:
        connection.execute(text("ALTER TABLE escalations ADD COLUMN IF NOT EXISTS escalation_level_id UUID"))
    except Exception:
        pass
        
    try:
        connection.execute(text("ALTER TABLE escalations ADD COLUMN IF NOT EXISTS metadata_json JSON DEFAULT '{}'::json"))
    except Exception:
        pass
        
    try:
        connection.execute(text("ALTER TABLE escalations ADD COLUMN IF NOT EXISTS next_escalation_at TIMESTAMP WITH TIME ZONE"))
    except Exception:
        pass
    
    # Add FK and index to escalations
    try:
        connection.execute(text("""
            ALTER TABLE escalations 
            ADD CONSTRAINT fk_escalations_escalation_level 
            FOREIGN KEY (escalation_level_id) REFERENCES escalation_level_definitions(id) ON DELETE SET NULL
        """))
    except Exception:
        pass
    
    try:
        connection.execute(text("CREATE INDEX IF NOT EXISTS idx_escalations_next_escalation ON escalations(next_escalation_at)"))
    except Exception:
        pass

    # 4. Add columns to conversations (if not already present)
    try:
        connection.execute(text("ALTER TABLE conversations ADD COLUMN IF NOT EXISTS escalation_level INTEGER DEFAULT 0"))
    except Exception:
        pass
        
    try:
        connection.execute(text("ALTER TABLE conversations ADD COLUMN IF NOT EXISTS last_escalated_at TIMESTAMP WITH TIME ZONE"))
    except Exception:
        pass
        
    try:
        connection.execute(text("ALTER TABLE conversations ADD COLUMN IF NOT EXISTS escalation_metadata_json JSON DEFAULT '{}'::json"))
    except Exception:
        pass
    
    try:
        connection.execute(text("CREATE INDEX IF NOT EXISTS idx_conversations_escalation_level ON conversations(client_id, escalation_level)"))
    except Exception:
        pass
    
    connection.commit()


def downgrade() -> None:
    # Reverse order of operations
    op.drop_index("idx_conversations_escalation_level", table_name="conversations")
    op.drop_column("conversations", "escalation_metadata_json")
    op.drop_column("conversations", "last_escalated_at")
    op.drop_column("conversations", "escalation_level")

    op.drop_index("idx_escalations_next_escalation", table_name="escalations")
    op.drop_constraint("fk_escalations_escalation_level", "escalations", type_="foreignkey")
    op.drop_column("escalations", "next_escalation_at")
    op.drop_column("escalations", "metadata_json")
    op.drop_column("escalations", "escalation_level_id")

    op.drop_constraint("fk_escalation_rules_escalation_level", "escalation_rules", type_="foreignkey")
    op.drop_index("idx_escalation_rules_category", table_name="escalation_rules")
    op.drop_column("escalation_rules", "trigger_after_hours")
    op.drop_column("escalation_rules", "escalation_level_id")
    op.drop_column("escalation_rules", "category_code")

    op.drop_table("escalation_level_definitions")
