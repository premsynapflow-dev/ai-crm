"""
Schema Guard - Ensures database schema is initialized
Fixed version with proper transaction handling
"""

import logging

from sqlalchemy import text
from sqlalchemy.sql.sqltypes import Boolean, DateTime, Float, Integer

from app.db.session import SessionLocal
from app.db.models import AIReplyQueue, Client, Complaint, Customer, CustomerInteraction, EventLog

logger = logging.getLogger(__name__)

REQUIRED_TABLES = [
    "clients",
    "complaints",
    "event_logs",
    "sla_policies",
    "business_hours",
    "ticket_state_transitions",
    "escalation_rules",
    "ticket_comments",
    "ticket_assignments",
    "teams",
    "team_members",
    "routing_rules",
    "customers",
    "customer_merge_history",
    "customer_interactions",
    "customer_notes",
    "customer_relationships",
    "reply_templates",
    "reply_drafts",
    "ai_reply_queue",
    "reply_feedback",
    "reply_ab_tests",
    "reply_quality_metrics",
    "rbi_categories",
    "rbi_complaint_categories",
    "rbi_complaints",
    "rbi_escalation_log",
    "rbi_mis_reports",
    "escalations",
    "audit_logs",
    "plan_features",
    "tenant_usage_tracking",
    "channel_connections",
    "unified_messages",
    "conversations",
    "automation_settings",
    "message_events",
]


def ensure_schema():
    """
    Ensure all tables and seed data exist.
    Uses separate transactions for each operation to prevent cascading failures.
    """
    try:
        logger.info("Schema guard: Checking database schema...")

        missing_tables = _find_missing_tables()
        if missing_tables:
            logger.warning(
                "Schema guard: Missing tables detected: %s. Please run 'alembic upgrade head' to create them.",
                ", ".join(missing_tables),
            )
            return

        logger.info("Schema guard: All required tables exist")

        _ensure_required_columns()
        _seed_rbi_categories()
        _seed_plan_features()
        _create_indexes()

        logger.info("Schema guard: Database schema check complete")
    except Exception as exc:
        logger.exception("Schema guard failed: %s", exc)
        # Don't raise - let the app start anyway


def _find_missing_tables() -> list[str]:
    query = text(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = current_schema()
              AND table_name = :table_name
        )
        """
    )

    missing_tables: list[str] = []
    with SessionLocal() as db:
        for table_name in REQUIRED_TABLES:
            exists = db.execute(query, {"table_name": table_name}).scalar()
            if not exists:
                missing_tables.append(table_name)

    return missing_tables


def _format_server_default(default_arg) -> str | None:
    if default_arg is None:
        return None
    if hasattr(default_arg, "compile"):
        return str(default_arg.compile(compile_kwargs={"literal_binds": True}))
    return str(default_arg)


def _format_python_default(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return f"'{value}'"
    return None


def _column_definition(column, dialect) -> str:
    parts = [f"ADD COLUMN {column.name} {column.type.compile(dialect=dialect)}"]

    default_sql = None
    if column.server_default is not None:
        default_sql = _format_server_default(getattr(column.server_default, "arg", None))
    elif column.default is not None and getattr(column.default, "is_scalar", False):
        default_sql = _format_python_default(column.default.arg)

    if default_sql:
        parts.append(f"DEFAULT {default_sql}")

    should_be_nullable = column.nullable or default_sql is None
    if not should_be_nullable:
        parts.append("NOT NULL")

    return " ".join(parts)


def _sync_missing_model_columns(table_name: str, model, critical_columns: list[str], extra_sql: list[str] | None = None) -> list[str]:
    with SessionLocal() as db:
        existing_columns = {
            row[0]
            for row in db.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = current_schema()
                      AND table_name = :table_name
                    """
                ),
                {"table_name": table_name},
            ).all()
        }

        model_columns = {column.name: column for column in model.__table__.columns}
        added_columns: list[str] = []
        dialect = db.get_bind().dialect

        for column_name in critical_columns:
            if column_name in existing_columns:
                continue
            column = model_columns.get(column_name)
            if column is None:
                continue
            alter_sql = f"ALTER TABLE {table_name} {_column_definition(column, dialect)}"
            db.execute(text(alter_sql))
            added_columns.append(column_name)

        for statement in extra_sql or []:
            db.execute(text(statement))

        if added_columns:
            db.commit()
        else:
            db.rollback()

        return added_columns


