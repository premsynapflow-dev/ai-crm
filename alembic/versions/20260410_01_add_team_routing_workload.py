"""add team routing and workload balancing

Revision ID: 20260410_01
Revises: 20260408_01
Create Date: 2026-04-10
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260410_01"
down_revision = "20260408_01"
branch_labels = None
depends_on = None


def _column_names(inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "teams" not in tables:
        op.create_table(
            "teams",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("client_id", "name", name="uq_teams_client_name"),
        )
        op.create_index("idx_teams_client_name", "teams", ["client_id", "name"])

    if "team_members" not in tables:
        op.create_table(
            "team_members",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
            sa.Column("team_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("client_users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("role", sa.String(length=20), nullable=False, server_default="agent"),
            sa.Column("capacity", sa.Integer(), nullable=False, server_default="10"),
            sa.Column("active_tasks", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.CheckConstraint("capacity >= 0", name="ck_team_members_capacity_non_negative"),
            sa.CheckConstraint("active_tasks >= 0", name="ck_team_members_active_tasks_non_negative"),
            sa.CheckConstraint("role IN ('agent', 'manager')", name="ck_team_members_role"),
            sa.UniqueConstraint("client_id", "team_id", "user_id", name="uq_team_members_client_team_user"),
        )
        op.create_index("idx_team_members_lookup", "team_members", ["client_id", "team_id", "role", "is_active"])
        op.create_index(
            "idx_team_members_capacity",
            "team_members",
            ["team_id", "is_active", "role", "active_tasks", "updated_at"],
        )

    if "routing_rules" not in tables:
        op.create_table(
            "routing_rules",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
            sa.Column("category", sa.String(length=100), nullable=False),
            sa.Column("team_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("client_id", "category", name="uq_routing_rules_client_category"),
        )
        op.create_index("idx_routing_rules_client_category", "routing_rules", ["client_id", "category"])

    if "complaints" in tables:
        complaint_columns = _column_names(inspector, "complaints")
        complaint_indexes = _index_names(inspector, "complaints")

        if "team_id" not in complaint_columns:
            op.add_column("complaints", sa.Column("team_id", postgresql.UUID(as_uuid=True), nullable=True))
            op.create_foreign_key(
                "fk_complaints_team_id",
                "complaints",
                "teams",
                ["team_id"],
                ["id"],
                ondelete="SET NULL",
            )
        if "assigned_user_id" not in complaint_columns:
            op.add_column("complaints", sa.Column("assigned_user_id", postgresql.UUID(as_uuid=True), nullable=True))
            op.create_foreign_key(
                "fk_complaints_assigned_user_id",
                "complaints",
                "client_users",
                ["assigned_user_id"],
                ["id"],
                ondelete="SET NULL",
            )

        if "idx_complaints_team" not in complaint_indexes:
            op.create_index("idx_complaints_team", "complaints", ["client_id", "team_id"])
        if "idx_complaints_assigned_user" not in complaint_indexes:
            op.create_index("idx_complaints_assigned_user", "complaints", ["client_id", "assigned_user_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "complaints" in tables:
        complaint_columns = _column_names(inspector, "complaints")
        complaint_indexes = _index_names(inspector, "complaints")

        if "idx_complaints_assigned_user" in complaint_indexes:
            op.drop_index("idx_complaints_assigned_user", table_name="complaints")
        if "idx_complaints_team" in complaint_indexes:
            op.drop_index("idx_complaints_team", table_name="complaints")

        foreign_keys = {fk["name"] for fk in inspector.get_foreign_keys("complaints")}
        if "fk_complaints_assigned_user_id" in foreign_keys:
            op.drop_constraint("fk_complaints_assigned_user_id", "complaints", type_="foreignkey")
        if "fk_complaints_team_id" in foreign_keys:
            op.drop_constraint("fk_complaints_team_id", "complaints", type_="foreignkey")

        if "assigned_user_id" in complaint_columns:
            op.drop_column("complaints", "assigned_user_id")
        if "team_id" in complaint_columns:
            op.drop_column("complaints", "team_id")

    if "routing_rules" in tables:
        op.drop_table("routing_rules")
    if "team_members" in tables:
        op.drop_table("team_members")
    if "teams" in tables:
        op.drop_table("teams")
