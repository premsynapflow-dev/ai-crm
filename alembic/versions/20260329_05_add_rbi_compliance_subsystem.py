"""add rbi compliance subsystem

Revision ID: 20260329_05
Revises: 20260329_04
Create Date: 2026-03-29
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260329_05"
down_revision = "20260329_04"
branch_labels = None
depends_on = None


def _index_names(inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "rbi_complaint_categories" not in tables:
        op.create_table(
            "rbi_complaint_categories",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("category_code", sa.String(length=20), nullable=False),
            sa.Column("category_name", sa.String(length=100), nullable=False),
            sa.Column("subcategory_code", sa.String(length=20), nullable=True),
            sa.Column("subcategory_name", sa.String(length=100), nullable=True),
            sa.Column("tat_days", sa.Integer(), nullable=False, server_default=sa.text("30")),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
            sa.UniqueConstraint("category_code", "subcategory_code", name="unique_rbi_category_subcategory"),
        )
        op.create_index("ix_rbi_complaint_categories_category_code", "rbi_complaint_categories", ["category_code"])
        op.create_index("ix_rbi_complaint_categories_subcategory_code", "rbi_complaint_categories", ["subcategory_code"])

    if "rbi_complaints" not in tables:
        op.create_table(
            "rbi_complaints",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("complaint_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False),
            sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id"), nullable=False),
            sa.Column("rbi_category_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("rbi_complaint_categories.id"), nullable=True),
            sa.Column("category_code", sa.String(length=20), nullable=True),
            sa.Column("subcategory_code", sa.String(length=20), nullable=True),
            sa.Column("rbi_reference_number", sa.String(length=50), nullable=True, unique=True),
            sa.Column("escalation_level", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("escalated_to_rbi", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("rbi_escalation_date", sa.DateTime(timezone=True), nullable=True),
            sa.Column("tat_due_date", sa.DateTime(timezone=True), nullable=False),
            sa.Column("tat_status", sa.String(length=20), nullable=False, server_default=sa.text("'within_tat'")),
            sa.Column("tat_breach_hours", sa.Integer(), nullable=True),
            sa.Column("resolution_date", sa.DateTime(timezone=True), nullable=True),
            sa.Column("resolution_summary", sa.Text(), nullable=True),
            sa.Column("customer_satisfied", sa.Boolean(), nullable=True),
            sa.Column("audit_log", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
            sa.UniqueConstraint("complaint_id", name="unique_complaint_rbi"),
        )
        op.create_index("idx_rbi_complaints_client", "rbi_complaints", ["client_id", "created_at"])
        op.create_index(
            "idx_rbi_complaints_tat",
            "rbi_complaints",
            ["tat_due_date"],
            postgresql_where=sa.text("resolution_date IS NULL"),
        )
        op.create_index("idx_rbi_complaints_category", "rbi_complaints", ["category_code", "subcategory_code"])
        op.create_index("idx_rbi_reference", "rbi_complaints", ["rbi_reference_number"])

    if "rbi_escalation_log" not in tables:
        op.create_table(
            "rbi_escalation_log",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("rbi_complaint_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("rbi_complaints.id", ondelete="CASCADE"), nullable=False),
            sa.Column("from_level", sa.Integer(), nullable=False),
            sa.Column("to_level", sa.Integer(), nullable=False),
            sa.Column("escalation_reason", sa.Text(), nullable=False),
            sa.Column("escalated_by", sa.String(length=255), nullable=False),
            sa.Column("escalated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
            sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        )
        op.create_index("idx_escalation_log_complaint", "rbi_escalation_log", ["rbi_complaint_id", "escalated_at"])

    if "rbi_mis_reports" not in tables:
        op.create_table(
            "rbi_mis_reports",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id"), nullable=False),
            sa.Column("report_month", sa.Date(), nullable=False),
            sa.Column("total_complaints", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("complaints_by_category", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("resolved_within_tat", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("tat_breach_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("avg_resolution_days", sa.Float(), nullable=True),
            sa.Column("pending_complaints", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("escalated_to_regional", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("escalated_to_nodal", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("escalated_to_ombudsman", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("satisfaction_rate", sa.Float(), nullable=True),
            sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
            sa.Column("report_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.UniqueConstraint("client_id", "report_month", name="unique_client_month"),
        )
        op.create_index("idx_mis_reports_client_month", "rbi_mis_reports", ["client_id", "report_month"])

    op.execute(
        """
        INSERT INTO rbi_complaint_categories (category_code, category_name, subcategory_code, subcategory_name, tat_days)
        VALUES
            ('ATM', 'ATM / Debit Card', 'ATM_FAIL', 'Failed Transaction', 30),
            ('ATM', 'ATM / Debit Card', 'ATM_CASH', 'Cash Not Dispensed', 30),
            ('CC', 'Credit Card', 'CC_UNAUTHORIZED', 'Unauthorized Transaction', 30),
            ('CC', 'Credit Card', 'CC_BILLING', 'Billing Dispute', 30),
            ('LOAN', 'Loans', 'LOAN_DISBURSEMENT', 'Delayed Disbursement', 30),
            ('LOAN', 'Loans', 'LOAN_INTEREST', 'Interest Rate Issue', 30),
            ('DEP', 'Deposits', 'DEP_INTEREST', 'Interest Not Credited', 30),
            ('NB', 'Net Banking', 'NB_ACCESS', 'Login Issue', 30),
            ('NB', 'Net Banking', 'NB_TXN', 'Transaction Failure', 30),
            ('MOBILE', 'Mobile Banking', 'MOBILE_APP', 'App Not Working', 30),
            ('BRANCH', 'Branch Banking', 'BRANCH_SERVICE', 'Poor Service', 30),
            ('OTHER', 'Others', 'OTHER', 'Other Complaints', 30)
        ON CONFLICT (category_code, subcategory_code) DO NOTHING
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "rbi_mis_reports" in tables:
        indexes = _index_names(inspector, "rbi_mis_reports")
        if "idx_mis_reports_client_month" in indexes:
            op.drop_index("idx_mis_reports_client_month", table_name="rbi_mis_reports")
        op.drop_table("rbi_mis_reports")
    if "rbi_escalation_log" in tables:
        indexes = _index_names(inspector, "rbi_escalation_log")
        if "idx_escalation_log_complaint" in indexes:
            op.drop_index("idx_escalation_log_complaint", table_name="rbi_escalation_log")
        op.drop_table("rbi_escalation_log")
    if "rbi_complaints" in tables:
        indexes = _index_names(inspector, "rbi_complaints")
        for index_name in ["idx_rbi_reference", "idx_rbi_complaints_category", "idx_rbi_complaints_tat", "idx_rbi_complaints_client"]:
            if index_name in indexes:
                op.drop_index(index_name, table_name="rbi_complaints")
        op.drop_table("rbi_complaints")
    if "rbi_complaint_categories" in tables:
        indexes = _index_names(inspector, "rbi_complaint_categories")
        for index_name in ["ix_rbi_complaint_categories_subcategory_code", "ix_rbi_complaint_categories_category_code"]:
            if index_name in indexes:
                op.drop_index(index_name, table_name="rbi_complaint_categories")
        op.drop_table("rbi_complaint_categories")
