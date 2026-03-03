from openai import OpenAI

from app.config import get_settings
from app.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()
client = OpenAI(api_key=settings.openai_api_key)

_ALLOWED_CATEGORIES = {"refund", "billing", "technical", "abuse", "general"}


def classify_complaint(message: str) -> str:
    prompt = (
        "Classify the customer complaint into exactly one category from this list: "
        "refund, billing, technical, abuse, general. "
        "Return only the single category token."
    )

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        messages=[
            {"role": "system", "content": "You are a strict complaint classifier."},
            {"role": "user", "content": f"{prompt}\n\nComplaint:\n{message}"},
        ],
    )

    raw = (response.choices[0].message.content or "").strip().lower()
    category = raw.split()[0] if raw else "general"

    if category not in _ALLOWED_CATEGORIES:
        logger.warning("Unexpected category '%s', defaulting to general.", category)
        return "general"

    return category
