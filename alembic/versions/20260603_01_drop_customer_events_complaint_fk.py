"""Drop FK from customer_events.complaint_id — table is append-only, FK blocks complaint deletion.

Revision ID: 20260603_01
Revises: 20260602_02
Create Date: 2026-06-03
"""

from alembic import op

revision = "20260603_01"
down_revision = "20260602_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "customer_events_complaint_id_fkey",
        "customer_events",
        type_="foreignkey",
    )


def downgrade() -> None:
    op.create_foreign_key(
        "customer_events_complaint_id_fkey",
        "customer_events",
        "complaints",
        ["complaint_id"],
        ["id"],
    )
