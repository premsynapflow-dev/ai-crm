"""add customer intelligence identity layer

Revision ID: 20260412_01
Revises: 20260410_01
Create Date: 2026-04-12
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260412_01"
down_revision = "20260410_01"
branch_labels = None
depends_on = None


def _column_names(inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _unique_constraint_names(inspector, table_name: str) -> set[str]:
    return {constraint["name"] for constraint in inspector.get_unique_constraints(table_name)}


def _create_customers_table() -> None:
    op.create_table(
        "customers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("primary_email", sa.String(length=255), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("primary_phone", sa.String(length=50), nullable=True),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("company_name", sa.String(length=255), nullable=True),
        sa.Column("emails", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("merged_emails", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("phones", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("customer_type", sa.String(length=50), nullable=False, server_default=sa.text("'individual'")),
        sa.Column("status", sa.String(length=50), nullable=False, server_default=sa.text("'active'")),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("total_messages", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_tickets", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("open_tickets", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_interactions", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("first_interaction_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_interaction_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_contacted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("avg_response_time", sa.Float(), nullable=True),
        sa.Column("sentiment_score", sa.Float(), nullable=True),
        sa.Column("sentiment_label", sa.String(length=50), nullable=True),
        sa.Column("churn_risk", sa.String(length=20), nullable=False, server_default=sa.text("'low'")),
        sa.Column("avg_satisfaction_score", sa.Float(), nullable=True),
        sa.Column("churn_risk_score", sa.Float(), nullable=False, server_default=sa.text("0.0")),
        sa.Column("lifetime_value", sa.Float(), nullable=False, server_default=sa.text("0.0")),
        sa.Column("enrichment_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("custom_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_master", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("merged_into", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default=sa.text("1.0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("client_id", "primary_email", name="uq_customers_client_primary_email"),
    )
    op.create_index("idx_customers_client", "customers", ["client_id"], postgresql_where=sa.text("is_master = true"))
    op.create_index("idx_customers_company", "customers", ["client_id", "company_name"])
    op.create_index("idx_customers_churn_risk", "customers", ["client_id", "churn_risk_score"])
    op.create_index("idx_customers_name", "customers", ["client_id", "full_name"])


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "customers" not in tables:
        _create_customers_table()
        inspector = sa.inspect(bind)
        tables = set(inspector.get_table_names())

    customer_columns = _column_names(inspector, "customers")
    customer_indexes = _index_names(inspector, "customers")
    customer_constraints = _unique_constraint_names(inspector, "customers")

    if "name" not in customer_columns:
        op.add_column("customers", sa.Column("name", sa.String(length=255), nullable=True))
    if "merged_emails" not in customer_columns:
        op.add_column(
            "customers",
            sa.Column("merged_emails", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        )
    if "notes" not in customer_columns:
        op.add_column("customers", sa.Column("notes", sa.Text(), nullable=True))
    if "total_messages" not in customer_columns:
        op.add_column("customers", sa.Column("total_messages", sa.Integer(), nullable=False, server_default=sa.text("0")))
    if "open_tickets" not in customer_columns:
        op.add_column("customers", sa.Column("open_tickets", sa.Integer(), nullable=False, server_default=sa.text("0")))
    if "last_contacted_at" not in customer_columns:
        op.add_column("customers", sa.Column("last_contacted_at", sa.DateTime(timezone=True), nullable=True))
    if "avg_response_time" not in customer_columns:
        op.add_column("customers", sa.Column("avg_response_time", sa.Float(), nullable=True))
    if "sentiment_score" not in customer_columns:
        op.add_column("customers", sa.Column("sentiment_score", sa.Float(), nullable=True))
    if "sentiment_label" not in customer_columns:
        op.add_column("customers", sa.Column("sentiment_label", sa.String(length=50), nullable=True))
    if "churn_risk" not in customer_columns:
        op.add_column(
            "customers",
            sa.Column("churn_risk", sa.String(length=20), nullable=False, server_default=sa.text("'low'")),
        )

    op.execute("UPDATE customers SET primary_email = LOWER(BTRIM(primary_email)) WHERE primary_email IS NOT NULL")
    op.execute("UPDATE customers SET name = COALESCE(name, full_name) WHERE name IS NULL AND full_name IS NOT NULL")
    op.execute(
        """
        UPDATE customers
        SET merged_emails = COALESCE(
            (
                SELECT jsonb_agg(value)
                FROM (
                    SELECT DISTINCT value
                    FROM jsonb_array_elements_text(COALESCE(emails, '[]'::jsonb)) AS value
                    WHERE value IS NOT NULL
                      AND BTRIM(value) <> ''
                      AND LOWER(BTRIM(value)) <> LOWER(COALESCE(primary_email, ''))
                ) deduped
            ),
            '[]'::jsonb
        )
        WHERE merged_emails IS NULL OR merged_emails = '[]'::jsonb
        """
    )
    op.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY client_id, primary_email
                    ORDER BY CASE WHEN is_master THEN 0 ELSE 1 END, created_at ASC, id ASC
                ) AS rn
            FROM customers
            WHERE primary_email IS NOT NULL AND BTRIM(primary_email) <> ''
        )
        UPDATE customers
        SET primary_email = NULL
        WHERE id IN (SELECT id FROM ranked WHERE rn > 1)
        """
    )

    if "uq_customers_client_primary_email" not in customer_constraints:
        op.create_unique_constraint("uq_customers_client_primary_email", "customers", ["client_id", "primary_email"])
    if "idx_customers_client" not in customer_indexes:
        op.create_index("idx_customers_client", "customers", ["client_id"], postgresql_where=sa.text("is_master = true"))
    if "idx_customers_company" not in customer_indexes:
        op.create_index("idx_customers_company", "customers", ["client_id", "company_name"])
    if "idx_customers_churn_risk" not in customer_indexes:
        op.create_index("idx_customers_churn_risk", "customers", ["client_id", "churn_risk_score"])
    if "idx_customers_name" not in customer_indexes:
        op.create_index("idx_customers_name", "customers", ["client_id", "full_name"])

    if "complaints" in tables:
        complaint_columns = _column_names(inspector, "complaints")
        complaint_indexes = _index_names(inspector, "complaints")
        if "customer_id" not in complaint_columns:
            op.add_column(
                "complaints",
                sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id", ondelete="SET NULL"), nullable=True),
            )
        if "idx_complaints_customer" not in complaint_indexes:
            op.create_index("idx_complaints_customer", "complaints", ["customer_id"])

    if "unified_messages" in tables:
        message_columns = _column_names(inspector, "unified_messages")
        message_indexes = _index_names(inspector, "unified_messages")
        if "customer_id" not in message_columns:
            op.add_column(
                "unified_messages",
                sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id", ondelete="SET NULL"), nullable=True),
            )
        if "idx_unified_messages_customer" not in message_indexes:
            op.create_index("idx_unified_messages_customer", "unified_messages", ["customer_id"])
        op.execute(
            """
            UPDATE unified_messages AS message
            SET customer_id = complaint.customer_id
            FROM complaints AS complaint
            WHERE message.customer_id IS NULL
              AND complaint.customer_id IS NOT NULL
              AND message.raw_payload ->> 'complaint_id' = complaint.id::text
            """
        )

    op.execute(
        """
        UPDATE customers AS customer
        SET total_tickets = COALESCE(ticket_counts.total_tickets, 0),
            open_tickets = COALESCE(ticket_counts.open_tickets, 0)
        FROM (
            SELECT
                customer_id,
                COUNT(*) AS total_tickets,
                COUNT(*) FILTER (WHERE resolution_status <> 'resolved') AS open_tickets
            FROM complaints
            WHERE customer_id IS NOT NULL
            GROUP BY customer_id
        ) AS ticket_counts
        WHERE customer.id = ticket_counts.customer_id
        """
    )
    op.execute(
        """
        UPDATE customers AS customer
        SET total_messages = COALESCE(message_counts.total_messages, 0),
            last_contacted_at = message_counts.last_contacted_at
        FROM (
            SELECT
                customer_id,
                COUNT(*) AS total_messages,
                MAX(COALESCE(timestamp, created_at)) AS last_contacted_at
            FROM unified_messages
            WHERE customer_id IS NOT NULL
            GROUP BY customer_id
        ) AS message_counts
        WHERE customer.id = message_counts.customer_id
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "unified_messages" in tables:
        message_indexes = _index_names(inspector, "unified_messages")
        message_columns = _column_names(inspector, "unified_messages")
        if "idx_unified_messages_customer" in message_indexes:
            op.drop_index("idx_unified_messages_customer", table_name="unified_messages")
        if "customer_id" in message_columns:
            op.drop_column("unified_messages", "customer_id")

    if "customers" in tables:
        customer_constraints = _unique_constraint_names(inspector, "customers")
        customer_columns = _column_names(inspector, "customers")
        if "uq_customers_client_primary_email" in customer_constraints:
            op.drop_constraint("uq_customers_client_primary_email", "customers", type_="unique")
        for column_name in [
            "churn_risk",
            "sentiment_label",
            "sentiment_score",
            "avg_response_time",
            "last_contacted_at",
            "open_tickets",
            "total_messages",
            "notes",
            "merged_emails",
            "name",
        ]:
            if column_name in customer_columns:
                op.drop_column("customers", column_name)
