"""add event intelligence and workflow execution logs

Revision ID: 20260521_01
Revises: 20260412_03
Create Date: 2026-05-21
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260521_01"
down_revision = "20260412_03"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns(table_name)}


def _indexes(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _json_type():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.JSONB(astext_type=sa.Text())
    return sa.JSON()


def _empty_json_default():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return sa.text("'{}'::jsonb")
    return sa.text("'{}'")


def _uuid_type():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.UUID(as_uuid=True)
    return sa.Uuid(as_uuid=True)


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if column.name not in _columns(table_name):
        op.add_column(table_name, column)


def _create_index_if_missing(name: str, table_name: str, columns: list[str], **kwargs) -> None:
    if name not in _indexes(table_name):
        op.create_index(name, table_name, columns, **kwargs)


def upgrade() -> None:
    tables = _tables()
    uuid_type = _uuid_type()

    if "event_logs" in tables:
        _add_column_if_missing("event_logs", sa.Column("customer_id", uuid_type, nullable=True))
        _add_column_if_missing("event_logs", sa.Column("complaint_id", uuid_type, nullable=True))
        _add_column_if_missing("event_logs", sa.Column("source", sa.String(length=50), nullable=True))
        _add_column_if_missing("event_logs", sa.Column("actor_type", sa.String(length=50), nullable=True))
        _add_column_if_missing("event_logs", sa.Column("event_timestamp", sa.DateTime(timezone=True), nullable=True))
        _add_column_if_missing("event_logs", sa.Column("sentiment_score", sa.Float(), nullable=True))
        _add_column_if_missing("event_logs", sa.Column("risk_delta", sa.Float(), nullable=True))
        op.execute("UPDATE event_logs SET event_timestamp = created_at WHERE event_timestamp IS NULL")
        _create_index_if_missing("ix_event_logs_customer_id", "event_logs", ["customer_id"])
        _create_index_if_missing("ix_event_logs_complaint_id", "event_logs", ["complaint_id"])
        _create_index_if_missing("ix_event_logs_event_timestamp", "event_logs", ["event_timestamp"])
        _create_index_if_missing("idx_event_logs_client_time", "event_logs", ["client_id", "event_timestamp"])
        _create_index_if_missing("idx_event_logs_customer_time", "event_logs", ["customer_id", "event_timestamp"])
        _create_index_if_missing("idx_event_logs_complaint_time", "event_logs", ["complaint_id", "event_timestamp"])
        _create_index_if_missing("idx_event_logs_type_time", "event_logs", ["client_id", "event_type", "event_timestamp"])

    if "message_events" in tables:
        _add_column_if_missing("message_events", sa.Column("client_id", uuid_type, nullable=True))
        _add_column_if_missing("message_events", sa.Column("customer_id", uuid_type, nullable=True))
        _add_column_if_missing("message_events", sa.Column("complaint_id", uuid_type, nullable=True))
        _add_column_if_missing("message_events", sa.Column("source", sa.String(length=50), nullable=True))
        _add_column_if_missing("message_events", sa.Column("actor_type", sa.String(length=50), nullable=True))
        _add_column_if_missing("message_events", sa.Column("event_timestamp", sa.DateTime(timezone=True), nullable=True))
        _add_column_if_missing("message_events", sa.Column("sentiment_score", sa.Float(), nullable=True))
        _add_column_if_missing("message_events", sa.Column("risk_delta", sa.Float(), nullable=True))
        op.execute("UPDATE message_events SET event_timestamp = created_at WHERE event_timestamp IS NULL")
        _create_index_if_missing("ix_message_events_client_id", "message_events", ["client_id"])
        _create_index_if_missing("ix_message_events_customer_id", "message_events", ["customer_id"])
        _create_index_if_missing("ix_message_events_complaint_id", "message_events", ["complaint_id"])
        _create_index_if_missing("ix_message_events_event_timestamp", "message_events", ["event_timestamp"])
        _create_index_if_missing("idx_message_events_client_time", "message_events", ["client_id", "event_timestamp"])
        _create_index_if_missing("idx_message_events_customer_time", "message_events", ["customer_id", "event_timestamp"])
        _create_index_if_missing("idx_message_events_complaint_time", "message_events", ["complaint_id", "event_timestamp"])

    if "workflow_executions" not in tables:
        op.create_table(
            "workflow_executions",
            sa.Column("id", uuid_type, primary_key=True, nullable=False),
            sa.Column("client_id", uuid_type, nullable=False),
            sa.Column("automation_rule_id", uuid_type, nullable=True),
            sa.Column("complaint_id", uuid_type, nullable=True),
            sa.Column("customer_id", uuid_type, nullable=True),
            sa.Column("trigger_event_type", sa.String(length=100), nullable=True),
            sa.Column("action_type", sa.String(length=50), nullable=False),
            sa.Column("execution_status", sa.String(length=30), nullable=False, server_default="succeeded"),
            sa.Column("execution_logs", _json_type(), nullable=False, server_default=_empty_json_default()),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("executed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
            sa.ForeignKeyConstraint(["automation_rule_id"], ["automation_rules.id"]),
            sa.ForeignKeyConstraint(["complaint_id"], ["complaints.id"]),
            sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        )
    _create_index_if_missing("ix_workflow_executions_client_id", "workflow_executions", ["client_id"])
    _create_index_if_missing("ix_workflow_executions_automation_rule_id", "workflow_executions", ["automation_rule_id"])
    _create_index_if_missing("ix_workflow_executions_complaint_id", "workflow_executions", ["complaint_id"])
    _create_index_if_missing("ix_workflow_executions_customer_id", "workflow_executions", ["customer_id"])
    _create_index_if_missing("ix_workflow_executions_execution_status", "workflow_executions", ["execution_status"])
    _create_index_if_missing("idx_workflow_executions_client_time", "workflow_executions", ["client_id", "executed_at"])
    _create_index_if_missing("idx_workflow_executions_rule_time", "workflow_executions", ["automation_rule_id", "executed_at"])
    _create_index_if_missing("idx_workflow_executions_complaint_time", "workflow_executions", ["complaint_id", "executed_at"])


def downgrade() -> None:
    tables = _tables()
    if "workflow_executions" in tables:
        op.drop_table("workflow_executions")
