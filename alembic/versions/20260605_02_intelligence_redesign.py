"""Intelligence layer redesign: new revenue fields, model versioning, accuracy log, benchmarking schema.

Revision ID: 20260605_02
Revises: 20260605_01
Create Date: 2026-06-05

Changes:
  Customer table — new revenue intelligence + model versioning columns
  New table: forecast_accuracy_log
  New table: benchmark_contribution_log (schema only, no data collected yet)
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260605_02"
down_revision = "20260605_01"
branch_labels = None
depends_on = None


def _columns(table_name: str) -> set[str]:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return {c["name"] for c in insp.get_columns(table_name)}


def _tables() -> set[str]:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return set(insp.get_table_names())


def upgrade() -> None:
    existing = _columns("customers")

    # Extended revenue intelligence columns
    if "annual_contract_value" not in existing:
        op.add_column("customers", sa.Column("annual_contract_value", sa.Float(), nullable=True))
    if "monthly_recurring_value" not in existing:
        op.add_column("customers", sa.Column("monthly_recurring_value", sa.Float(), nullable=True))
    if "remaining_contract_value" not in existing:
        op.add_column("customers", sa.Column("remaining_contract_value", sa.Float(), nullable=True))
    if "customer_lifetime_revenue" not in existing:
        op.add_column("customers", sa.Column("customer_lifetime_revenue", sa.Float(), nullable=True))

    # Industry awareness
    if "industry_profile" not in existing:
        op.add_column("customers", sa.Column("industry_profile", sa.String(30), nullable=True))

    # Model versioning
    if "risk_score_version" not in existing:
        op.add_column(
            "customers",
            sa.Column("risk_score_version", sa.String(20), nullable=False, server_default="v1"),
        )
    if "risk_score_computed_at" not in existing:
        op.add_column("customers", sa.Column("risk_score_computed_at", sa.DateTime(timezone=True), nullable=True))
    if "prediction_explanation" not in existing:
        op.add_column("customers", sa.Column("prediction_explanation", sa.JSON(), nullable=True))

    # Forecast accuracy log
    all_tables = _tables()
    if "forecast_accuracy_log" not in all_tables:
        op.create_table(
            "forecast_accuracy_log",
            sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
            sa.Column("client_id", sa.UUID(as_uuid=True), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
            sa.Column("forecast_date", sa.DateTime(timezone=True), nullable=False),
            sa.Column("target_date", sa.DateTime(timezone=True), nullable=False),
            sa.Column("predicted_count", sa.Float(), nullable=False),
            sa.Column("actual_count", sa.Integer(), nullable=True),
            sa.Column("absolute_error", sa.Float(), nullable=True),
            sa.Column("pct_error", sa.Float(), nullable=True),
            sa.Column("forecast_params", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("client_id", "forecast_date", "target_date", name="uq_fal_client_forecast_target"),
        )
        op.create_index("idx_fal_client_target", "forecast_accuracy_log", ["client_id", "target_date"])

    # Benchmarking schema (empty, opt-in only)
    if "benchmark_contribution_log" not in all_tables:
        op.create_table(
            "benchmark_contribution_log",
            sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
            sa.Column("contributed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("industry", sa.String(30), nullable=False),
            sa.Column("ticket_volume_bucket", sa.String(10), nullable=True),
            sa.Column("resolution_rate_bucket", sa.String(10), nullable=True),
            sa.Column("response_time_bucket", sa.String(10), nullable=True),
            sa.Column("churn_rate_bucket", sa.String(10), nullable=True),
        )
        op.create_index("idx_bcl_industry_contributed", "benchmark_contribution_log", ["industry", "contributed_at"])


def downgrade() -> None:
    # Drop new tables
    for table in ("benchmark_contribution_log", "forecast_accuracy_log"):
        if table in _tables():
            op.drop_table(table)

    # Remove new customer columns (only if they exist)
    existing = _columns("customers")
    for col in (
        "prediction_explanation",
        "risk_score_computed_at",
        "risk_score_version",
        "industry_profile",
        "customer_lifetime_revenue",
        "remaining_contract_value",
        "monthly_recurring_value",
        "annual_contract_value",
    ):
        if col in existing:
            op.drop_column("customers", col)
