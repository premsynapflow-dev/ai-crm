"""Revenue at Risk engine redesign — add three-tier value source columns.

Revision ID: 20260605_01
Revises: 20260603_05
Create Date: 2026-06-05
"""

import sqlalchemy as sa
from alembic import op

revision = "20260605_01"
down_revision = "20260603_05"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return set(inspector.get_table_names())


def _columns(table: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    if "customers" not in _tables():
        return

    existing = _columns("customers")

    new_cols = [
        ("customer_value_source", sa.String(20), "unknown"),
        ("actual_customer_value", sa.Float, None),
        ("estimated_customer_value", sa.Float, None),
        ("predicted_churn_probability", sa.Float, None),
        ("revenue_risk_confidence", sa.String(10), "low"),
        ("tenure_days", sa.Integer, None),
        ("complaint_velocity_score", sa.Float, None),
        ("competitive_mention_count", sa.Integer, 0),
    ]

    for col_name, col_type, default in new_cols:
        if col_name in existing:
            continue
        nullable = default is None
        if nullable:
            op.add_column("customers", sa.Column(col_name, col_type, nullable=True))
        else:
            op.add_column(
                "customers",
                sa.Column(col_name, col_type, nullable=False, server_default=str(default)),
            )


def downgrade() -> None:
    cols_to_drop = [
        "customer_value_source",
        "actual_customer_value",
        "estimated_customer_value",
        "predicted_churn_probability",
        "revenue_risk_confidence",
        "tenure_days",
        "complaint_velocity_score",
        "competitive_mention_count",
    ]
    existing = _columns("customers")
    for col in cols_to_drop:
        if col in existing:
            op.drop_column("customers", col)
