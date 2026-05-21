"""add async workflow execution reliability fields

Revision ID: 20260522_03
Revises: 20260522_02
Create Date: 2026-05-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260522_03"
down_revision = "20260522_02"
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


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if column.name not in _columns(table_name):
        op.add_column(table_name, column)


def _create_index_if_missing(name: str, table_name: str, columns: list[str], **kwargs) -> None:
    if name not in _indexes(table_name):
        op.create_index(name, table_name, columns, **kwargs)


def upgrade() -> None:
    tables = _tables()
    uuid_type = _uuid_type()
    if "workflow_executions" in tables:
        _add_column_if_missing("workflow_executions", sa.Column("trigger_event_id", uuid_type, nullable=True))
        _add_column_if_missing("workflow_executions", sa.Column("job_id", uuid_type, nullable=True))
        _add_column_if_missing("workflow_executions", sa.Column("idempotency_key", sa.String(length=255), nullable=True))
        _add_column_if_missing("workflow_executions", sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"))
        _add_column_if_missing("workflow_executions", sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"))
        _add_column_if_missing("workflow_executions", sa.Column("error_json", _json_type(), nullable=False, server_default=_empty_json_default()))
        _add_column_if_missing("workflow_executions", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
        _add_column_if_missing("workflow_executions", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
        _add_column_if_missing("workflow_executions", sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True))
        _add_column_if_missing("workflow_executions", sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))

        if op.get_bind().dialect.name == "postgresql":
            op.execute(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conname = 'fk_workflow_executions_trigger_event_id'
                    ) THEN
                        ALTER TABLE workflow_executions
                        ADD CONSTRAINT fk_workflow_executions_trigger_event_id
                        FOREIGN KEY (trigger_event_id) REFERENCES customer_events(id);
                    END IF;
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conname = 'fk_workflow_executions_job_id'
                    ) THEN
                        ALTER TABLE workflow_executions
                        ADD CONSTRAINT fk_workflow_executions_job_id
                        FOREIGN KEY (job_id) REFERENCES job_queue(id);
                    END IF;
                END $$;
                """
            )

        _create_index_if_missing("ix_workflow_executions_trigger_event_id", "workflow_executions", ["trigger_event_id"])
        _create_index_if_missing("ix_workflow_executions_job_id", "workflow_executions", ["job_id"])
        _create_index_if_missing("ix_workflow_executions_idempotency_key", "workflow_executions", ["idempotency_key"])
        _create_index_if_missing("idx_workflow_executions_status_created", "workflow_executions", ["execution_status", "created_at"])
        _create_index_if_missing("idx_workflow_executions_idempotency", "workflow_executions", ["idempotency_key"], unique=True)

    if "job_queue" in tables:
        _create_index_if_missing("idx_job_queue_status_scheduled", "job_queue", ["status", "scheduled_for", "created_at"])


def downgrade() -> None:
    # Intentionally no destructive downgrade: these additive fields are safe to leave in place.
    pass
