import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    database_url: str
    openai_api_key: str
    slack_webhook_url: str
    secret_key: str


def get_settings() -> Settings:
    database_url = os.getenv("DATABASE_URL", "").strip()
    openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
    slack_webhook_url = os.getenv("SLACK_WEBHOOK_URL", "").strip()
    secret_key = os.getenv("SECRET_KEY", "").strip()

    missing = []
    if not database_url:
        missing.append("DATABASE_URL")
    if not openai_api_key:
        missing.append("OPENAI_API_KEY")
    if not slack_webhook_url:
        missing.append("SLACK_WEBHOOK_URL")
    if not secret_key:
        missing.append("SECRET_KEY")

    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

    return Settings(
        database_url=database_url,
        openai_api_key=openai_api_key,
        slack_webhook_url=slack_webhook_url,
        secret_key=secret_key,
    )
