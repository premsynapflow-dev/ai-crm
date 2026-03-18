import os
from functools import lru_cache
from typing import Literal

from dotenv import load_dotenv
from pydantic import Field, ValidationError, field_validator

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError:  # pragma: no cover - keeps local imports working before deps install
    from pydantic import BaseModel as BaseSettings  # type: ignore[misc]

    SettingsConfigDict = dict  # type: ignore[assignment]

load_dotenv()


class Settings(BaseSettings):
    database_url: str = Field(alias="DATABASE_URL")
    secret_key: str = Field(alias="SECRET_KEY")
    environment: Literal["dev", "staging", "prod"] = Field(default="dev", alias="ENVIRONMENT")
    allowed_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:8000",
            "http://localhost:8000",
            "https://synapflow.up.railway.app",
        ],
        alias="ALLOWED_ORIGINS",
    )

    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    slack_webhook_url: str = Field(default="", alias="SLACK_WEBHOOK_URL")
    admin_username: str = Field(default="admin", alias="ADMIN_USERNAME")
    admin_password: str = Field(default="", alias="ADMIN_PASSWORD")

    smtp_host: str = Field(default="", alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_user: str = Field(default="", alias="SMTP_USER")
    smtp_password: str = Field(default="", alias="SMTP_PASSWORD")
    smtp_from: str = Field(default="", alias="SMTP_FROM")

    app_base_url: str = Field(default="http://127.0.0.1:8000", alias="APP_BASE_URL")
    sqlite_queue_path: str = Field(default="data/jobs.db", alias="SQLITE_QUEUE_PATH")
    request_log_retention_days: int = Field(default=30, alias="REQUEST_LOG_RETENTION_DAYS")

    razorpay_key_id: str = Field(default="", alias="RAZORPAY_KEY_ID")
    razorpay_key_secret: str = Field(default="", alias="RAZORPAY_KEY_SECRET")
    razorpay_webhook_secret: str = Field(default="", alias="RAZORPAY_WEBHOOK_SECRET")

    jwt_secret_key: str = Field(default="", alias="JWT_SECRET_KEY")
    access_token_expire_minutes: int = Field(default=60, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(default=30, alias="REFRESH_TOKEN_EXPIRE_DAYS")

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    sentry_dsn: str = Field(default="", alias="SENTRY_DSN")

    if SettingsConfigDict is not dict:
        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            extra="ignore",
            populate_by_name=True,
        )

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("DATABASE_URL is required")
        return value

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters")
        return value

    @field_validator("admin_password")
    @classmethod
    def validate_admin_password(cls, value: str) -> str:
        if value and len(value) < 8:
            raise ValueError("ADMIN_PASSWORD must be at least 8 characters when set")
        return value

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, value: str) -> str:
        allowed = ["dev", "staging", "prod"]
        if value not in allowed:
            raise ValueError(f"ENVIRONMENT must be one of {allowed}")
        return value

    def is_production(self) -> bool:
        return self.environment == "prod"

    def is_development(self) -> bool:
        return self.environment == "dev"

    @field_validator("jwt_secret_key")
    @classmethod
    def default_jwt_secret(cls, value: str, info):  # type: ignore[override]
        return value or info.data.get("secret_key", "")

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value):
        if isinstance(value, list):
            return [item.strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


def _manual_settings_data() -> dict:
    return {
        "DATABASE_URL": os.getenv("DATABASE_URL", ""),
        "SECRET_KEY": os.getenv("SECRET_KEY", ""),
        "ENVIRONMENT": os.getenv("ENVIRONMENT", "dev"),
        "ALLOWED_ORIGINS": os.getenv(
            "ALLOWED_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000,http://127.0.0.1:8000,http://localhost:8000,https://synapflow.up.railway.app",
        ),
        "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY", ""),
        "SLACK_WEBHOOK_URL": os.getenv("SLACK_WEBHOOK_URL", ""),
        "ADMIN_USERNAME": os.getenv("ADMIN_USERNAME", "admin"),
        "ADMIN_PASSWORD": os.getenv("ADMIN_PASSWORD", ""),
        "SMTP_HOST": os.getenv("SMTP_HOST", ""),
        "SMTP_PORT": os.getenv("SMTP_PORT", "587"),
        "SMTP_USER": os.getenv("SMTP_USER", ""),
        "SMTP_PASSWORD": os.getenv("SMTP_PASSWORD", ""),
        "SMTP_FROM": os.getenv("SMTP_FROM", ""),
        "APP_BASE_URL": os.getenv("APP_BASE_URL", "http://127.0.0.1:8000"),
        "SQLITE_QUEUE_PATH": os.getenv("SQLITE_QUEUE_PATH", "data/jobs.db"),
        "REQUEST_LOG_RETENTION_DAYS": os.getenv("REQUEST_LOG_RETENTION_DAYS", "30"),
        "RAZORPAY_KEY_ID": os.getenv("RAZORPAY_KEY_ID", ""),
        "RAZORPAY_KEY_SECRET": os.getenv("RAZORPAY_KEY_SECRET", ""),
        "RAZORPAY_WEBHOOK_SECRET": os.getenv("RAZORPAY_WEBHOOK_SECRET", ""),
        "JWT_SECRET_KEY": os.getenv("JWT_SECRET_KEY", ""),
        "ACCESS_TOKEN_EXPIRE_MINUTES": os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"),
        "REFRESH_TOKEN_EXPIRE_DAYS": os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30"),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", ""),
        "SENTRY_DSN": os.getenv("SENTRY_DSN", ""),
    }


@lru_cache
def get_settings() -> Settings:
    try:
        if hasattr(Settings, "model_config") and SettingsConfigDict is not dict:
            return Settings()
        return Settings(**_manual_settings_data())
    except ValidationError as exc:
        raise RuntimeError(str(exc)) from exc
