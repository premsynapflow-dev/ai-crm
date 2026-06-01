"""add password reset OTPs

Revision ID: 20260601_06
Revises: 20260601_05
Create Date: 2026-06-01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260601_06"
down_revision = "20260601_05"
branch_labels = None
depends_on = None


def _uuid():
    if op.get_bind().dialect.name == "postgresql":
        return postgresql.UUID(as_uuid=True)
    return sa.Uuid(as_uuid=True)


def upgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "password_reset_otps" in tables:
        return

    op.create_table(
        "password_reset_otps",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column("user_id", _uuid(), sa.ForeignKey("client_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("otp_hash", sa.String(128), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_password_reset_otps_user_id", "password_reset_otps", ["user_id"])
    op.create_index("ix_password_reset_otps_email", "password_reset_otps", ["email"])
    op.create_index(
        "idx_password_reset_otps_user_active",
        "password_reset_otps",
        ["user_id", "used_at", "expires_at"],
    )
    op.create_index("idx_password_reset_otps_expires_at", "password_reset_otps", ["expires_at"])


def downgrade() -> None:
    op.drop_table("password_reset_otps")
