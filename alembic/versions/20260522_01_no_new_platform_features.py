"""add no-new-platform intelligence features

Revision ID: 20260522_01
Revises: 20260521_01
Create Date: 2026-05-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260522_01"
down_revision = "20260521_01"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _indexes(table_name: str) -> set[str]:
    return {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def _uuid_type():
    if op.get_bind().dialect.name == "postgresql":
        return postgresql.UUID(as_uuid=True)
    return sa.Uuid(as_uuid=True)


def _json_type():
    if op.get_bind().dialect.name == "postgresql":
        return postgresql.JSONB(astext_type=sa.Text())
    return sa.JSON()


def _empty_json_default():
    if op.get_bind().dialect.name == "postgresql":
        return sa.text("'{}'::jsonb")
    return sa.text("'{}'")


def _empty_list_default():
    if op.get_bind().dialect.name == "postgresql":
        return sa.text("'[]'::jsonb")
    return sa.text("'[]'")


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if column.name not in _columns(table_name):
        op.add_column(table_name, column)


def _create_index_if_missing(name: str, table_name: str, columns: list[str], **kwargs) -> None:
    if name not in _indexes(table_name):
        op.create_index(name, table_name, columns, **kwargs)


def upgrade() -> None:
    tables = _tables()
    uuid_type = _uuid_type()
    json_type = _json_type()

    if "automation_rules" in tables:
        _add_column_if_missing("automation_rules", sa.Column("workflow_name", sa.String(length=100), nullable=True))
        _add_column_if_missing("automation_rules", sa.Column("trigger_definition", json_type, nullable=True))
        _add_column_if_missing("automation_rules", sa.Column("condition_definition", json_type, nullable=True))
        _add_column_if_missing("automation_rules", sa.Column("action_definition", json_type, nullable=True))

    if "churn_outcomes" not in tables:
        op.create_table(
            "churn_outcomes",
            sa.Column("id", uuid_type, primary_key=True, nullable=False),
            sa.Column("client_id", uuid_type, nullable=False),
            sa.Column("customer_id", uuid_type, nullable=False),
            sa.Column("outcome_type", sa.String(length=30), nullable=False),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("risk_score_at_outcome", sa.Float(), nullable=True),
            sa.Column("metadata", json_type, nullable=False, server_default=_empty_json_default()),
            sa.Column("recorded_by", sa.String(length=255), nullable=True),
            sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
            sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
            sa.UniqueConstraint("client_id", "customer_id", "outcome_type", name="uq_churn_outcomes_customer_type"),
        )
    _create_index_if_missing("idx_churn_outcomes_client_time", "churn_outcomes", ["client_id", "recorded_at"])
    _create_index_if_missing("idx_churn_outcomes_customer_time", "churn_outcomes", ["customer_id", "recorded_at"])

    if "agent_corrections" not in tables:
        op.create_table(
            "agent_corrections",
            sa.Column("id", uuid_type, primary_key=True, nullable=False),
            sa.Column("client_id", uuid_type, nullable=False),
            sa.Column("complaint_id", uuid_type, nullable=True),
            sa.Column("customer_id", uuid_type, nullable=True),
            sa.Column("correction_type", sa.String(length=50), nullable=False),
            sa.Column("original_value", json_type, nullable=True),
            sa.Column("corrected_value", json_type, nullable=False),
            sa.Column("feedback_score", sa.Integer(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("corrected_by", sa.String(length=255), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
            sa.ForeignKeyConstraint(["complaint_id"], ["complaints.id"]),
            sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        )
    _create_index_if_missing("idx_agent_corrections_client_time", "agent_corrections", ["client_id", "created_at"])
    _create_index_if_missing("idx_agent_corrections_complaint_time", "agent_corrections", ["complaint_id", "created_at"])

    if "knowledge_snippets" not in tables:
        op.create_table(
            "knowledge_snippets",
            sa.Column("id", uuid_type, primary_key=True, nullable=False),
            sa.Column("client_id", uuid_type, nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("category", sa.String(length=100), nullable=True),
            sa.Column("keywords", json_type, nullable=False, server_default=_empty_list_default()),
            sa.Column("source_type", sa.String(length=50), nullable=False, server_default="manual"),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
            sa.Column("created_by", sa.String(length=255), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
        )
    _create_index_if_missing("idx_knowledge_snippets_client_status", "knowledge_snippets", ["client_id", "status"])
    _create_index_if_missing("idx_knowledge_snippets_client_category", "knowledge_snippets", ["client_id", "category"])

    if "model_audit_logs" not in tables:
        op.create_table(
            "model_audit_logs",
            sa.Column("id", uuid_type, primary_key=True, nullable=False),
            sa.Column("client_id", uuid_type, nullable=True),
            sa.Column("complaint_id", uuid_type, nullable=True),
            sa.Column("customer_id", uuid_type, nullable=True),
            sa.Column("provider", sa.String(length=50), nullable=False),
            sa.Column("model", sa.String(length=100), nullable=True),
            sa.Column("task_type", sa.String(length=100), nullable=False),
            sa.Column("prompt_hash", sa.String(length=64), nullable=True),
            sa.Column("prompt_preview", sa.Text(), nullable=True),
            sa.Column("output_preview", sa.Text(), nullable=True),
            sa.Column("confidence_score", sa.Float(), nullable=True),
            sa.Column("latency_ms", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="succeeded"),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("metadata", json_type, nullable=False, server_default=_empty_json_default()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
            sa.ForeignKeyConstraint(["complaint_id"], ["complaints.id"]),
            sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        )
    _create_index_if_missing("idx_model_audit_client_time", "model_audit_logs", ["client_id", "created_at"])
    _create_index_if_missing("idx_model_audit_complaint_time", "model_audit_logs", ["complaint_id", "created_at"])
    _create_index_if_missing("idx_model_audit_task_time", "model_audit_logs", ["task_type", "created_at"])


def downgrade() -> None:
    tables = _tables()
    for table_name in ("model_audit_logs", "knowledge_snippets", "agent_corrections", "churn_outcomes"):
        if table_name in tables:
            op.drop_table(table_name)
