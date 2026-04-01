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
    # 1. Create escalation_level_definitions table
    op.create_table(
        "escalation_level_definitions",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column("client_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("level_code", sa.String(20), nullable=False),  # L1, L2, IO
        sa.Column("level_number", sa.Integer(), nullable=False),  # 1, 2, 3
        sa.Column("trigger_after_hours", sa.Integer(), nullable=False),  # hours
        sa.Column("escalate_to_role", sa.String(255), nullable=False),  # team or email pattern
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_id", "level_code", name="unique_client_level_code"),
        sa.Index("idx_escalation_levels_client", "client_id"),
        sa.Index("idx_escalation_levels_client_number", "client_id", "level_number"),
    )

    # 2. Extend escalation_rules (if not already exists) to support category-based rules
    # First check if escalation_rules has category_code - if not, add it
    op.add_column(
        "escalation_rules",
        sa.Column("category_code", sa.String(20), nullable=True),
    )
    op.add_column(
        "escalation_rules",
        sa.Column("escalation_level_id", sa.Uuid(as_uuid=True), nullable=True),
    )
    op.add_column(
        "escalation_rules",
        sa.Column("trigger_after_hours", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_escalation_rules_escalation_level",
        "escalation_rules",
        "escalation_level_definitions",
        ["escalation_level_id"],
        ["id"],
    )
    op.create_index(
        "idx_escalation_rules_category",
        "escalation_rules",
        ["category_code"],
    )

    # 3. Extend escalations table with metadata
    op.add_column(
        "escalations",
        sa.Column("escalation_level_id", sa.Uuid(as_uuid=True), nullable=True),
    )
    op.add_column(
        "escalations",
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.add_column(
        "escalations",
        sa.Column("next_escalation_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_escalations_escalation_level",
        "escalations",
        "escalation_level_definitions",
        ["escalation_level_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "idx_escalations_next_escalation",
        "escalations",
        ["next_escalation_at"],
    )

    # 4. Extend conversations table with escalation tracking
    op.add_column(
        "conversations",
        sa.Column("escalation_level", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "conversations",
        sa.Column("last_escalated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "conversations",
        sa.Column("escalation_metadata_json", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.create_index(
        "idx_conversations_escalation_level",
        "conversations",
        ["client_id", "escalation_level"],
    )


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
