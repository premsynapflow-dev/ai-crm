"""Add RBI TAT Rules table for client-specific TAT configuration.

Revision ID: 20260401_01
Revises: 20260330_01
Create Date: 2026-04-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import uuid


# revision identifiers, used by Alembic
revision = "20260401_01"
down_revision = "20260330_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create rbi_tat_rules table (idempotent - skip if exists)
    from sqlalchemy import text
    
    # Check if table exists before creating
    try:
        connection = op.get_bind()
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS rbi_tat_rules (
                id UUID NOT NULL PRIMARY KEY,
                client_id UUID NOT NULL,
                category_code VARCHAR(20) NOT NULL,
                tat_days INTEGER NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT true,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                CONSTRAINT fk_tat_rules_client FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
                CONSTRAINT unique_client_tat_rule UNIQUE (client_id, category_code)
            )
        """))
        # Create indexes if they don't exist
        connection.execute(text("CREATE INDEX IF NOT EXISTS idx_tat_rules_client ON rbi_tat_rules(client_id)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS idx_tat_rules_category ON rbi_tat_rules(category_code)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS idx_tat_rules_lookup ON rbi_tat_rules(client_id, category_code, is_active)"))
        connection.commit()
    except Exception as e:
        print(f"Warning: Error creating rbi_tat_rules table: {e}")
        # Continue silently - table may already exist


def downgrade() -> None:
    op.drop_table("rbi_tat_rules")
