"""fix conversations table: customer_id type, missing columns, unique constraint

Revision ID: 20260602_02
Revises: 20260602_01
Create Date: 2026-06-02

The conversations table was created with a UUID FK for customer_id, but the ORM
model and upsert code use String(255). Missing columns and the unique constraint
required by the ON CONFLICT upsert were never added, causing 100% failure on
Gmail inbox ingestion.
"""

from alembic import op
import sqlalchemy as sa

revision = "20260602_02"
down_revision = "20260602_01"
branch_labels = None
depends_on = None


def _has_column(conn, table: str, column: str) -> bool:
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    )
    return result.fetchone() is not None


def _has_constraint(conn, table: str, constraint: str) -> bool:
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.table_constraints "
            "WHERE table_name = :t AND constraint_name = :c"
        ),
        {"t": table, "c": constraint},
    )
    return result.fetchone() is not None


def _has_index(conn, index_name: str) -> bool:
    result = conn.execute(
        sa.text("SELECT 1 FROM pg_indexes WHERE indexname = :i"),
        {"i": index_name},
    )
    return result.fetchone() is not None


def upgrade():
    conn = op.get_bind()

    # 1. Fix customer_id: drop any FK constraint, change type to VARCHAR(255).
    #    The ORM stores customer_id as str(uuid) — not a FK relationship.
    fk_rows = conn.execute(
        sa.text(
            "SELECT constraint_name FROM information_schema.table_constraints "
            "WHERE table_name = 'conversations' AND constraint_type = 'FOREIGN KEY' "
            "AND constraint_name LIKE '%customer%'"
        )
    ).fetchall()
    for (fk_name,) in fk_rows:
        op.drop_constraint(fk_name, "conversations", type_="foreignkey")

    conn.execute(
        sa.text(
            "ALTER TABLE conversations "
            "ALTER COLUMN customer_id TYPE VARCHAR(255) USING customer_id::text"
        )
    )

    # 2. Add columns present in the ORM model but missing from the original migration.
    if not _has_column(conn, "conversations", "last_message_at"):
        op.add_column(
            "conversations",
            sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        )

    if not _has_column(conn, "conversations", "assigned_to"):
        op.add_column(
            "conversations",
            sa.Column("assigned_to", sa.Uuid(as_uuid=True), nullable=True),
        )

    if not _has_column(conn, "conversations", "escalation_level"):
        op.add_column(
            "conversations",
            sa.Column(
                "escalation_level",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
        )

    if not _has_column(conn, "conversations", "last_escalated_at"):
        op.add_column(
            "conversations",
            sa.Column("last_escalated_at", sa.DateTime(timezone=True), nullable=True),
        )

    if not _has_column(conn, "conversations", "escalation_metadata_json"):
        op.add_column(
            "conversations",
            sa.Column(
                "escalation_metadata_json",
                sa.JSON(),
                nullable=False,
                server_default="{}",
            ),
        )

    # 3. Unique constraint required by the ON CONFLICT upsert in ensure_conversation().
    # Fix event_logs: action column is NOT NULL but the ORM never sets it.
    conn.execute(sa.text("ALTER TABLE event_logs ALTER COLUMN action DROP NOT NULL"))
    conn.execute(sa.text("ALTER TABLE event_logs ALTER COLUMN client_id DROP NOT NULL"))

    # Fix usage_records: metric_type is NOT NULL but UsageRecord ORM doesn't set it.
    conn.execute(sa.text("ALTER TABLE usage_records ALTER COLUMN metric_type SET DEFAULT 'tickets'"))

    if not _has_constraint(conn, "conversations", "uq_conversations_client_channel_thread"):
        op.create_unique_constraint(
            "uq_conversations_client_channel_thread",
            "conversations",
            ["client_id", "channel", "external_thread_id"],
        )

    # 4. Indexes referenced in the ORM model's __table_args__.
    if not _has_index(conn, "idx_conversations_last_message_at"):
        op.create_index(
            "idx_conversations_last_message_at",
            "conversations",
            ["last_message_at"],
        )

    if not _has_index(conn, "idx_conversations_client_external_thread"):
        op.create_index(
            "idx_conversations_client_external_thread",
            "conversations",
            ["client_id", "external_thread_id"],
        )

    if not _has_index(conn, "idx_conversations_escalation_level"):
        op.create_index(
            "idx_conversations_escalation_level",
            "conversations",
            ["client_id", "escalation_level"],
        )


def downgrade():
    op.drop_constraint(
        "uq_conversations_client_channel_thread", "conversations", type_="unique"
    )
