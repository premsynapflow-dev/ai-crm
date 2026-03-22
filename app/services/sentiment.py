from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import Complaint
from app.services.ai import _extract_json_payload, get_gemini_client


def analyze_sentiment(complaint_text: str) -> dict:
    """
    Analyze customer sentiment on a 1-5 scale where 1 is calm and 5 is furious.
    """
    try:
        client = get_gemini_client()
        prompt = f"""Analyze the sentiment of this customer complaint.

Complaint: {complaint_text}

Provide:
1. Sentiment score (1-5): 1=calm, 2=mildly upset, 3=frustrated, 4=angry, 5=furious
2. Sentiment label: calm, upset, frustrated, angry, or furious
3. Key emotional indicators (2-3 short phrases that reveal the sentiment)

Respond with JSON only:
{{
  "score": <number 1-5>,
  "label": "<sentiment label>",
  "indicators": ["phrase1", "phrase2"]
}}"""

        response = client.generate_content(prompt, temperature=0.1, max_output_tokens=250)
        result = _extract_json_payload(response.text)
        score = int(result.get("score", 3))
        score = max(1, min(score, 5))

        return {
            "score": score,
            "label": str(result.get("label", "frustrated")).strip().lower() or "frustrated",
            "indicators": list(result.get("indicators", []))[:3],
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        return {
            "score": 3,
            "label": "unknown",
            "indicators": [],
            "error": str(exc),
        }


def get_sentiment_distribution(db: Session, client_id: str) -> dict:
    """Get distribution of 1-5 sentiment scores for a client."""
    complaints = db.query(Complaint).filter(Complaint.client_id == client_id).all()

    distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for complaint in complaints:
        score = getattr(complaint, "sentiment_score", None)
        if score in distribution:
            distribution[score] += 1

    return {
        "distribution": distribution,
        "labels": {
            1: "Calm",
            2: "Mildly Upset",
            3: "Frustrated",
            4: "Angry",
            5: "Furious",
        },
    }
