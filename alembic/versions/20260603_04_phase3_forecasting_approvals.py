"""Phase 3: complaint surge forecasting and approval chain workflow tables.

Revision ID: 20260603_04
Revises: 20260603_03
Create Date: 2026-06-03
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260603_04"
down_revision = "20260603_03"
branch_labels = None
depends_on = None


def _is_pg() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _uuid():
    return postgresql.UUID(as_uuid=True) if _is_pg() else sa.Uuid(as_uuid=True)


def _jsonb():
    return postgresql.JSONB(astext_type=sa.Text()) if _is_pg() else sa.JSON()


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    existing = _tables()

    # -- complaint_forecasts: EWMA surge forecast + actuals --
    if "complaint_forecasts" not in existing:
        op.create_table(
            "complaint_forecasts",
            sa.Column("id", _uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column(
                "client_id", _uuid(),
                sa.ForeignKey("clients.id", ondelete="CASCADE"),
                nullable=False, index=True,
            ),
            sa.Column("forecast_hour", sa.DateTime(timezone=True), nullable=False),
            sa.Column("predicted_count", sa.Float, nullable=False),
            sa.Column("actual_count", sa.Integer, nullable=True),
            sa.Column("alert_triggered", sa.Boolean, nullable=False, server_default="false"),
            sa.Column(
                "computed_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.UniqueConstraint("client_id", "forecast_hour", name="uq_complaint_forecasts_client_hour"),
        )
        op.create_index(
            "idx_complaint_forecasts_client_hour",
            "complaint_forecasts",
            ["client_id", "forecast_hour"],
        )

    # -- approval_requests: human-in-the-loop workflow approvals --
    if "approval_requests" not in existing:
        op.create_table(
            "approval_requests",
            sa.Column("id", _uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column(
                "client_id", _uuid(),
                sa.ForeignKey("clients.id", ondelete="CASCADE"),
                nullable=False, index=True,
            ),
            sa.Column(
                "complaint_id", _uuid(),
                sa.ForeignKey("complaints.id", ondelete="CASCADE"),
                nullable=False, index=True,
            ),
            sa.Column(
                "workflow_execution_id", _uuid(),
                sa.ForeignKey("workflow_executions.id", ondelete="SET NULL"),
                nullable=True, index=True,
            ),
            sa.Column(
                "approver_user_id", _uuid(),
                sa.ForeignKey("client_users.id", ondelete="SET NULL"),
                nullable=True, index=True,
            ),
            sa.Column("requested_by", sa.String(255), nullable=True),
            sa.Column("approver_role", sa.String(50), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
            sa.Column("notes", sa.Text, nullable=True),
            sa.Column("on_approve_actions", _jsonb(), nullable=False, server_default="[]"),
            sa.Column("on_reject_actions", _jsonb(), nullable=False, server_default="[]"),
            sa.Column("timeout_hours", sa.Integer, nullable=False, server_default="24"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index(
            "idx_approval_requests_client_status",
            "approval_requests",
            ["client_id", "status"],
        )
        op.create_index(
            "idx_approval_requests_complaint",
            "approval_requests",
            ["complaint_id"],
        )

    # -- skill_map config on clients (JSON config: category→intent→[skill,...]) --
    client_cols = _columns("clients")
    if "skill_map" not in client_cols:
        op.add_column(
            "clients",
            sa.Column("skill_map", _jsonb(), nullable=False, server_default="{}"),
        )


def downgrade() -> None:
    existing = _tables()

    if "approval_requests" in existing:
        op.drop_table("approval_requests")

    if "complaint_forecasts" in existing:
        op.drop_table("complaint_forecasts")

    if "clients" in existing:
        client_cols = _columns("clients")
        if "skill_map" in client_cols:
            op.drop_column("clients", "skill_map")
