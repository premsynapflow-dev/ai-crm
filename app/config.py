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
    admin_username: str
    admin_password: str
    gemini_api_key: str
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    smtp_from: str


def get_settings() -> Settings:
    database_url = os.getenv("DATABASE_URL", "").strip()
    openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
    slack_webhook_url = os.getenv("SLACK_WEBHOOK_URL", "").strip()
    secret_key = os.getenv("SECRET_KEY", "").strip()
    admin_username = os.getenv("ADMIN_USERNAME", "").strip()
    admin_password = os.getenv("ADMIN_PASSWORD", "").strip()
    gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
    smtp_host = os.getenv("SMTP_HOST", "").strip()
    try:
        smtp_port = int(os.getenv("SMTP_PORT", "587").strip() or "587")
    except ValueError:
        smtp_port = 587
    smtp_user = os.getenv("SMTP_USER", "").strip()
    smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
    smtp_from = os.getenv("SMTP_FROM", "").strip()

    missing = []
    if not database_url:
        missing.append("DATABASE_URL")
    if not slack_webhook_url:
        missing.append("SLACK_WEBHOOK_URL")
    if not secret_key:
        missing.append("SECRET_KEY")
    if not admin_username:
        missing.append("ADMIN_USERNAME")
    if not admin_password:
        missing.append("ADMIN_PASSWORD")

    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

    return Settings(
        database_url=database_url,
        openai_api_key=openai_api_key,
        slack_webhook_url=slack_webhook_url,
        secret_key=secret_key,
        admin_username=admin_username,
        admin_password=admin_password,
        gemini_api_key=gemini_api_key,
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        smtp_user=smtp_user,
        smtp_password=smtp_password,
        smtp_from=smtp_from,
    )
