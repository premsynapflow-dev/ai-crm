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

print("Migration complete: summary column added.")
