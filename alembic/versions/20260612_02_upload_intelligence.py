"""upload_intelligence_jobs table

Revision ID: 20260612_02
Revises: 20260612_01
Create Date: 2026-06-12
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260612_02"
down_revision = "20260612_01"
branch_labels = None
depends_on = None


def _tables():
    conn = op.get_bind()
    return {r[0] for r in conn.execute(sa.text(
        "SELECT tablename FROM pg_tables WHERE schemaname='public'"
    ))}


def upgrade() -> None:
    if "upload_intelligence_jobs" in _tables():
        return

    op.create_table(
        "upload_intelligence_jobs",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("client_id", sa.Uuid(as_uuid=True),
                  sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.Text, nullable=True),
        sa.Column("file_format", sa.String(10), nullable=False, server_default="csv"),
        sa.Column("data_type", sa.String(30), nullable=False, server_default="complaints"),
        sa.Column("status", sa.String(20), nullable=False, server_default="processing"),
        sa.Column("total_rows", sa.Integer, nullable=True),
        sa.Column("mapped_rows", sa.Integer, nullable=False, server_default="0"),
        sa.Column("failed_rows", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_log", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("analysis_status", sa.String(20), nullable=False, server_default="none"),
        sa.Column("analysis_results", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("artifact_id", sa.Uuid(as_uuid=True),
                  sa.ForeignKey("artifacts.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_upload_intel_client", "upload_intelligence_jobs", ["client_id"])
    op.create_index("idx_upload_intel_status", "upload_intelligence_jobs", ["client_id", "status", "created_at"])


def downgrade() -> None:
    if "upload_intelligence_jobs" not in _tables():
        return
    op.drop_table("upload_intelligence_jobs")
