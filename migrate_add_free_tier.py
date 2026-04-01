"""
Migration: Add Free Tier Plan
- Updates clients on invalid legacy plans to the new free tier
- Leaves existing paid customers unchanged
"""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def migrate():
    db = SessionLocal()
    try:
        result = db.execute(
            text(
                """
                SELECT COUNT(*)
                FROM clients
                WHERE plan NOT IN ('free', 'starter', 'pro', 'max', 'scale', 'enterprise')
                """
            )
        )
        count = result.scalar() or 0

        if count <= 0:
            print("No migration needed. All clients already have valid plans.")
            return

        print(f"Found {count} clients with invalid plans. Migrating them to 'free'...")
        db.execute(
            text(
                """
                UPDATE clients
                SET plan = 'free',
                    plan_id = 'free',
                    monthly_ticket_limit = 50,
                    trial_ends_at = NULL
                WHERE plan NOT IN ('free', 'starter', 'pro', 'max', 'scale', 'enterprise')
                """
            )
        )
        db.commit()
        print("Migration completed successfully.")
    except Exception as exc:
        db.rollback()
        print(f"Migration failed: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    migrate()
