from sqlalchemy import inspect, text

from app.db.models import Base
from app.db.session import engine
from app.utils.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


REQUIRED_COLUMNS = {
    "clients": {
        "custom_prompt_enabled": (
            "ALTER TABLE clients "
            "ADD COLUMN IF NOT EXISTS custom_prompt_enabled BOOLEAN DEFAULT FALSE"
        ),
        "custom_prompt_config": (
            "ALTER TABLE clients "
            "ADD COLUMN IF NOT EXISTS custom_prompt_config JSONB"
        ),
        "custom_prompt_updated_at": (
            "ALTER TABLE clients "
            "ADD COLUMN IF NOT EXISTS custom_prompt_updated_at TIMESTAMPTZ"
        ),
    },
    "complaints": {
        "sentiment_score": (
            "ALTER TABLE complaints "
            "ADD COLUMN IF NOT EXISTS sentiment_score INTEGER"
        ),
        "sentiment_label": (
            "ALTER TABLE complaints "
            "ADD COLUMN IF NOT EXISTS sentiment_label VARCHAR(50)"
        ),
        "sentiment_indicators": (
            "ALTER TABLE complaints "
            "ADD COLUMN IF NOT EXISTS sentiment_indicators JSONB"
        ),
        "assigned_to": (
            "ALTER TABLE complaints "
            "ADD COLUMN IF NOT EXISTS assigned_to VARCHAR(255)"
        ),
        "customer_id": (
            "ALTER TABLE complaints "
            "ADD COLUMN IF NOT EXISTS customer_id UUID REFERENCES customers(id) ON DELETE SET NULL"
        ),
        "state": (
            "ALTER TABLE complaints "
            "ADD COLUMN IF NOT EXISTS state VARCHAR(50) DEFAULT 'new'"
        ),
        "state_changed_at": (
            "ALTER TABLE complaints "
            "ADD COLUMN IF NOT EXISTS state_changed_at TIMESTAMPTZ DEFAULT NOW()"
        ),
        "ticket_number": (
            "ALTER TABLE complaints "
            "ADD COLUMN IF NOT EXISTS ticket_number VARCHAR(50)"
        ),
        "reopened_count": (
            "ALTER TABLE complaints "
            "ADD COLUMN IF NOT EXISTS reopened_count INTEGER DEFAULT 0"
        ),
        "last_reopened_at": (
            "ALTER TABLE complaints "
            "ADD COLUMN IF NOT EXISTS last_reopened_at TIMESTAMPTZ"
        ),
        "sla_due_at": (
            "ALTER TABLE complaints "
            "ADD COLUMN IF NOT EXISTS sla_due_at TIMESTAMPTZ"
        ),
        "sla_status": (
            "ALTER TABLE complaints "
            "ADD COLUMN IF NOT EXISTS sla_status VARCHAR(20) DEFAULT 'on_track'"
        ),
        "escalation_level": (
            "ALTER TABLE complaints "
            "ADD COLUMN IF NOT EXISTS escalation_level INTEGER DEFAULT 0"
        ),
        "escalated_at": (
            "ALTER TABLE complaints "
            "ADD COLUMN IF NOT EXISTS escalated_at TIMESTAMPTZ"
        ),
        "escalated_to": (
            "ALTER TABLE complaints "
            "ADD COLUMN IF NOT EXISTS escalated_to VARCHAR(255)"
        ),
        "resolved_at": (
            "ALTER TABLE complaints "
            "ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMPTZ"
        ),
        "first_response_at": (
            "ALTER TABLE complaints "
            "ADD COLUMN IF NOT EXISTS first_response_at TIMESTAMPTZ"
        ),
        "response_time_seconds": (
            "ALTER TABLE complaints "
            "ADD COLUMN IF NOT EXISTS response_time_seconds INTEGER"
        ),
        "customer_satisfaction_score": (
            "ALTER TABLE complaints "
            "ADD COLUMN IF NOT EXISTS customer_satisfaction_score INTEGER"
        ),
        "satisfaction_score": (
            "ALTER TABLE complaints "
            "ADD COLUMN IF NOT EXISTS satisfaction_score INTEGER"
        ),
        "ai_reply": (
            "ALTER TABLE complaints "
            "ADD COLUMN IF NOT EXISTS ai_reply TEXT"
        ),
        "ai_reply_confidence": (
            "ALTER TABLE complaints "
            "ADD COLUMN IF NOT EXISTS ai_reply_confidence FLOAT"
        ),
        "ai_reply_status": (
            "ALTER TABLE complaints "
            "ADD COLUMN IF NOT EXISTS ai_reply_status VARCHAR DEFAULT 'pending'"
        ),
        "ai_reply_sent_at": (
            "ALTER TABLE complaints "
            "ADD COLUMN IF NOT EXISTS ai_reply_sent_at TIMESTAMPTZ"
        ),
    },
    "job_queue": {
        "last_error": (
            "ALTER TABLE job_queue "
            "ADD COLUMN IF NOT EXISTS last_error TEXT"
        ),
    },
}

