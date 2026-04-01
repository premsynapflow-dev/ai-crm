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
    # Create rbi_tat_rules table
    op.create_table(
        "rbi_tat_rules",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column("client_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("category_code", sa.String(20), nullable=False),
        sa.Column("tat_days", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_id", "category_code", name="unique_client_tat_rule"),
        sa.Index("idx_tat_rules_client", "client_id"),
        sa.Index("idx_tat_rules_category", "category_code"),
        sa.Index("idx_tat_rules_lookup", "client_id", "category_code", "is_active"),
    )


def downgrade() -> None:
    op.drop_table("rbi_tat_rules")
