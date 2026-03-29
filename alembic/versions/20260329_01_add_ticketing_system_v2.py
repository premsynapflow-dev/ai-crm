"""add ticketing system v2

Revision ID: 20260329_01
Revises: 20260322_01
Create Date: 2026-03-29
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260329_01"
down_revision = "20260322_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "complaints" in tables:
        complaint_columns = {column["name"] for column in inspector.get_columns("complaints")}
        if "state" not in complaint_columns:
            op.add_column("complaints", sa.Column("state", sa.String(length=50), nullable=False, server_default="new"))
        if "state_changed_at" not in complaint_columns:
            op.add_column("complaints", sa.Column("state_changed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
        if "ticket_number" not in complaint_columns:
            op.add_column("complaints", sa.Column("ticket_number", sa.String(length=50), nullable=True, unique=True))
        if "reopened_count" not in complaint_columns:
            op.add_column("complaints", sa.Column("reopened_count", sa.Integer(), nullable=False, server_default="0"))
        if "last_reopened_at" not in complaint_columns:
            op.add_column("complaints", sa.Column("last_reopened_at", sa.DateTime(timezone=True), nullable=True))
        if "sla_due_at" not in complaint_columns:
            op.add_column("complaints", sa.Column("sla_due_at", sa.DateTime(timezone=True), nullable=True))
        if "sla_status" not in complaint_columns:
            op.add_column("complaints", sa.Column("sla_status", sa.String(length=20), nullable=False, server_default="on_track"))
        if "escalation_level" not in complaint_columns:
            op.add_column("complaints", sa.Column("escalation_level", sa.Integer(), nullable=False, server_default="0"))
        if "escalated_at" not in complaint_columns:
            op.add_column("complaints", sa.Column("escalated_at", sa.DateTime(timezone=True), nullable=True))
        if "escalated_to" not in complaint_columns:
            op.add_column("complaints", sa.Column("escalated_to", sa.String(length=255), nullable=True))

        complaint_indexes = {index["name"] for index in inspector.get_indexes("complaints")}
        if "uq_complaints_ticket_number" not in complaint_indexes:
            op.create_index(
                "uq_complaints_ticket_number",
                "complaints",
                ["ticket_number"],
                unique=True,
                postgresql_where=sa.text("ticket_number IS NOT NULL"),
            )
        if "idx_complaints_state" not in complaint_indexes:
            op.create_index(
                "idx_complaints_state",
                "complaints",
                ["client_id", "state", "created_at"],
                unique=False,
            )
        if "idx_complaints_sla_due" not in complaint_indexes:
            op.create_index(
                "idx_complaints_sla_due",
                "complaints",
                ["sla_due_at"],
                unique=False,
                postgresql_where=sa.text("sla_due_at IS NOT NULL AND resolved_at IS NULL"),
            )

        op.execute(
            """
            UPDATE complaints
            SET state = CASE
                WHEN resolution_status = 'resolved' OR resolved_at IS NOT NULL THEN 'resolved'
                WHEN status IN ('ESCALATE_HIGH', 'PROCESSING', 'PROCESSED', 'IN_PROGRESS', 'REPLIED', 'SENT') THEN 'in_progress'
                WHEN assigned_to IS NOT NULL OR assigned_team IS NOT NULL THEN 'assigned'
                ELSE COALESCE(state, 'new')
            END,
            state_changed_at = COALESCE(state_changed_at, NOW())
            """
        )

    if "sla_policies" not in tables:
        op.create_table(
            "sla_policies",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("priority_level", sa.String(length=20), nullable=False),
            sa.Column("first_response_minutes", sa.Integer(), nullable=False),
            sa.Column("resolution_minutes", sa.Integer(), nullable=False),
            sa.Column("escalation_threshold_minutes", sa.Integer(), nullable=True),
            sa.Column("business_hours_only", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("timezone", sa.String(length=50), nullable=False, server_default="UTC"),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("client_id", "priority_level", name="unique_client_priority"),
        )
        op.create_index(
            "idx_sla_policies_client",
            "sla_policies",
            ["client_id"],
            postgresql_where=sa.text("enabled = true"),
        )

    if "business_hours" not in tables:
        op.create_table(
            "business_hours",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
            sa.Column("day_of_week", sa.Integer(), nullable=False),
            sa.Column("start_time", sa.Time(), nullable=False),
            sa.Column("end_time", sa.Time(), nullable=False),
            sa.Column("timezone", sa.String(length=50), nullable=False, server_default="UTC"),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.CheckConstraint("day_of_week BETWEEN 0 AND 6", name="ck_business_hours_day_of_week"),
            sa.UniqueConstraint("client_id", "day_of_week", name="unique_client_day"),
        )

    if "ticket_state_transitions" not in tables:
        op.create_table(
            "ticket_state_transitions",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("complaint_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False),
            sa.Column("from_state", sa.String(length=50), nullable=True),
            sa.Column("to_state", sa.String(length=50), nullable=False),
            sa.Column("transitioned_by", sa.String(length=255), nullable=False),
            sa.Column("transition_reason", sa.Text(), nullable=True),
            sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("idx_transitions_complaint", "ticket_state_transitions", ["complaint_id", "created_at"])
        op.create_index("idx_transitions_created", "ticket_state_transitions", ["created_at"])

    if "escalation_rules" not in tables:
        op.create_table(
            "escalation_rules",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
            sa.Column("rule_name", sa.String(length=100), nullable=False),
            sa.Column("trigger_condition", sa.String(length=50), nullable=False),
            sa.Column("escalation_level", sa.Integer(), nullable=False),
            sa.Column("escalate_to_team", sa.String(length=100), nullable=True),
            sa.Column("escalate_to_email", sa.String(length=255), nullable=True),
            sa.Column("notification_template", sa.Text(), nullable=True),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )

    if "ticket_comments" not in tables:
        op.create_table(
            "ticket_comments",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("complaint_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False),
            sa.Column("author_email", sa.String(length=255), nullable=False),
            sa.Column("author_name", sa.String(length=255), nullable=True),
            sa.Column("comment_type", sa.String(length=20), nullable=False, server_default="note"),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("is_internal", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("idx_comments_complaint", "ticket_comments", ["complaint_id", "created_at"])

    if "ticket_assignments" not in tables:
        op.create_table(
            "ticket_assignments",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("complaint_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False),
            sa.Column("assigned_to", sa.String(length=255), nullable=False),
            sa.Column("assigned_by", sa.String(length=255), nullable=True),
            sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("unassigned_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("assignment_reason", sa.Text(), nullable=True),
        )
        op.create_index("idx_assignments_complaint", "ticket_assignments", ["complaint_id"])
        op.create_index(
            "idx_assignments_agent",
            "ticket_assignments",
            ["assigned_to"],
            unique=False,
            postgresql_where=sa.text("unassigned_at IS NULL"),
        )

    # Seed economy SLA policies
    if "clients" in tables and "sla_policies" in tables:
        op.execute(
            """
            INSERT INTO sla_policies (client_id, name, priority_level, first_response_minutes, resolution_minutes)
            SELECT id, 'Critical - 15min/2hr', 'critical', 15, 120 FROM clients
            ON CONFLICT (client_id, priority_level) DO NOTHING
            """
        )
        op.execute(
            """
            INSERT INTO sla_policies (client_id, name, priority_level, first_response_minutes, resolution_minutes)
            SELECT id, 'High - 1hr/8hr', 'high', 60, 480 FROM clients
            ON CONFLICT (client_id, priority_level) DO NOTHING
            """
        )
        op.execute(
            """
            INSERT INTO sla_policies (client_id, name, priority_level, first_response_minutes, resolution_minutes)
            SELECT id, 'Medium - 4hr/24hr', 'medium', 240, 1440 FROM clients
            ON CONFLICT (client_id, priority_level) DO NOTHING
            """
        )
        op.execute(
            """
            INSERT INTO sla_policies (client_id, name, priority_level, first_response_minutes, resolution_minutes)
            SELECT id, 'Low - 24hr/72hr', 'low', 1440, 4320 FROM clients
            ON CONFLICT (client_id, priority_level) DO NOTHING
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "ticket_assignments" in tables:
        op.drop_table("ticket_assignments")
    if "ticket_comments" in tables:
        op.drop_table("ticket_comments")
    if "escalation_rules" in tables:
        op.drop_table("escalation_rules")
    if "ticket_state_transitions" in tables:
        op.drop_table("ticket_state_transitions")
    if "business_hours" in tables:
        op.drop_table("business_hours")
    if "sla_policies" in tables:
        op.drop_table("sla_policies")

    if "complaints" in tables:
        complaint_columns = {column["name"] for column in inspector.get_columns("complaints")}
        complaint_indexes = {index["name"] for index in inspector.get_indexes("complaints")}
        for index_name in ["idx_complaints_sla_due", "idx_complaints_state", "uq_complaints_ticket_number"]:
            if index_name in complaint_indexes:
                op.drop_index(index_name, table_name="complaints")
        for col in [
            "escalated_to",
            "escalated_at",
            "escalation_level",
            "sla_status",
            "sla_due_at",
            "last_reopened_at",
            "reopened_count",
            "ticket_number",
            "state_changed_at",
            "state",
        ]:
            if col in complaint_columns:
                op.drop_column("complaints", col)