REQUIRED_INDEXES = [
    """
    CREATE INDEX IF NOT EXISTS idx_reply_queue_status
    ON ai_reply_queue (client_id, status, created_at)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_reply_queue_confidence
    ON ai_reply_queue (client_id, confidence_score)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_reply_queue_pending
    ON ai_reply_queue (client_id, created_at)
    WHERE status = 'pending'
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_feedback_queue
    ON reply_feedback (reply_queue_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_templates_client_category
    ON reply_templates (client_id, category)
    WHERE enabled = true
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_rbi_complaints_client
    ON rbi_complaints (client_id, created_at)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_rbi_complaints_tat
    ON rbi_complaints (tat_due_date)
    WHERE resolution_date IS NULL
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_rbi_complaints_category
    ON rbi_complaints (category_code, subcategory_code)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_escalation_log_complaint
    ON rbi_escalation_log (rbi_complaint_id, escalated_at)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_mis_reports_client_month
    ON rbi_mis_reports (client_id, report_month)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_plan_features_plan_name
    ON plan_features (plan_name)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_usage_tracking_client
    ON tenant_usage_tracking (client_id, period_start)
    """,
]

RBI_CATEGORY_SEED = """
INSERT INTO rbi_complaint_categories (category_code, category_name, subcategory_code, subcategory_name, tat_days)
VALUES
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
ON CONFLICT (category_code, subcategory_code) DO NOTHING
"""

PLAN_FEATURE_SEED = """
INSERT INTO plan_features (plan_name, features, limits)
VALUES
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


def ensure_schema() -> None:
    Base.metadata.create_all(bind=engine)

    with engine.begin() as conn:
        inspector = inspect(conn)
        tables = set(inspector.get_table_names())

        for table_name, columns in REQUIRED_COLUMNS.items():
            if table_name not in tables:
                logger.warning(
                    "Schema guard: table '%s' missing after create_all; skipping column checks.",
                    table_name,
                )
                continue

            existing_columns = {
                column["name"] for column in inspector.get_columns(table_name)
            }
            missing_columns = [
                column_name
                for column_name in columns
                if column_name not in existing_columns
            ]

            if missing_columns:
                logger.warning(
                    "Schema guard: table '%s' missing columns %s",
                    table_name,
                    ", ".join(missing_columns),
                )

            for column_name in missing_columns:
                conn.execute(text(columns[column_name]))

        existing_tables = tables
        for index_sql in REQUIRED_INDEXES:
            try:
                conn.execute(text(index_sql))
            except Exception as exc:
                logger.warning("Schema guard: could not create index: %s", exc)

        if "plan_features" in existing_tables:
            try:
                conn.execute(text(PLAN_FEATURE_SEED))
            except Exception as exc:
                logger.warning("Schema guard: plan feature seed skipped: %s", exc)

        if "rbi_complaint_categories" in existing_tables:
            try:
                conn.execute(text(RBI_CATEGORY_SEED))
            except Exception as exc:
                logger.warning("Schema guard: RBI category seed skipped: %s", exc)

        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_complaints_response_time
                ON complaints (response_time_seconds)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_complaints_customer
                ON complaints (customer_id)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_complaints_state
                ON complaints (client_id, state, created_at)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_complaints_sla_due
                ON complaints (sla_due_at)
                WHERE sla_due_at IS NOT NULL AND resolved_at IS NULL
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_complaints_ticket_number
                ON complaints (ticket_number)
                WHERE ticket_number IS NOT NULL
                """
            )
        )

    logger.info("Schema guard completed.")


def main() -> None:
    ensure_schema()


if __name__ == "__main__":
    main()
