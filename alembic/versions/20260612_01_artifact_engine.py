"""Artifact Engine: create artifacts table for recurring operational digests.

Revision ID: 20260612_01
Revises: 20260605_02
Create Date: 2026-06-12
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260612_01"
down_revision = "20260605_02"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return set(insp.get_table_names())


def upgrade() -> None:
    if "artifacts" not in _tables():
        op.create_table(
            "artifacts",
            sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
            sa.Column("client_id", sa.UUID(as_uuid=True),
                      sa.ForeignKey("clients.id", ondelete="CASCADE"),
                      nullable=False),
            sa.Column("artifact_type", sa.String(50), nullable=False,
                      server_default="weekly_operational_digest"),
            sa.Column("period_start", sa.Date(), nullable=False),
            sa.Column("period_end", sa.Date(), nullable=False),
            sa.Column("title", sa.String(255), nullable=False),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("sections_json", sa.JSON(), nullable=False,
                      server_default="{}"),
            sa.Column("edited_body", sa.Text(), nullable=True),
            sa.Column("status", sa.String(30), nullable=False,
                      server_default="draft"),
            sa.Column("reviewed_by", sa.String(255), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("rejection_reason", sa.Text(), nullable=True),
            sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("delivery_channel", sa.String(30), nullable=True),
            sa.Column("recipient", sa.String(255), nullable=True),
            sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("acted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("model_used", sa.String(50), nullable=True),
            sa.Column("generation_metadata", sa.JSON(), nullable=False,
                      server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True),
                      server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True),
                      server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("client_id", "artifact_type", "period_start",
                                name="uq_artifact_client_type_period"),
        )
        op.create_index("idx_artifacts_status", "artifacts",
                        ["client_id", "status", "created_at"])
        op.create_index("idx_artifacts_client", "artifacts", ["client_id"])


def downgrade() -> None:
    if "artifacts" in _tables():
        op.drop_index("idx_artifacts_client", "artifacts")
        op.drop_index("idx_artifacts_status", "artifacts")
        op.drop_table("artifacts")
