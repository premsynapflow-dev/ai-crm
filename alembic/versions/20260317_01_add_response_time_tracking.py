"""add first response tracking to complaints

Revision ID: 20260317_01
Revises:
Create Date: 2026-03-17
"""

from alembic import op
import sqlalchemy as sa


revision = "20260317_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "complaints" not in tables:
        return
    columns = {column["name"] for column in inspector.get_columns("complaints")}
    indexes = {index["name"] for index in inspector.get_indexes("complaints")}

    if "first_response_at" not in columns:
        op.add_column(
            "complaints",
            sa.Column("first_response_at", sa.DateTime(timezone=True), nullable=True),
        )

    if "response_time_seconds" not in columns:
        op.add_column(
            "complaints",
            sa.Column("response_time_seconds", sa.Integer(), nullable=True),
        )
    else:
        op.alter_column(
            "complaints",
            "response_time_seconds",
            existing_type=sa.Float(),
            type_=sa.Integer(),
            existing_nullable=True,
            postgresql_using="response_time_seconds::integer",
        )

    if "idx_complaints_response_time" not in indexes:
        op.create_index(
            "idx_complaints_response_time",
            "complaints",
            ["response_time_seconds"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "complaints" not in tables:
        return
    indexes = {index["name"] for index in inspector.get_indexes("complaints")}
    columns = {column["name"] for column in inspector.get_columns("complaints")}

    if "idx_complaints_response_time" in indexes:
        op.drop_index("idx_complaints_response_time", table_name="complaints")

    if "response_time_seconds" in columns:
        op.drop_column("complaints", "response_time_seconds")

    if "first_response_at" in columns:
        op.drop_column("complaints", "first_response_at")
