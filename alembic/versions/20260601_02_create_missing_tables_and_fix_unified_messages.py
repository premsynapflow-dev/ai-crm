"""create missing tables and fix unified_messages schema drift

Revision ID: 20260601_02
Revises: 20260601_01
Create Date: 2026-06-01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260601_02"
down_revision = "20260601_01"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _indexes(table: str) -> set[str]:
    return {i["name"] for i in sa.inspect(op.get_bind()).get_indexes(table)}


def _uuid():
    if op.get_bind().dialect.name == "postgresql":
        return postgresql.UUID(as_uuid=True)
    return sa.Uuid(as_uuid=True)


def _json():
    if op.get_bind().dialect.name == "postgresql":
        return postgresql.JSONB(astext_type=sa.Text())
    return sa.JSON()


def _empty_json():
    if op.get_bind().dialect.name == "postgresql":
        return sa.text("'{}'::jsonb")
    return sa.text("'{}'")


def _empty_array():
    if op.get_bind().dialect.name == "postgresql":
        return sa.text("'[]'::jsonb")
    return sa.text("'[]'")


def _add_col_if_missing(table: str, col: sa.Column) -> None:
    if col.name not in _columns(table):
        op.add_column(table, col)


def _create_idx_if_missing(name: str, table: str, cols_expr: str) -> None:
    op.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({cols_expr})")


def upgrade() -> None:
    tables = _tables()
    uuid = _uuid()
    json = _json()

    # ─── 1. Fix unified_messages column schema drift ────────────────────────
    if "unified_messages" in tables:
        cols = _columns("unified_messages")
        is_pg = op.get_bind().dialect.name == "postgresql"

        if "channel" not in cols:
            op.add_column("unified_messages", sa.Column("channel", sa.String(50), nullable=True))
            if "source" in cols:
                op.execute("UPDATE unified_messages SET channel = COALESCE(source, 'api')")
            else:
                op.execute("UPDATE unified_messages SET channel = 'api'")

        if "external_message_id" not in cols:
            op.add_column("unified_messages", sa.Column("external_message_id", sa.String(255), nullable=True))
            if "external_id" in cols:
                op.execute("UPDATE unified_messages SET external_message_id = COALESCE(external_id, '')")
            else:
                op.execute("UPDATE unified_messages SET external_message_id = ''")

        _add_col_if_missing("unified_messages", sa.Column("external_thread_id", sa.String(255), nullable=True))

        if "sender_id" not in cols:
            op.add_column("unified_messages", sa.Column("sender_id", sa.String(255), nullable=True))

        if "sender_name" not in cols:
            op.add_column("unified_messages", sa.Column("sender_name", sa.String(255), nullable=True))
            if "sender" in cols:
                op.execute("UPDATE unified_messages SET sender_name = sender")

        if "message_text" not in cols:
            op.add_column("unified_messages", sa.Column("message_text", sa.Text(), nullable=True))
            if "body" in cols:
                op.execute("UPDATE unified_messages SET message_text = body")

        if "attachments" not in cols:
            op.add_column("unified_messages", sa.Column("attachments", json, nullable=False, server_default=_empty_array()))

        if "timestamp" not in cols:
            op.add_column("unified_messages", sa.Column("timestamp", sa.DateTime(timezone=True), nullable=True))
            op.execute("UPDATE unified_messages SET timestamp = created_at")

        if "status" not in cols:
            op.add_column("unified_messages", sa.Column("status", sa.String(50), nullable=True))
            op.execute("UPDATE unified_messages SET status = 'sent'")

        if "raw_payload" not in cols:
            op.add_column("unified_messages", sa.Column("raw_payload", json, nullable=False, server_default=_empty_json()))

        _add_col_if_missing("unified_messages", sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"))
        _add_col_if_missing("unified_messages", sa.Column("last_error", sa.Text(), nullable=True))
        _add_col_if_missing("unified_messages", sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True))

        # Composite/single indexes needed by the ORM
        _create_idx_if_missing("idx_unified_messages_client_channel", "unified_messages", "client_id, channel")
        _create_idx_if_missing("idx_unified_messages_external_message_id", "unified_messages", "external_message_id")
        _create_idx_if_missing("idx_unified_messages_status", "unified_messages", "status")
        _create_idx_if_missing("idx_unified_messages_next_retry_at", "unified_messages", "next_retry_at")

    # ─── 2. Create channel_connections ──────────────────────────────────────
    if "channel_connections" not in tables:
        op.create_table(
            "channel_connections",
            sa.Column("id", uuid, primary_key=True),
            sa.Column("client_id", uuid, sa.ForeignKey("clients.id"), nullable=False, index=True),
            sa.Column("channel_type", sa.String(50), nullable=False),
            sa.Column("account_identifier", sa.String(255), nullable=True),
            sa.Column("access_token", sa.Text(), nullable=True),
            sa.Column("refresh_token", sa.Text(), nullable=True),
            sa.Column("token_expiry", sa.DateTime(timezone=True), nullable=True),
            sa.Column("metadata", json, nullable=False, server_default=_empty_json()),
            sa.Column("status", sa.String(20), nullable=False, server_default="active"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        _create_idx_if_missing("ix_channel_connections_channel_type", "channel_connections", "channel_type")

    # ─── 3. Create conversations ─────────────────────────────────────────────
    if "conversations" not in tables:
        op.create_table(
            "conversations",
            sa.Column("id", uuid, primary_key=True),
            sa.Column("client_id", uuid, sa.ForeignKey("clients.id"), nullable=False, index=True),
            sa.Column("customer_id", uuid, sa.ForeignKey("customers.id"), nullable=True, index=True),
            sa.Column("complaint_id", uuid, sa.ForeignKey("complaints.id"), nullable=True, index=True),
            sa.Column("channel", sa.String(50), nullable=False),
            sa.Column("external_thread_id", sa.String(255), nullable=True),
            sa.Column("subject", sa.String(500), nullable=True),
            sa.Column("status", sa.String(50), nullable=False, server_default="open"),
            sa.Column("metadata", json, nullable=False, server_default=_empty_json()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        _create_idx_if_missing("ix_conversations_status", "conversations", "status")

    # ─── 4. Create audit_logs ────────────────────────────────────────────────
    if "audit_logs" not in tables:
        op.create_table(
            "audit_logs",
            sa.Column("id", uuid, primary_key=True),
            sa.Column("client_id", uuid, nullable=True, index=True),
            sa.Column("user_id", uuid, nullable=True),
            sa.Column("action", sa.String(100), nullable=False),
            sa.Column("resource_type", sa.String(100), nullable=True),
            sa.Column("resource_id", sa.String(255), nullable=True),
            sa.Column("ip_address", sa.String(45), nullable=True),
            sa.Column("user_agent", sa.Text(), nullable=True),
            sa.Column("request_path", sa.String(500), nullable=True),
            sa.Column("request_method", sa.String(10), nullable=True),
            sa.Column("response_status", sa.Integer(), nullable=True),
            sa.Column("payload", json, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        _create_idx_if_missing("ix_audit_logs_created_at", "audit_logs", "created_at")

    # ─── 5. Create plan_features ─────────────────────────────────────────────
    if "plan_features" not in tables:
        op.create_table(
            "plan_features",
            sa.Column("id", uuid, primary_key=True),
            sa.Column("plan_name", sa.String(50), nullable=False, unique=True),
            sa.Column("features", json, nullable=False, server_default=_empty_json()),
            sa.Column("limits", json, nullable=False, server_default=_empty_json()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    # ─── 6. Create tenant_usage_tracking ─────────────────────────────────────
    if "tenant_usage_tracking" not in tables:
        op.create_table(
            "tenant_usage_tracking",
            sa.Column("id", uuid, primary_key=True),
            sa.Column("client_id", uuid, sa.ForeignKey("clients.id"), nullable=False, index=True),
            sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
            sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
            sa.Column("tickets_used", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("api_calls_used", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    # ─── 7. Create automation_settings ──────────────────────────────────────
    if "automation_settings" not in tables:
        op.create_table(
            "automation_settings",
            sa.Column("id", uuid, primary_key=True),
            sa.Column("client_id", uuid, sa.ForeignKey("clients.id"), nullable=False, unique=True),
            sa.Column("auto_reply_enabled", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("auto_escalate_enabled", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("follow_up_enabled", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("settings", json, nullable=False, server_default=_empty_json()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    # ─── 8. Create churn_outcomes ────────────────────────────────────────────
    if "churn_outcomes" not in tables:
        op.create_table(
            "churn_outcomes",
            sa.Column("id", uuid, primary_key=True),
            sa.Column("client_id", uuid, sa.ForeignKey("clients.id"), nullable=False, index=True),
            sa.Column("customer_id", uuid, sa.ForeignKey("customers.id"), nullable=True, index=True),
            sa.Column("complaint_id", uuid, sa.ForeignKey("complaints.id"), nullable=True),
            sa.Column("predicted_churn_score", sa.Float(), nullable=True),
            sa.Column("actual_outcome", sa.String(50), nullable=True),
            sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("metadata", json, nullable=True),
        )

    # ─── 9. Create knowledge_snippets ────────────────────────────────────────
    if "knowledge_snippets" not in tables:
        op.create_table(
            "knowledge_snippets",
            sa.Column("id", uuid, primary_key=True),
            sa.Column("client_id", uuid, sa.ForeignKey("clients.id"), nullable=False, index=True),
            sa.Column("title", sa.String(500), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("category", sa.String(100), nullable=True),
            sa.Column("tags", json, nullable=True),
            sa.Column("status", sa.String(50), nullable=False, server_default="active"),
            sa.Column("embedding_vector", json, nullable=True),
            sa.Column("created_by", uuid, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        _create_idx_if_missing("ix_knowledge_snippets_client_status", "knowledge_snippets", "client_id, status")

    # ─── 10. Create rbi_categories ───────────────────────────────────────────
    if "rbi_categories" not in tables:
        op.create_table(
            "rbi_categories",
            sa.Column("id", uuid, primary_key=True),
            sa.Column("category_code", sa.String(50), nullable=False, unique=True),
            sa.Column("category_name", sa.String(255), nullable=False),
            sa.Column("subcategory_code", sa.String(50), nullable=True),
            sa.Column("subcategory_name", sa.String(255), nullable=True),
            sa.Column("tat_days", sa.Integer(), nullable=False, server_default="30"),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    # ─── 11. Create rbi_complaint_categories ─────────────────────────────────
    if "rbi_complaint_categories" not in tables:
        op.create_table(
            "rbi_complaint_categories",
            sa.Column("id", uuid, primary_key=True),
            sa.Column("category_code", sa.String(50), nullable=False),
            sa.Column("category_name", sa.String(255), nullable=False),
            sa.Column("subcategory_code", sa.String(50), nullable=True),
            sa.Column("subcategory_name", sa.String(255), nullable=True),
            sa.Column("tat_days", sa.Integer(), nullable=False, server_default="30"),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    # ─── 12. Create rbi_escalation_log ───────────────────────────────────────
    if "rbi_escalation_log" not in tables:
        op.create_table(
            "rbi_escalation_log",
            sa.Column("id", uuid, primary_key=True),
            sa.Column("client_id", uuid, sa.ForeignKey("clients.id"), nullable=False, index=True),
            sa.Column("complaint_id", uuid, sa.ForeignKey("complaints.id"), nullable=True, index=True),
            sa.Column("escalation_level", sa.String(50), nullable=False),
            sa.Column("escalated_to_email", sa.String(255), nullable=True),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    # ─── 13. Create rbi_mis_reports ──────────────────────────────────────────
    if "rbi_mis_reports" not in tables:
        op.create_table(
            "rbi_mis_reports",
            sa.Column("id", uuid, primary_key=True),
            sa.Column("client_id", uuid, sa.ForeignKey("clients.id"), nullable=False, index=True),
            sa.Column("report_month", sa.Integer(), nullable=False),
            sa.Column("report_year", sa.Integer(), nullable=False),
            sa.Column("total_complaints", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("resolved_within_tat", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("breached_tat", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("category_breakdown", json, nullable=True),
            sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    # ─── 14. Create reply_feedback ───────────────────────────────────────────
    if "reply_feedback" not in tables:
        op.create_table(
            "reply_feedback",
            sa.Column("id", uuid, primary_key=True),
            sa.Column("client_id", uuid, sa.ForeignKey("clients.id"), nullable=False, index=True),
            sa.Column("complaint_id", uuid, sa.ForeignKey("complaints.id"), nullable=True, index=True),
            sa.Column("reply_draft_id", uuid, nullable=True),
            sa.Column("rating", sa.Integer(), nullable=True),
            sa.Column("comment", sa.Text(), nullable=True),
            sa.Column("submitted_by", uuid, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    # ─── 15. Create reply_ab_tests ───────────────────────────────────────────
    if "reply_ab_tests" not in tables:
        op.create_table(
            "reply_ab_tests",
            sa.Column("id", uuid, primary_key=True),
            sa.Column("client_id", uuid, sa.ForeignKey("clients.id"), nullable=False, index=True),
            sa.Column("test_name", sa.String(255), nullable=False),
            sa.Column("variant_a", sa.Text(), nullable=True),
            sa.Column("variant_b", sa.Text(), nullable=True),
            sa.Column("winner", sa.String(1), nullable=True),
            sa.Column("status", sa.String(50), nullable=False, server_default="running"),
            sa.Column("metadata", json, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    # ─── 16. Create reply_quality_metrics ────────────────────────────────────
    if "reply_quality_metrics" not in tables:
        op.create_table(
            "reply_quality_metrics",
            sa.Column("id", uuid, primary_key=True),
            sa.Column("client_id", uuid, sa.ForeignKey("clients.id"), nullable=False, index=True),
            sa.Column("complaint_id", uuid, sa.ForeignKey("complaints.id"), nullable=True, index=True),
            sa.Column("reply_draft_id", uuid, nullable=True),
            sa.Column("confidence_score", sa.Float(), nullable=True),
            sa.Column("tone_score", sa.Float(), nullable=True),
            sa.Column("relevance_score", sa.Float(), nullable=True),
            sa.Column("overall_score", sa.Float(), nullable=True),
            sa.Column("model_version", sa.String(100), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )


def downgrade() -> None:
    # Intentionally additive-only — no destructive downgrade.
    pass
