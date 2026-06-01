"""create remaining missing tables

Revision ID: 20260601_04
Revises: 20260601_03
Create Date: 2026-06-01
"""

from alembic import op
import sqlalchemy as sa


revision = "20260601_04"
down_revision = "20260601_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.db.models import Base  # noqa: PLC0415
    from app.inboxes.models import Inbox  # noqa: PLC0415, F401 (registers table with Base)

    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    missing_names = [
        "request_audits",
        "materialized_analytics",
        "reply_cache",
        "monitoring_metrics",
        "waitlist_entries",
        "demo_requests",
        "inboxes",
    ]
    tables = [Base.metadata.tables[n] for n in missing_names if n in Base.metadata.tables]
    for tbl in tables:
        if tbl.name not in existing:
            tbl.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    pass