def _ensure_required_columns():
    """
    Add critical columns that may be missing on older deployed schemas.

    We intentionally add missing columns in an additive way so older databases
    can keep serving traffic without waiting for a separate migration step.
    """

    try:
        added_summary: dict[str, list[str]] = {}

        complaint_columns = [
                "customer_id",
                "sentiment_score",
                "sentiment_label",
                "sentiment_indicators",
                "assigned_to",
                "team_id",
                "assigned_user_id",
                "state",
                "state_changed_at",
                "ticket_number",
                "reopened_count",
                "last_reopened_at",
                "sla_due_at",
                "sla_status",
                "escalation_level",
                "escalated_at",
                "escalated_to",
                "rbi_category_code",
                "tat_due_at",
                "tat_status",
                "tat_breached_at",
                "response_time_seconds",
                "first_response_at",
                "resolved_at",
                "customer_satisfaction_score",
                "satisfaction_score",
                "ai_reply_confidence",
                "ai_reply_status",
                "ai_reply_sent_at",
                "last_replied_at",
            ]
        client_columns = [
            "contact_phone",
            "business_sector",
            "is_rbi_regulated",
        ]
        customer_columns = [
            "full_name",
            "company_name",
            "emails",
            "phones",
            "customer_type",
            "status",
            "tags",
            "total_tickets",
            "total_interactions",
            "first_interaction_at",
            "last_interaction_at",
            "avg_satisfaction_score",
            "churn_risk_score",
            "lifetime_value",
            "enrichment_data",
            "custom_fields",
            "is_master",
            "merged_into",
            "confidence_score",
            "updated_at",
        ]
        interaction_columns = [
            "client_id",
            "interaction_type",
            "interaction_channel",
            "complaint_id",
            "summary",
            "sentiment_score",
            "duration_seconds",
            "metadata",
            "created_at",
        ]
        event_log_columns = [
            "client_id",
            "event_type",
            "payload",
            "created_at",
        ]
        reply_queue_columns = [
            "reply_draft_id",
        ]

        added_client_columns = _sync_missing_model_columns("clients", Client, client_columns)
        if added_client_columns:
            added_summary["clients"] = added_client_columns

        added_complaint_columns = _sync_missing_model_columns(
            "complaints",
            Complaint,
            complaint_columns,
            extra_sql=[
                "CREATE INDEX IF NOT EXISTS ix_complaints_customer_id ON complaints(customer_id)",
                "CREATE INDEX IF NOT EXISTS idx_complaints_team ON complaints(client_id, team_id)",
                "CREATE INDEX IF NOT EXISTS idx_complaints_assigned_user ON complaints(client_id, assigned_user_id)",
            ],
        )
        if added_complaint_columns:
            added_summary["complaints"] = added_complaint_columns

        added_customer_columns = _sync_missing_model_columns("customers", Customer, customer_columns)
        if added_customer_columns:
            added_summary["customers"] = added_customer_columns

        added_interaction_columns = _sync_missing_model_columns(
            "customer_interactions",
            CustomerInteraction,
            interaction_columns,
        )
        if added_interaction_columns:
            added_summary["customer_interactions"] = added_interaction_columns

        added_reply_queue_columns = _sync_missing_model_columns(
            "ai_reply_queue",
            AIReplyQueue,
            reply_queue_columns,
        )
        if added_reply_queue_columns:
            added_summary["ai_reply_queue"] = added_reply_queue_columns

        added_event_log_columns = _sync_missing_model_columns("event_logs", EventLog, event_log_columns)
        if added_event_log_columns:
            added_summary["event_logs"] = added_event_log_columns

        if added_summary:
            for table_name, added_columns in added_summary.items():
                logger.info(
                    "Schema guard: Added missing %s columns: %s",
                    table_name,
                    ", ".join(sorted(added_columns)),
                )
    except Exception as exc:
        logger.warning("Schema guard: Column sync skipped: %s", exc)


def _seed_rbi_categories():
    """Seed RBI complaint categories with transaction safety."""
    with SessionLocal() as db:
        try:
            count = db.execute(text("SELECT COUNT(*) FROM rbi_complaint_categories")).scalar() or 0
            if count >= 12:
                logger.info("Schema guard: RBI categories already seeded (%s records)", count)
            else:
                logger.info("Schema guard: Seeding RBI complaint categories...")
                db.execute(
                    text(
                        """
                        INSERT INTO rbi_complaint_categories (category_code, category_name, subcategory_code, subcategory_name, tat_days) VALUES
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
                        ON CONFLICT DO NOTHING
                        """
                    )
                )
                logger.info("Schema guard: RBI categories seeded successfully")

            db.execute(
                text(
                    """
                    INSERT INTO rbi_categories (category_code, category_name, subcategory_code, subcategory_name, tat_days, description, is_active)
                    SELECT
                        category_code,
                        category_name,
                        subcategory_code,
                        subcategory_name,
                        tat_days,
                        description,
                        is_active
                    FROM rbi_complaint_categories
                    ON CONFLICT DO NOTHING
                    """
                )
            )
            db.commit()
            logger.info("Schema guard: RBI category compatibility seed verified")
        except Exception as exc:
            db.rollback()
            logger.warning("Schema guard: RBI category seed skipped: %s", exc)


