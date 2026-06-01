"""add performance indexes for high-frequency query patterns

Revision ID: 20260602_01
Revises: 20260601_06
Create Date: 2026-06-02
"""

from alembic import op
import sqlalchemy as sa

revision = "20260602_01"
down_revision = "20260601_06"
branch_labels = None
depends_on = None


def _existing_indexes(table: str) -> set:
    return {idx["name"] for idx in sa.inspect(op.get_bind()).get_indexes(table)}


def _existing_tables() -> set:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    tables = _existing_tables()

    if "complaints" in tables:
        existing = _existing_indexes("complaints")

        # (client_id, status, created_at) — covers list queries with status filter + default sort
        if "idx_complaints_client_status_created" not in existing:
            op.create_index(
                "idx_complaints_client_status_created",
                "complaints",
                ["client_id", "status", "created_at"],
            )

        # (client_id, created_at) — default inbox sort when no status filter
        if "idx_complaints_client_created" not in existing:
            op.create_index(
                "idx_complaints_client_created",
                "complaints",
                ["client_id", "created_at"],
            )

        # (client_id, ai_reply_status) — reply queue list
        if "idx_complaints_client_ai_reply_status" not in existing:
            op.create_index(
                "idx_complaints_client_ai_reply_status",
                "complaints",
                ["client_id", "ai_reply_status"],
            )

        # (client_id, sla_status, sla_due_at) — SLA monitor background scan
        if "idx_complaints_client_sla" not in existing:
            op.create_index(
                "idx_complaints_client_sla",
                "complaints",
                ["client_id", "sla_status", "sla_due_at"],
            )

        # (client_id, resolution_status, created_at) — open/resolved filter + sort
        if "idx_complaints_client_resolution" not in existing:
            op.create_index(
                "idx_complaints_client_resolution",
                "complaints",
                ["client_id", "resolution_status", "created_at"],
            )

        # (client_id, category) — routing lookups + analytics breakdowns
        if "idx_complaints_client_category" not in existing:
            op.create_index(
                "idx_complaints_client_category",
                "complaints",
                ["client_id", "category"],
            )

        # (client_id, priority, created_at) — priority-sorted inbox view
        if "idx_complaints_client_priority" not in existing:
            op.create_index(
                "idx_complaints_client_priority",
                "complaints",
                ["client_id", "priority", "created_at"],
            )

    if "request_audits" in tables:
        existing = _existing_indexes("request_audits")
        # Cleanup queries scan by created_at; no index = full table scan as audit table grows
        if "idx_request_audits_created_at" not in existing:
            op.create_index(
                "idx_request_audits_created_at",
                "request_audits",
                ["created_at"],
            )


def downgrade() -> None:
    tables = _existing_tables()

    if "complaints" in tables:
        for name in [
            "idx_complaints_client_status_created",
            "idx_complaints_client_created",
            "idx_complaints_client_ai_reply_status",
            "idx_complaints_client_sla",
            "idx_complaints_client_resolution",
            "idx_complaints_client_category",
            "idx_complaints_client_priority",
        ]:
            existing = _existing_indexes("complaints")
            if name in existing:
                op.drop_index(name, table_name="complaints")

    if "request_audits" in tables:
        existing = _existing_indexes("request_audits")
        if "idx_request_audits_created_at" in existing:
            op.drop_index("idx_request_audits_created_at", table_name="request_audits")
