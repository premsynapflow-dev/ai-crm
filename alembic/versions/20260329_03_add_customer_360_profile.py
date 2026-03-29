"""add customer 360 profile

Revision ID: 20260329_03
Revises: 20260329_02
Create Date: 2026-03-29
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260329_03"
down_revision = "20260329_02"
branch_labels = None
depends_on = None


def _column_names(inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "customers" not in tables:
        op.create_table(
            "customers",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
            sa.Column("primary_email", sa.String(length=255), nullable=True),
            sa.Column("primary_phone", sa.String(length=50), nullable=True),
            sa.Column("full_name", sa.String(length=255), nullable=True),
            sa.Column("company_name", sa.String(length=255), nullable=True),
            sa.Column("emails", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("phones", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("customer_type", sa.String(length=50), nullable=False, server_default=sa.text("'individual'")),
            sa.Column("status", sa.String(length=50), nullable=False, server_default=sa.text("'active'")),
            sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("total_tickets", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("total_interactions", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("first_interaction_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_interaction_at", sa.DateTime(timezone=True), nullable=True),
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
        )
        op.create_index("idx_customers_client", "customers", ["client_id"], postgresql_where=sa.text("is_master = true"))
        op.create_index("idx_customers_email", "customers", ["emails"], postgresql_using="gin", postgresql_where=sa.text("is_master = true"))
        op.create_index("idx_customers_phone", "customers", ["phones"], postgresql_using="gin", postgresql_where=sa.text("is_master = true"))
        op.create_index(
            "idx_customers_company",
            "customers",
            ["client_id", "company_name"],
            postgresql_where=sa.text("is_master = true AND company_name IS NOT NULL"),
        )
        op.create_index(
            "idx_customers_churn_risk",
            "customers",
            ["client_id", "churn_risk_score"],
            postgresql_where=sa.text("is_master = true"),
        )
        op.create_index("idx_customers_name", "customers", ["client_id", "full_name"], postgresql_where=sa.text("is_master = true"))

    if "complaints" in tables:
        complaint_columns = _column_names(inspector, "complaints")
        if "customer_id" not in complaint_columns:
            op.add_column(
                "complaints",
                sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id", ondelete="SET NULL"), nullable=True),
            )
        complaint_indexes = _index_names(inspector, "complaints")
        if "idx_complaints_customer" not in complaint_indexes:
            op.create_index("idx_complaints_customer", "complaints", ["customer_id"])

    if "customer_merge_history" not in tables:
        op.create_table(
            "customer_merge_history",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id"), nullable=False),
            sa.Column("master_customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=False),
            sa.Column("merged_customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=False),
            sa.Column("merge_reason", sa.Text(), nullable=True),
            sa.Column("confidence_score", sa.Float(), nullable=True),
            sa.Column("merged_by", sa.String(length=255), nullable=True),
            sa.Column("auto_merged", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("merge_strategy", sa.String(length=50), nullable=True),
            sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        )
        op.create_index("idx_merge_history_master", "customer_merge_history", ["master_customer_id"])
        op.create_index("idx_merge_history_merged", "customer_merge_history", ["merged_customer_id"])
        op.create_index("idx_merge_history_client", "customer_merge_history", ["client_id", "created_at"])

    if "customer_interactions" not in tables:
        op.create_table(
            "customer_interactions",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
            sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id"), nullable=False),
            sa.Column("interaction_type", sa.String(length=50), nullable=False),
            sa.Column("interaction_channel", sa.String(length=50), nullable=True),
            sa.Column("complaint_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("complaints.id", ondelete="SET NULL"), nullable=True),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("sentiment_score", sa.Float(), nullable=True),
            sa.Column("duration_seconds", sa.Integer(), nullable=True),
            sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        )
        op.create_index("idx_interactions_customer", "customer_interactions", ["customer_id", "created_at"])
        op.create_index("idx_interactions_client", "customer_interactions", ["client_id", "created_at"])

    if "customer_notes" not in tables:
        op.create_table(
            "customer_notes",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
            sa.Column("author_email", sa.String(length=255), nullable=False),
            sa.Column("note_type", sa.String(length=50), nullable=False, server_default=sa.text("'general'")),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("pinned", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        )
        op.create_index("idx_notes_customer", "customer_notes", ["customer_id", "created_at"])

    if "customer_relationships" not in tables:
        op.create_table(
            "customer_relationships",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id"), nullable=False),
            sa.Column("parent_customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
            sa.Column("child_customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
            sa.Column("relationship_type", sa.String(length=50), nullable=False),
            sa.Column("role_title", sa.String(length=100), nullable=True),
            sa.Column("is_primary_contact", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
            sa.UniqueConstraint("parent_customer_id", "child_customer_id", name="unique_parent_child"),
        )
        op.create_index("idx_relationships_parent", "customer_relationships", ["parent_customer_id"])
        op.create_index("idx_relationships_child", "customer_relationships", ["child_customer_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "customer_relationships" in tables:
        op.drop_index("idx_relationships_child", table_name="customer_relationships")
        op.drop_index("idx_relationships_parent", table_name="customer_relationships")
        op.drop_table("customer_relationships")

    if "customer_notes" in tables:
        op.drop_index("idx_notes_customer", table_name="customer_notes")
        op.drop_table("customer_notes")

    if "customer_interactions" in tables:
        op.drop_index("idx_interactions_client", table_name="customer_interactions")
        op.drop_index("idx_interactions_customer", table_name="customer_interactions")
        op.drop_table("customer_interactions")

    if "customer_merge_history" in tables:
        op.drop_index("idx_merge_history_client", table_name="customer_merge_history")
        op.drop_index("idx_merge_history_merged", table_name="customer_merge_history")
        op.drop_index("idx_merge_history_master", table_name="customer_merge_history")
        op.drop_table("customer_merge_history")

    if "complaints" in tables:
        complaint_indexes = _index_names(inspector, "complaints")
        if "idx_complaints_customer" in complaint_indexes:
            op.drop_index("idx_complaints_customer", table_name="complaints")
        complaint_columns = _column_names(inspector, "complaints")
        if "customer_id" in complaint_columns:
            op.drop_column("complaints", "customer_id")

    if "customers" in tables:
        op.drop_index("idx_customers_name", table_name="customers")
        op.drop_index("idx_customers_churn_risk", table_name="customers")
        op.drop_index("idx_customers_company", table_name="customers")
        op.drop_index("idx_customers_phone", table_name="customers")
        op.drop_index("idx_customers_email", table_name="customers")
        op.drop_index("idx_customers_client", table_name="customers")
        op.drop_table("customers")
