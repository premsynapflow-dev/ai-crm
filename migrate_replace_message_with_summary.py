from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

engine = create_engine(
    os.getenv("DATABASE_URL"),
    connect_args={"sslmode": "require"},
)

with engine.begin() as conn:

    conn.execute(text("""
        ALTER TABLE complaints
        ADD COLUMN IF NOT EXISTS summary VARCHAR(500);
    """))

    conn.execute(text("""
        UPDATE complaints
        SET summary = message
        WHERE summary IS NULL;
    """))

    conn.execute(text("""
        ALTER TABLE complaints
        DROP COLUMN IF EXISTS message;
    """))

print("Migration complete: message column replaced with summary")
