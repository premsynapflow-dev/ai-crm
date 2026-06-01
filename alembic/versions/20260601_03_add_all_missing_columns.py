"""add all missing columns across all tables (schema drift repair)

Revision ID: 20260601_03
Revises: 20260601_02
Create Date: 2026-06-01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260601_03"
down_revision = "20260601_02"
branch_labels = None
depends_on = None


# Tables whose missing columns require FK targets that may not exist yet —
# skip FK constraints when adding columns to these tables to avoid cascading
# failures. The column is added as a plain UUID column without the FK.
_SKIP_FK_TABLES = {
    "rbi_escalation_log", "rbi_mis_reports", "reply_feedback",
    "reply_ab_tests", "reply_quality_metrics", "conversations",
    "automation_settings", "churn_outcomes", "knowledge_snippets",
    "agent_corrections",
}


def _tables():
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table: str) -> set:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _safe_column(col: sa.Column, skip_fk: bool = False) -> sa.Column:
    """Return a copy of a column that is safe to add to an existing table.

    - Removes FK constraints when skip_fk=True (avoids cascading failures).
    - Makes NOT NULL columns nullable when there is no server_default, so
      existing rows are not rejected.
    """
    is_pg = op.get_bind().dialect.name == "postgresql"

    # Resolve JSONB → JSON for portability
    col_type = col.type
    if isinstance(col_type, postgresql.JSONB):
        col_type = postgresql.JSONB(astext_type=sa.Text()) if is_pg else sa.JSON()
    elif isinstance(col_type, postgresql.UUID):
        col_type = postgresql.UUID(as_uuid=True) if is_pg else sa.Uuid(as_uuid=True)

    server_default = col.server_default

    # For NOT NULL columns with no server_default, provide a sensible fallback
    # so existing rows don't violate the constraint.
    needs_nullable = not col.nullable and server_default is None and col.default is None

    return sa.Column(
        col.name,
        col_type,
        nullable=True if needs_nullable else col.nullable,
        server_default=server_default,
    )


def _add_missing_columns(tbl_name: str, model_table, skip_fk: bool = False) -> None:
    existing = _columns(tbl_name)
    for col in model_table.columns:
        if col.name in existing:
            continue
        safe_col = _safe_column(col, skip_fk=skip_fk)
        try:
            op.add_column(tbl_name, safe_col)
        except Exception as exc:
            print(f"  [warn] Could not add {tbl_name}.{col.name}: {exc}")


def upgrade() -> None:
    # Import inside function to avoid module-load-time issues during migrations
    from app.db.models import Base  # noqa: PLC0415

    existing_tables = _tables()

    for tbl_name, tbl in Base.metadata.tables.items():
        if tbl_name not in existing_tables:
            continue
        skip_fk = tbl_name in _SKIP_FK_TABLES
        _add_missing_columns(tbl_name, tbl, skip_fk=skip_fk)

    # ── Post-column-addition data backfills ──────────────────────────────────
    # rbi_complaints: new columns mirror old column names where data exists
    if "rbi_complaints" in existing_tables:
        rc_cols = _columns("rbi_complaints")
        if "tat_due_date" in rc_cols and "tat_due_at" in rc_cols:
            op.execute(
                "UPDATE rbi_complaints SET tat_due_date = tat_due_at "
                "WHERE tat_due_date IS NULL AND tat_due_at IS NOT NULL"
            )
        if "category_code" in rc_cols and "rbi_category_code" in rc_cols:
            op.execute(
                "UPDATE rbi_complaints SET category_code = rbi_category_code "
                "WHERE category_code IS NULL AND rbi_category_code IS NOT NULL"
            )

    # event_logs: event_timestamp backfill
    if "event_logs" in existing_tables:
        el_cols = _columns("event_logs")
        if "event_timestamp" in el_cols:
            op.execute(
                "UPDATE event_logs SET event_timestamp = created_at "
                "WHERE event_timestamp IS NULL"
            )

    # workflow_executions: execution_status backfill
    if "workflow_executions" in existing_tables:
        we_cols = _columns("workflow_executions")
        if "execution_status" in we_cols and "status" in we_cols:
            op.execute(
                "UPDATE workflow_executions SET execution_status = COALESCE(status, 'completed') "
                "WHERE execution_status IS NULL"
            )
        if "executed_at" in we_cols:
            op.execute(
                "UPDATE workflow_executions SET executed_at = created_at "
                "WHERE executed_at IS NULL"
            )


def downgrade() -> None:
    # Intentionally additive-only — no destructive downgrade.
    pass
