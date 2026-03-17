import httpx

from app.config import get_settings
from app.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


def send_slack_alert(text: str, webhook_url: str | None = None) -> None:
    """
    Send a Slack alert to the given webhook URL.
    Falls back to the global SLACK_WEBHOOK_URL from .env if none is provided.
    Silently skips if neither is configured.
    """
    url = webhook_url or settings.slack_webhook_url

    if not url:
        logger.warning("No Slack webhook URL configured - alert skipped.")
        return False

    payload = {"text": text}
    with httpx.Client(timeout=10.0) as client:
        response = client.post(url, json=payload)
        response.raise_for_status()
    return True
