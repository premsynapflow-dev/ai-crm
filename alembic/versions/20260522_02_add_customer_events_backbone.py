"""add canonical customer events backbone

Revision ID: 20260522_02
Revises: 20260522_01
Create Date: 2026-05-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260522_02"
down_revision = "20260522_01"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


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


def _uuid_default():
    if op.get_bind().dialect.name == "postgresql":
        return sa.text("gen_random_uuid()")
    return None


def _create_index_if_missing(name: str, table_name: str, columns: list[str], **kwargs) -> None:
    if name not in _indexes(table_name):
        op.create_index(name, table_name, columns, **kwargs)


def upgrade() -> None:
    bind = op.get_bind()
    tables = _tables()
    uuid_type = _uuid_type()

    if "customer_events" not in tables:
        op.create_table(
            "customer_events",
            sa.Column("id", uuid_type, primary_key=True, nullable=False, server_default=_uuid_default()),
            sa.Column("client_id", uuid_type, sa.ForeignKey("clients.id"), nullable=False),
            sa.Column("customer_id", uuid_type, sa.ForeignKey("customers.id"), nullable=True),
            sa.Column("conversation_id", uuid_type, sa.ForeignKey("conversations.id"), nullable=True),
            sa.Column("message_id", uuid_type, sa.ForeignKey("unified_messages.id"), nullable=True),
            sa.Column(
                "workflow_execution_id",
                uuid_type,
                sa.ForeignKey("workflow_executions.id", use_alter=True, name="fk_customer_events_workflow_execution_id"),
                nullable=True,
            ),
            sa.Column("complaint_id", uuid_type, sa.ForeignKey("complaints.id"), nullable=True),
            sa.Column("source", sa.String(length=50), nullable=False),
            sa.Column("source_event_id", uuid_type, nullable=True),
            sa.Column("event_type", sa.String(length=100), nullable=False),
            sa.Column("actor_type", sa.String(length=50), nullable=False, server_default="system"),
            sa.Column("actor_id", sa.String(length=255), nullable=True),
            sa.Column("event_timestamp", sa.DateTime(timezone=True), nullable=False),
            sa.Column("metadata", _json_type(), nullable=False, server_default=_empty_json_default()),
            sa.Column("sentiment_score", sa.Float(), nullable=True),
            sa.Column("risk_delta", sa.Float(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    _create_index_if_missing("ix_customer_events_client_id", "customer_events", ["client_id"])
    _create_index_if_missing("ix_customer_events_customer_id", "customer_events", ["customer_id"])
    _create_index_if_missing("ix_customer_events_conversation_id", "customer_events", ["conversation_id"])
    _create_index_if_missing("ix_customer_events_message_id", "customer_events", ["message_id"])
    _create_index_if_missing("ix_customer_events_workflow_execution_id", "customer_events", ["workflow_execution_id"])
    _create_index_if_missing("ix_customer_events_complaint_id", "customer_events", ["complaint_id"])
    _create_index_if_missing("ix_customer_events_event_type", "customer_events", ["event_type"])
    _create_index_if_missing("ix_customer_events_event_timestamp", "customer_events", ["event_timestamp"])
    _create_index_if_missing("idx_customer_events_tenant_time", "customer_events", ["client_id", "event_timestamp"])
    _create_index_if_missing("idx_customer_events_customer_time", "customer_events", ["customer_id", "event_timestamp"])
    _create_index_if_missing("idx_customer_events_conversation_time", "customer_events", ["conversation_id", "event_timestamp"])
    _create_index_if_missing("idx_customer_events_message_time", "customer_events", ["message_id", "event_timestamp"])
    _create_index_if_missing("idx_customer_events_workflow_time", "customer_events", ["workflow_execution_id", "event_timestamp"])
    _create_index_if_missing("idx_customer_events_type_time", "customer_events", ["client_id", "event_type", "event_timestamp"])
    _create_index_if_missing("idx_customer_events_source_event", "customer_events", ["source_event_id"])

    if bind.dialect.name == "postgresql":
        op.execute(
            """
            ALTER TABLE customer_events ENABLE ROW LEVEL SECURITY;
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_policies
                    WHERE schemaname = current_schema()
                      AND tablename = 'customer_events'
                      AND policyname = 'customer_events_tenant_isolation_policy'
                ) THEN
                    CREATE POLICY customer_events_tenant_isolation_policy ON customer_events
                        FOR ALL
                        USING (client_id::text = current_setting('app.current_client_id', true))
                        WITH CHECK (client_id::text = current_setting('app.current_client_id', true));
                END IF;
            END $$;
            """
        )
        op.execute(
            """
            CREATE OR REPLACE FUNCTION prevent_customer_events_mutation()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'customer_events is append-only';
            END;
            $$ LANGUAGE plpgsql;

            DROP TRIGGER IF EXISTS customer_events_no_update ON customer_events;
            CREATE TRIGGER customer_events_no_update
                BEFORE UPDATE OR DELETE ON customer_events
                FOR EACH ROW EXECUTE FUNCTION prevent_customer_events_mutation();
            """
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS customer_events_no_update ON customer_events")
        op.execute("DROP FUNCTION IF EXISTS prevent_customer_events_mutation()")
        op.execute("DROP POLICY IF EXISTS customer_events_tenant_isolation_policy ON customer_events")
    if "customer_events" in _tables():
        op.drop_table("customer_events")
