"""add missing analytics and queue columns

Revision ID: 20260318_01
Revises: 20260317_01
Create Date: 2026-03-18
"""

from alembic import op
import sqlalchemy as sa


revision = "20260318_01"
down_revision = "20260317_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "complaints" in tables:
        complaint_columns = {column["name"] for column in inspector.get_columns("complaints")}
        if "resolved_at" not in complaint_columns:
            op.add_column(
                "complaints",
                sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
            )
        if "first_response_at" not in complaint_columns:
            op.add_column(
                "complaints",
                sa.Column("first_response_at", sa.DateTime(timezone=True), nullable=True),
            )
        if "response_time_seconds" not in complaint_columns:
            op.add_column(
                "complaints",
                sa.Column("response_time_seconds", sa.Integer(), nullable=True),
            )

    if "job_queue" in tables:
        job_queue_columns = {column["name"] for column in inspector.get_columns("job_queue")}
        if "last_error" not in job_queue_columns:
            op.add_column(
                "job_queue",
                sa.Column("last_error", sa.Text(), nullable=True),
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "job_queue" in tables:
        job_queue_columns = {column["name"] for column in inspector.get_columns("job_queue")}
        if "last_error" in job_queue_columns:
            op.drop_column("job_queue", "last_error")

    if "complaints" in tables:
        complaint_columns = {column["name"] for column in inspector.get_columns("complaints")}
        if "resolved_at" in complaint_columns:
            op.drop_column("complaints", "resolved_at")
