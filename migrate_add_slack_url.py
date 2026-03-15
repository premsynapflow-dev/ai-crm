"""
Run this once to add the slack_webhook_url column to the clients table.
Usage: python migrate_add_slack_url.py
"""
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

engine = create_engine(
    os.getenv("DATABASE_URL", ""),
    connect_args={"sslmode": "require"},
)

with engine.begin() as conn:
    conn.execute(text("""
        ALTER TABLE clients
        ADD COLUMN IF NOT EXISTS slack_webhook_url VARCHAR(500);
    """))
    print("Migration complete: slack_webhook_url column added to clients table.")
