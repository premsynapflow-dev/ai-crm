"""repair ticketing system v2

Revision ID: 20260329_02
Revises: 20260329_01
Create Date: 2026-03-29
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260329_02"
down_revision = "20260329_01"
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

    if "complaints" in tables:
        complaint_indexes = _index_names(inspector, "complaints")
        if "uq_complaints_ticket_number" not in complaint_indexes:
            op.create_index(
                "uq_complaints_ticket_number",
                "complaints",
                ["ticket_number"],
                unique=True,
                postgresql_where=sa.text("ticket_number IS NOT NULL"),
            )
        if "idx_complaints_state" not in complaint_indexes:
            op.create_index("idx_complaints_state", "complaints", ["client_id", "state", "created_at"])
        if "idx_complaints_sla_due" not in complaint_indexes:
            op.create_index(
                "idx_complaints_sla_due",
                "complaints",
                ["sla_due_at"],
                postgresql_where=sa.text("sla_due_at IS NOT NULL AND resolved_at IS NULL"),
            )

    for table_name in ["sla_policies", "business_hours", "ticket_state_transitions", "escalation_rules", "ticket_comments", "ticket_assignments"]:
        if table_name not in tables:
            continue
        op.alter_column(table_name, "id", server_default=sa.text("gen_random_uuid()"))

    if "ticket_state_transitions" in tables:
        columns = _column_names(inspector, "ticket_state_transitions")
        if "metadata_json" in columns and "metadata" not in columns:
            op.alter_column("ticket_state_transitions", "metadata_json", new_column_name="metadata")
        elif "metadata" not in columns:
            op.add_column(
                "ticket_state_transitions",
                sa.Column(
                    "metadata",
                    postgresql.JSONB(astext_type=sa.Text()),
                    nullable=False,
                    server_default=sa.text("'{}'::jsonb"),
                ),
            )

        transition_indexes = _index_names(inspector, "ticket_state_transitions")
        if "idx_transitions_complaint" not in transition_indexes:
            op.create_index("idx_transitions_complaint", "ticket_state_transitions", ["complaint_id", "created_at"])
        if "idx_transitions_created" not in transition_indexes:
            op.create_index("idx_transitions_created", "ticket_state_transitions", ["created_at"])

    if "ticket_comments" in tables:
        columns = _column_names(inspector, "ticket_comments")
        if "metadata_json" in columns and "metadata" not in columns:
            op.alter_column("ticket_comments", "metadata_json", new_column_name="metadata")
        elif "metadata" not in columns:
            op.add_column(
                "ticket_comments",
                sa.Column(
                    "metadata",
                    postgresql.JSONB(astext_type=sa.Text()),
                    nullable=False,
                    server_default=sa.text("'{}'::jsonb"),
                ),
            )

        comment_indexes = _index_names(inspector, "ticket_comments")
        if "idx_comments_complaint" not in comment_indexes:
            op.create_index("idx_comments_complaint", "ticket_comments", ["complaint_id", "created_at"])

    if "ticket_assignments" in tables:
        assignment_indexes = _index_names(inspector, "ticket_assignments")
        if "idx_assignments_complaint" not in assignment_indexes:
            op.create_index("idx_assignments_complaint", "ticket_assignments", ["complaint_id"])
        if "idx_assignments_agent" not in assignment_indexes:
            op.create_index(
                "idx_assignments_agent",
                "ticket_assignments",
                ["assigned_to"],
                postgresql_where=sa.text("unassigned_at IS NULL"),
            )

    if "sla_policies" in tables:
        policy_indexes = _index_names(inspector, "sla_policies")
        if "idx_sla_policies_client" not in policy_indexes:
            op.create_index(
                "idx_sla_policies_client",
                "sla_policies",
                ["client_id"],
                postgresql_where=sa.text("enabled = true"),
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "ticket_state_transitions" in tables:
        columns = _column_names(inspector, "ticket_state_transitions")
        if "metadata" in columns and "metadata_json" not in columns:
            op.alter_column("ticket_state_transitions", "metadata", new_column_name="metadata_json")

    if "ticket_comments" in tables:
        columns = _column_names(inspector, "ticket_comments")
        if "metadata" in columns and "metadata_json" not in columns:
            op.alter_column("ticket_comments", "metadata", new_column_name="metadata_json")
