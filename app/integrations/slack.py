import httpx

from app.config import get_settings

settings = get_settings()


def send_slack_alert(text: str) -> None:
    payload = {"text": text}
    with httpx.Client(timeout=10.0) as client:
        response = client.post(settings.slack_webhook_url, json=payload)
        response.raise_for_status()