def _seed_plan_features():
    """Seed plan features with transaction safety."""
    with SessionLocal() as db:
        try:
            count = db.execute(text("SELECT COUNT(*) FROM plan_features")).scalar() or 0
            if count >= 5:
                logger.info("Schema guard: Plan features already seeded (%s records)", count)
                return

            logger.info("Schema guard: Seeding plan features...")
            db.execute(
                text(
                    """
                    INSERT INTO plan_features (plan_name, features, limits) VALUES
                    (
                        'starter',
                        '{"ticketing_state_machine": true, "sla_management": false, "customer_360": false, "auto_reply_approval_queue": true, "rbi_compliance": false, "auto_escalation": false}'::jsonb,
                        '{"tickets_per_month": 500, "api_calls_per_day": 1000, "users": 3}'::jsonb
                    ),
                    (
                        'pro',
                        '{"ticketing_state_machine": true, "sla_management": true, "customer_360": true, "auto_reply_approval_queue": true, "rbi_compliance": false, "auto_escalation": false}'::jsonb,
                        '{"tickets_per_month": 2000, "api_calls_per_day": 10000, "users": 10}'::jsonb
                    ),
                    (
                        'max',
                        '{"ticketing_state_machine": true, "sla_management": true, "customer_360": true, "auto_reply_approval_queue": true, "rbi_compliance": false, "auto_escalation": false}'::jsonb,
                        '{"tickets_per_month": 10000, "api_calls_per_day": 50000, "users": 25}'::jsonb
                    ),
                    (
                        'scale',
                        '{"ticketing_state_machine": true, "sla_management": true, "customer_360": true, "auto_reply_approval_queue": true, "rbi_compliance": true, "auto_escalation": false}'::jsonb,
                        '{"tickets_per_month": 100000, "api_calls_per_day": 250000, "users": 100}'::jsonb
                    ),
                    (
                        'enterprise',
                        '{"ticketing_state_machine": true, "sla_management": true, "customer_360": true, "auto_reply_approval_queue": true, "rbi_compliance": true, "auto_escalation": true}'::jsonb,
                        '{"tickets_per_month": -1, "api_calls_per_day": -1, "users": -1}'::jsonb
                    )
                    ON CONFLICT (plan_name) DO UPDATE
                    SET features = EXCLUDED.features,
                        limits = EXCLUDED.limits,
                        updated_at = NOW()
                    """
                )
            )
            db.commit()
            logger.info("Schema guard: Plan features seeded successfully")
        except Exception as exc:
            db.rollback()
            logger.warning("Schema guard: Plan features seed skipped: %s", exc)


def _create_indexes():
    """Create additional indexes if they don't exist."""
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_complaints_client_state ON complaints(client_id, state, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_complaints_sla_due ON complaints(sla_due_at) WHERE sla_due_at IS NOT NULL AND resolved_at IS NULL",
        "CREATE INDEX IF NOT EXISTS idx_customers_client ON customers(client_id) WHERE is_master = true",
        "CREATE INDEX IF NOT EXISTS idx_customers_churn ON customers(client_id, churn_risk_score DESC) WHERE is_master = true",
        "CREATE INDEX IF NOT EXISTS idx_reply_queue_pending ON ai_reply_queue(client_id, created_at DESC) WHERE status = 'pending'",
        "CREATE INDEX IF NOT EXISTS idx_rbi_tat ON rbi_complaints(tat_due_date) WHERE resolution_date IS NULL",
        "CREATE INDEX IF NOT EXISTS idx_complaints_rbi_tat_due ON complaints(tat_due_at) WHERE tat_due_at IS NOT NULL",
        "CREATE INDEX IF NOT EXISTS idx_complaints_rbi_category ON complaints(client_id, rbi_category_code) WHERE rbi_category_code IS NOT NULL",
    ]

    for index_sql in indexes:
        with SessionLocal() as db:
            try:
                db.execute(text(index_sql))
                db.commit()
            except Exception as exc:
                db.rollback()
                logger.debug("Schema guard: Index creation skipped (may already exist): %s", exc)

    logger.info("Schema guard: Indexes verified")


if __name__ == "__main__":
    ensure_schema()
