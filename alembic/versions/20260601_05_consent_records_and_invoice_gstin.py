"""add consent_records table and GSTIN/GST columns to invoices

Revision ID: 20260601_05
Revises: 20260601_04
Create Date: 2026-06-01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260601_05"
down_revision = "20260601_04"
branch_labels = None
depends_on = None


def _tables():
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table: str) -> set:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _uuid():
    if op.get_bind().dialect.name == "postgresql":
        return postgresql.UUID(as_uuid=True)
    return sa.Uuid(as_uuid=True)


def upgrade() -> None:
    tables = _tables()

    # ── consent_records (DPDP §6, GDPR Art. 7) ──────────────────────────────
    if "consent_records" not in tables:
        inet_type = sa.Text()  # Use Text as a portable fallback; cast to INET on PG
        op.create_table(
            "consent_records",
            sa.Column("id", _uuid(), primary_key=True),
            sa.Column("user_id", _uuid(), nullable=True, index=True),
            sa.Column("client_id", _uuid(), sa.ForeignKey("clients.id"), nullable=True, index=True),
            sa.Column("consent_type", sa.String(100), nullable=False),
            sa.Column("version", sa.String(20), nullable=False),
            sa.Column("granted", sa.Boolean(), nullable=False),
            sa.Column("ip_address", sa.String(45), nullable=True),
            sa.Column("user_agent", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.execute("CREATE INDEX IF NOT EXISTS ix_consent_records_consent_type ON consent_records (consent_type)")

    # ── invoices: add GSTIN / GST / SAC fields ────────────────────────────────
    if "invoices" in tables:
        invoice_cols = _columns("invoices")
        if "gstin" not in invoice_cols:
            op.add_column("invoices", sa.Column("gstin", sa.String(15), nullable=True))
        if "gst_rate" not in invoice_cols:
            op.add_column("invoices", sa.Column("gst_rate", sa.Float(), nullable=False, server_default="18.0"))
        if "gst_amount" not in invoice_cols:
            op.add_column("invoices", sa.Column("gst_amount", sa.Integer(), nullable=False, server_default="0"))
        if "sac_code" not in invoice_cols:
            op.add_column("invoices", sa.Column("sac_code", sa.String(10), nullable=False, server_default="998314"))
        if "invoice_date" not in invoice_cols:
            op.add_column("invoices", sa.Column("invoice_date", sa.DateTime(timezone=True), nullable=True))
        if "client_gstin" not in invoice_cols:
            op.add_column("invoices", sa.Column("client_gstin", sa.String(15), nullable=True))

    # ── clients: add gstin field ──────────────────────────────────────────────
    if "clients" in tables:
        client_cols = _columns("clients")
        if "gstin" not in client_cols:
            op.add_column("clients", sa.Column("gstin", sa.String(15), nullable=True))


def downgrade() -> None:
    pass
