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

        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_complaints_response_time
                ON complaints (response_time_seconds)
                """
            )
        )

    logger.info("Schema guard completed.")


def main() -> None:
    ensure_schema()


if __name__ == "__main__":
    main()
