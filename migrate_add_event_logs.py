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
        CREATE TABLE IF NOT EXISTS event_logs (
            id UUID PRIMARY KEY,
            client_id UUID NOT NULL,
            event_type VARCHAR(100) NOT NULL,
            payload JSON,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
        );
    """))

print("Migration complete: event_logs table created.")
