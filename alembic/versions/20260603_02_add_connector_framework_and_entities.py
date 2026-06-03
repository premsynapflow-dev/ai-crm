"""Add universal connector framework, poll_cursors, bulk_import_jobs, complaint_entities.

Revision ID: 20260603_02
Revises: 20260603_01
Create Date: 2026-06-03
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260603_02"
down_revision = "20260603_01"
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

    # -- poll_cursors: tracks per-connector ingestion cursor to prevent duplicate polling --
    if "poll_cursors" not in existing:
        op.create_table(
            "poll_cursors",
            sa.Column("id", _uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("connection_id", _uuid(),
                      sa.ForeignKey("channel_connections.id", ondelete="CASCADE"), nullable=False),
            sa.Column("cursor_value", sa.Text, nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.UniqueConstraint("connection_id", name="uq_poll_cursors_connection"),
        )
        op.create_index("idx_poll_cursors_connection", "poll_cursors", ["connection_id"])

    # -- channel_connections: polling config columns --
    cc_cols = _columns("channel_connections")
    if "poll_interval_minutes" not in cc_cols:
        op.add_column("channel_connections", sa.Column(
            "poll_interval_minutes", sa.Integer, nullable=True, server_default="60"))
    if "last_poll_at" not in cc_cols:
        op.add_column("channel_connections", sa.Column(
            "last_poll_at", sa.DateTime(timezone=True), nullable=True))
    if "poll_enabled" not in cc_cols:
        op.add_column("channel_connections", sa.Column(
            "poll_enabled", sa.Boolean, nullable=False, server_default="true"))

    # -- bulk_import_jobs: tracks CSV upload batch processing --
    if "bulk_import_jobs" not in existing:
        op.create_table(
            "bulk_import_jobs",
            sa.Column("id", _uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("client_id", _uuid(),
                      sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("filename", sa.Text, nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="processing"),
            sa.Column("total_rows", sa.Integer, nullable=True),
            sa.Column("imported_rows", sa.Integer, nullable=False, server_default="0"),
            sa.Column("failed_rows", sa.Integer, nullable=False, server_default="0"),
            sa.Column("error_log", _jsonb(), nullable=False, server_default="[]"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("idx_bulk_import_jobs_client_status", "bulk_import_jobs", ["client_id", "status"])

    # -- complaint_entities: NER extraction results per complaint --
    if "complaint_entities" not in existing:
        op.create_table(
            "complaint_entities",
            sa.Column("id", _uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("complaint_id", _uuid(),
                      sa.ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False),
            sa.Column("entity_type", sa.String(30), nullable=False),
            sa.Column("entity_value", sa.Text, nullable=False),
            sa.Column("confidence", sa.Float, nullable=False, server_default="1.0"),
            sa.Column("extracted_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        )
        op.create_index("idx_complaint_entities_complaint", "complaint_entities", ["complaint_id"])
        op.create_index("idx_complaint_entities_type_value", "complaint_entities",
                        ["entity_type", "entity_value"])


def downgrade() -> None:
    existing = _tables()
    if "complaint_entities" in existing:
        op.drop_table("complaint_entities")
    if "bulk_import_jobs" in existing:
        op.drop_table("bulk_import_jobs")
    cc_cols = _columns("channel_connections")
    for col in ("poll_enabled", "last_poll_at", "poll_interval_minutes"):
        if col in cc_cols:
            op.drop_column("channel_connections", col)
    if "poll_cursors" in existing:
        op.drop_table("poll_cursors")
