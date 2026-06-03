"""Phase 4: workflow outcomes tracker and churn feedback loop.

Revision ID: 20260603_05
Revises: 20260603_04
Create Date: 2026-06-03
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260603_05"
down_revision = "20260603_04"
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

    # -- workflow_outcomes: post-execution outcome measurements (T+48h) --
    if "workflow_outcomes" not in existing:
        op.create_table(
            "workflow_outcomes",
            sa.Column("id", _uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column(
                "client_id", _uuid(),
                sa.ForeignKey("clients.id", ondelete="CASCADE"),
                nullable=False, index=True,
            ),
            sa.Column(
                "execution_id", _uuid(),
                sa.ForeignKey("workflow_executions.id", ondelete="CASCADE"),
                nullable=False, index=True,
            ),
            sa.Column(
                "complaint_id", _uuid(),
                sa.ForeignKey("complaints.id", ondelete="CASCADE"),
                nullable=True, index=True,
            ),
            sa.Column("customer_id", _uuid(), nullable=True, index=True),
            sa.Column("resolved", sa.Boolean, nullable=True),
            sa.Column("sla_met", sa.Boolean, nullable=True),
            sa.Column("escalation_prevented", sa.Boolean, nullable=True),
            sa.Column("customer_churned", sa.Boolean, nullable=True),
            sa.Column("churn_score_before", sa.Float, nullable=True),
            sa.Column("churn_score_after", sa.Float, nullable=True),
            sa.Column("resolution_time_hours", sa.Float, nullable=True),
            sa.Column("measure_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("measured_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.UniqueConstraint("execution_id", name="uq_workflow_outcomes_execution"),
        )
        op.create_index(
            "idx_workflow_outcomes_client_time",
            "workflow_outcomes",
            ["client_id", "created_at"],
        )

    # -- outcome_weights: per-client feedback loop calibration weights --
    if "outcome_weights" not in existing:
        op.create_table(
            "outcome_weights",
            sa.Column("id", _uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column(
                "client_id", _uuid(),
                sa.ForeignKey("clients.id", ondelete="CASCADE"),
                nullable=False, unique=True, index=True,
            ),
            sa.Column("weights", _jsonb(), nullable=False, server_default="{}"),
            sa.Column("calibration_count", sa.Integer, nullable=False, server_default="0"),
            sa.Column(
                "last_calibrated_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
        )

    # -- measure_at column on workflow_executions for deferred outcome scheduling --
    if "workflow_executions" in existing:
        exec_cols = _columns("workflow_executions")
        if "measure_outcome_at" not in exec_cols:
            op.add_column(
                "workflow_executions",
                sa.Column("measure_outcome_at", sa.DateTime(timezone=True), nullable=True),
            )


def downgrade() -> None:
    existing = _tables()

    if "outcome_weights" in existing:
        op.drop_table("outcome_weights")

    if "workflow_outcomes" in existing:
        op.drop_table("workflow_outcomes")

    if "workflow_executions" in existing:
        exec_cols = _columns("workflow_executions")
        if "measure_outcome_at" in exec_cols:
            op.drop_column("workflow_executions", "measure_outcome_at")
