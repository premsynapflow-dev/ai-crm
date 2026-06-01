"""create job_queue table

Revision ID: 20260601_01
Revises: 20260522_03
Create Date: 2026-06-01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260601_01"
down_revision = "20260522_03"
branch_labels = None
depends_on = None


def _uuid_type():
    if op.get_bind().dialect.name == "postgresql":
        return postgresql.UUID(as_uuid=True)
    return sa.Uuid(as_uuid=True)


def _json_type():
    if op.get_bind().dialect.name == "postgresql":
        return postgresql.JSONB(astext_type=sa.Text())
    return sa.JSON()


def upgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "job_queue" in tables:
        return

    op.create_table(
        "job_queue",
        sa.Column("id", _uuid_type(), primary_key=True),
        sa.Column("job_type", sa.String(100), nullable=False),
        sa.Column("payload", _json_type(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="queued"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index("ix_job_queue_job_type", "job_queue", ["job_type"])
    op.create_index("ix_job_queue_status", "job_queue", ["status"])
    op.create_index(
        "idx_job_queue_status_scheduled",
        "job_queue",
        ["status", "scheduled_for", "created_at"],
    )


def downgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "job_queue" not in tables:
        return

    op.drop_index("idx_job_queue_status_scheduled", table_name="job_queue")
    op.drop_index("ix_job_queue_status", table_name="job_queue")
    op.drop_index("ix_job_queue_job_type", table_name="job_queue")
    op.drop_table("job_queue")
