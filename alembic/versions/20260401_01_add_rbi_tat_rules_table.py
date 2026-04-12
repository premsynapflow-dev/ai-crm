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
    # Create rbi_tat_rules table using alembic operations (idempotent)
    from sqlalchemy import text
    
    # Check if table already exists
    connection = op.get_bind()
    result = connection.execute(text("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'rbi_tat_rules')"))
    table_exists = result.fetchone()[0]
    
    if not table_exists:
        # Create table using alembic operations
        try:
            op.create_table(
                "rbi_tat_rules",
                sa.Column("id", sa.UUID(), nullable=False),
                sa.Column("client_id", sa.UUID(), nullable=False),
                sa.Column("category_code", sa.String(length=20), nullable=False),
                sa.Column("tat_days", sa.Integer(), nullable=False),
                sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
                sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
                sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
                sa.PrimaryKeyConstraint("id"),
                sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
                sa.UniqueConstraint("client_id", "category_code", name="unique_client_tat_rule"),
            )
        except Exception:
            # Table may already exist, skip silently
            pass
        
        # Create indexes
        op.create_index("idx_tat_rules_client", "rbi_tat_rules", ["client_id"])
        op.create_index("idx_tat_rules_category", "rbi_tat_rules", ["category_code"])
        op.create_index("idx_tat_rules_lookup", "rbi_tat_rules", ["client_id", "category_code", "is_active"])
    else:
        # Table exists, ensure indexes exist (idempotent)
        try:
            op.create_index("idx_tat_rules_client", "rbi_tat_rules", ["client_id"], unique=False)
        except:
            pass  # Index may already exist
        try:
            op.create_index("idx_tat_rules_category", "rbi_tat_rules", ["category_code"], unique=False)
        except:
            pass  # Index may already exist
        try:
            op.create_index("idx_tat_rules_lookup", "rbi_tat_rules", ["client_id", "category_code", "is_active"], unique=False)
        except:
            pass  # Index may already exist


def downgrade() -> None:
    op.drop_table("rbi_tat_rules")
