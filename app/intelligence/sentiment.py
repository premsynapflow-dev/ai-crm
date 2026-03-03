from openai import OpenAI

from app.config import get_settings
from app.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()
client = OpenAI(api_key=settings.openai_api_key)


def _clamp(value: float, min_v: float, max_v: float) -> float:
    return max(min_v, min(max_v, value))


def analyze_sentiment(message: str) -> float:
    prompt = (
        "Analyze sentiment of this complaint and return only a number between -1 and 1. "
        "-1 is extremely negative, 1 is extremely positive."
    )

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        messages=[
            {"role": "system", "content": "You return only numeric sentiment scores."},
            {"role": "user", "content": f"{prompt}\n\nComplaint:\n{message}"},
        ],
    )

    raw = (response.choices[0].message.content or "").strip()
    try:
        score = float(raw)
    except ValueError:
        logger.warning("Invalid sentiment '%s', defaulting to 0.0.", raw)
        score = 0.0

    return _clamp(score, -1.0, 1.0)
