"""
Schema Guard - Ensures database schema is initialized
Fixed version with proper transaction handling
"""

import logging

from sqlalchemy import text

from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

REQUIRED_TABLES = [
    "clients",
    "complaints",
    "sla_policies",
    "business_hours",
    "ticket_state_transitions",
    "escalation_rules",
    "ticket_comments",
    "ticket_assignments",
    "customers",
    "customer_merge_history",
    "customer_interactions",
    "customer_notes",
    "customer_relationships",
    "reply_templates",
    "ai_reply_queue",
    "reply_feedback",
    "reply_ab_tests",
    "reply_quality_metrics",
    "rbi_complaint_categories",
    "rbi_complaints",
    "rbi_escalation_log",
    "rbi_mis_reports",
    "plan_features",
    "tenant_usage_tracking",
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


def _seed_rbi_categories():
    """Seed RBI complaint categories with transaction safety."""
    with SessionLocal() as db:
        try:
            count = db.execute(text("SELECT COUNT(*) FROM rbi_complaint_categories")).scalar() or 0
            if count >= 12:
                logger.info("Schema guard: RBI categories already seeded (%s records)", count)
                return

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
            db.commit()
            logger.info("Schema guard: RBI categories seeded successfully")
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
                        '{"ticketing_state_machine": true, "sla_management": true, "customer_360": true, "auto_reply_approval_queue": true, "rbi_compliance": true, "auto_escalation": false}'::jsonb,
                        '{"tickets_per_month": 2000, "api_calls_per_day": 10000, "users": 10}'::jsonb
                    ),
                    (
                        'max',
                        '{"ticketing_state_machine": true, "sla_management": true, "customer_360": true, "auto_reply_approval_queue": true, "rbi_compliance": true, "auto_escalation": false}'::jsonb,
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
