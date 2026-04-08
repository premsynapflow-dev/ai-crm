"""unify inbox email ingestion

Revision ID: 20260408_01
Revises: 20260401_02
Create Date: 2026-04-08
"""

from alembic import op
import sqlalchemy as sa


revision = "20260408_01"
down_revision = "20260401_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "inboxes" not in set(inspector.get_table_names()):
        return

    columns = {column["name"] for column in inspector.get_columns("inboxes")}
    if "metadata" not in columns:
        op.add_column(
            "inboxes",
            sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        )
    if "imap_use_ssl" not in columns:
        op.add_column(
            "inboxes",
            sa.Column("imap_use_ssl", sa.Boolean(), nullable=False, server_default=sa.true()),
        )
    if "last_synced_at" not in columns:
        op.add_column("inboxes", sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "inboxes" not in set(inspector.get_table_names()):
        return

    columns = {column["name"] for column in inspector.get_columns("inboxes")}
    if "last_synced_at" in columns:
        op.drop_column("inboxes", "last_synced_at")
    if "imap_use_ssl" in columns:
        op.drop_column("inboxes", "imap_use_ssl")
    if "metadata" in columns:
        op.drop_column("inboxes", "metadata")
