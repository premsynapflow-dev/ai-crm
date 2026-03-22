"""add synapflow feature columns

Revision ID: 20260322_01
Revises: 20260318_01
Create Date: 2026-03-22
"""

from alembic import op
import sqlalchemy as sa


revision = "20260322_01"
down_revision = "20260318_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "complaints" not in tables:
        return

    complaint_columns = {column["name"] for column in inspector.get_columns("complaints")}

    if "sentiment_score" not in complaint_columns:
        op.add_column("complaints", sa.Column("sentiment_score", sa.Integer(), nullable=True))
    if "sentiment_label" not in complaint_columns:
        op.add_column("complaints", sa.Column("sentiment_label", sa.String(length=50), nullable=True))
    if "sentiment_indicators" not in complaint_columns:
        op.add_column("complaints", sa.Column("sentiment_indicators", sa.JSON(), nullable=True))
    if "assigned_to" not in complaint_columns:
        op.add_column("complaints", sa.Column("assigned_to", sa.String(length=255), nullable=True))
    if "satisfaction_score" not in complaint_columns:
        op.add_column("complaints", sa.Column("satisfaction_score", sa.Integer(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "complaints" not in tables:
        return

    complaint_columns = {column["name"] for column in inspector.get_columns("complaints")}

    if "satisfaction_score" in complaint_columns:
        op.drop_column("complaints", "satisfaction_score")
    if "assigned_to" in complaint_columns:
        op.drop_column("complaints", "assigned_to")
    if "sentiment_indicators" in complaint_columns:
        op.drop_column("complaints", "sentiment_indicators")
    if "sentiment_label" in complaint_columns:
        op.drop_column("complaints", "sentiment_label")
    if "sentiment_score" in complaint_columns:
        op.drop_column("complaints", "sentiment_score")
