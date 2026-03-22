import os
from urllib.parse import parse_qs, urlparse

from app.utils.logging import get_logger

logger = get_logger(__name__)


def verify_database_security() -> None:
    """
    Verify that the configured database connection uses a secure direct PostgreSQL DSN.

    Raises:
        RuntimeError: If a critical configuration issue is found.
    """
    db_url = os.getenv("DATABASE_URL", "").strip()

    if not db_url:
        raise RuntimeError("SECURITY: DATABASE_URL environment variable is not set")

    parsed = urlparse(db_url)
    scheme = parsed.scheme.lower()
    is_postgres_scheme = scheme in {"postgresql", "postgres"} or scheme.startswith("postgresql+")
    if not is_postgres_scheme:
        raise RuntimeError(
            "SECURITY: DATABASE_URL must use a direct PostgreSQL connection string "
            "(postgresql:// or postgres://). Do not use Supabase HTTP API endpoints."
        )

    normalized_url = db_url.lower()
    if "anon" in normalized_url or "service_role" in normalized_url:
        raise RuntimeError(
            "SECURITY: Do not expose Supabase API keys (anon/service_role) in DATABASE_URL. "
            "Use a direct PostgreSQL connection string instead."
        )

    sslmode = parse_qs(parsed.query).get("sslmode", [])
    if not sslmode:
        logger.warning(
            "SECURITY WARNING: SSL mode is not explicitly set in DATABASE_URL. "
            "Consider adding ?sslmode=require for encrypted connections."
        )

    logger.info("Database connection security check passed")


def verify_client_isolation() -> None:
    """
    Log a reminder that all multi-tenant queries must filter by client_id.
    """
    logger.info("Client data isolation check: ensure all complaint and analytics queries filter by client_id")


def run_all_security_checks() -> bool:
    """Run all security verification checks during application startup."""
    try:
        verify_database_security()
        verify_client_isolation()
        logger.info("All security checks passed")
        return True
    except RuntimeError as exc:
        logger.error("SECURITY CHECK FAILED: %s", exc)
        logger.error("Application may be vulnerable. Review the database and tenant-isolation configuration.")
        return False
