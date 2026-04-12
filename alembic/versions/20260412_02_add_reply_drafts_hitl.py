"""add reply drafts for hitl auto reply

Revision ID: 20260412_02
Revises: 20260410_01
Create Date: 2026-04-12
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260412_02"
down_revision = "20260410_01"
branch_labels = None
depends_on = None


def _column_names(inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _unique_constraint_names(inspector, table_name: str) -> set[str]:
    return {constraint["name"] for constraint in inspector.get_unique_constraints(table_name) if constraint.get("name")}


def _enable_rls(table_name: str) -> None:
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")


def _disable_rls(table_name: str) -> None:
    op.execute(f"ALTER TABLE {table_name} NO FORCE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY")


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "reply_drafts" not in tables:
        op.create_table(
            "reply_drafts",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("complaint_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False),
            sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id"), nullable=False),
            sa.Column("ticket_id", sa.String(length=50), nullable=False),
            sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id", ondelete="SET NULL"), nullable=True),
            sa.Column("subject", sa.String(length=255), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'pending'")),
            sa.Column("confidence_score", sa.Float(), nullable=True),
            sa.Column("prompt_version", sa.String(length=50), nullable=False, server_default=sa.text("'auto_reply_with_hitl_v1'")),
            sa.Column("generation_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
            sa.UniqueConstraint("complaint_id", name="uq_reply_drafts_complaint"),
            sa.UniqueConstraint("client_id", "ticket_id", name="uq_reply_drafts_client_ticket"),
        )
        op.create_index("idx_reply_drafts_status", "reply_drafts", ["client_id", "status", "created_at"])
        op.create_index("idx_reply_drafts_customer", "reply_drafts", ["client_id", "customer_id", "created_at"])

    if "complaints" in tables:
        complaint_columns = _column_names(inspector, "complaints")
        if "last_replied_at" not in complaint_columns:
            op.add_column("complaints", sa.Column("last_replied_at", sa.DateTime(timezone=True), nullable=True))

    if "ai_reply_queue" in tables:
        queue_columns = _column_names(inspector, "ai_reply_queue")
        if "reply_draft_id" not in queue_columns:
            op.add_column(
                "ai_reply_queue",
                sa.Column("reply_draft_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("reply_drafts.id", ondelete="SET NULL"), nullable=True),
            )
        queue_indexes = _index_names(inspector, "ai_reply_queue")
        if "ix_ai_reply_queue_reply_draft_id" not in queue_indexes:
            op.create_index("ix_ai_reply_queue_reply_draft_id", "ai_reply_queue", ["reply_draft_id"])
        queue_uniques = _unique_constraint_names(inspector, "ai_reply_queue")
        if "uq_ai_reply_queue_draft" not in queue_uniques:
            op.create_unique_constraint("uq_ai_reply_queue_draft", "ai_reply_queue", ["reply_draft_id"])

    if bind.dialect.name.startswith("postgresql") and "reply_drafts" in set(sa.inspect(bind).get_table_names()):
        _enable_rls("reply_drafts")
        op.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_policies
                    WHERE schemaname = current_schema()
                      AND tablename = 'reply_drafts'
                      AND policyname = 'reply_drafts_tenant_isolation_policy'
                ) THEN
                    CREATE POLICY reply_drafts_tenant_isolation_policy ON reply_drafts
                        FOR ALL
                        USING (client_id::text = current_setting('app.current_client_id', true))
                        WITH CHECK (client_id::text = current_setting('app.current_client_id', true));
                END IF;
            END $$;
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "ai_reply_queue" in tables:
        queue_uniques = _unique_constraint_names(inspector, "ai_reply_queue")
        if "uq_ai_reply_queue_draft" in queue_uniques:
            op.drop_constraint("uq_ai_reply_queue_draft", "ai_reply_queue", type_="unique")
        queue_indexes = _index_names(inspector, "ai_reply_queue")
        if "ix_ai_reply_queue_reply_draft_id" in queue_indexes:
            op.drop_index("ix_ai_reply_queue_reply_draft_id", table_name="ai_reply_queue")
        queue_columns = _column_names(inspector, "ai_reply_queue")
        if "reply_draft_id" in queue_columns:
            op.drop_column("ai_reply_queue", "reply_draft_id")

    if "complaints" in tables:
        complaint_columns = _column_names(inspector, "complaints")
        if "last_replied_at" in complaint_columns:
            op.drop_column("complaints", "last_replied_at")

    if "reply_drafts" in tables:
        if bind.dialect.name.startswith("postgresql"):
            op.execute("DROP POLICY IF EXISTS reply_drafts_tenant_isolation_policy ON reply_drafts")
            _disable_rls("reply_drafts")
        draft_indexes = _index_names(inspector, "reply_drafts")
        if "idx_reply_drafts_customer" in draft_indexes:
            op.drop_index("idx_reply_drafts_customer", table_name="reply_drafts")
        if "idx_reply_drafts_status" in draft_indexes:
            op.drop_index("idx_reply_drafts_status", table_name="reply_drafts")
        op.drop_table("reply_drafts")
