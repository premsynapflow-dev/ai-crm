import logging
import re
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)


class ReplyConfidenceScorer:
    """Multi-factor confidence scoring with lightweight safety checks."""

    TOXIC_KEYWORDS = ["stupid", "idiot", "hate", "worst", "terrible", "awful", "useless"]
    HALLUCINATION_PATTERNS = [
        r"as an ai",
        r"i cannot",
        r"i am a language model",
        r"i don't have access",
        r"i'm not able to",
        r"i apologize.*i don't have",
    ]

    def __init__(self):
        settings = get_settings()
        self.auto_approve_threshold = settings.reply_auto_approve_threshold
        self.human_review_threshold = settings.reply_human_review_threshold

    def score_reply(self, reply_text: str, ticket_summary: str, generation_metadata: dict[str, Any]) -> dict[str, Any]:
        warnings: list[str] = []

        sanitized_reply = (reply_text or "").strip()
        length_score = self._score_length(sanitized_reply)
        coherence_score = self._score_coherence(sanitized_reply)
        relevance_score = self._score_relevance(sanitized_reply, ticket_summary or "")
        toxicity_score = self._check_toxicity(sanitized_reply)
        hallucination_passed = self._check_hallucinations(sanitized_reply)
        factual_consistency_score = self._score_factual_consistency(sanitized_reply, ticket_summary or "")
        model_confidence = float(generation_metadata.get("model_confidence", 0.7) or 0.7)

        confidence_score = (
            0.25 * model_confidence
            + 0.20 * coherence_score
            + 0.20 * relevance_score
            + 0.10 * length_score
            + 0.10 * (1.0 - toxicity_score)
            + 0.15 * factual_consistency_score
        )

        if not hallucination_passed:
            confidence_score *= 0.7
            warnings.append("Potential hallucination detected")

        if toxicity_score > 0.3:
            confidence_score *= 0.8
            warnings.append(f"Toxicity score: {toxicity_score:.2f}")

        if factual_consistency_score < 0.5:
            confidence_score *= 0.85
            warnings.append("Low factual consistency")

        if confidence_score >= self.auto_approve_threshold and hallucination_passed:
            recommendation = "auto_approve"
        elif confidence_score >= self.human_review_threshold:
            recommendation = "human_review"
        else:
            recommendation = "reject"
            warnings.append("Confidence too low")

        return {
            "confidence_score": max(0.0, min(1.0, round(confidence_score, 4))),
            "hallucination_check_passed": hallucination_passed,
            "toxicity_score": round(toxicity_score, 4),
            "factual_consistency_score": round(factual_consistency_score, 4),
            "recommendation": recommendation,
            "warnings": warnings,
            "component_scores": {
                "length": round(length_score, 4),
                "coherence": round(coherence_score, 4),
                "relevance": round(relevance_score, 4),
                "model_confidence": round(model_confidence, 4),
                "factual_consistency": round(factual_consistency_score, 4),
            },
        }

    def _score_length(self, text: str) -> float:
        word_count = len(text.split())
        if 50 <= word_count <= 300:
            return 1.0
        if word_count == 0:
            return 0.0
        if word_count < 50:
            return max(0.3, word_count / 50)
        return max(0.5, 1.0 - (word_count - 300) / 500)

    def _score_coherence(self, text: str) -> float:
        if not text:
            return 0.0

        score = 1.0
        sentences = [sentence.strip() for sentence in re.split(r"[.!?]", text) if sentence.strip()]
        if len(sentences) < 2:
            score *= 0.7
        if not text[0].isupper():
            score *= 0.9
        if text.rstrip()[-1] not in ".!?":
            score *= 0.9

        words = re.findall(r"\b\w+\b", text.lower())
        if words:
            unique_ratio = len(set(words)) / len(words)
            if unique_ratio < 0.4:
                score *= 0.7

        if "\n\n\n" in text:
            score *= 0.9
        return max(0.0, score)

    def _score_relevance(self, reply: str, ticket_summary: str) -> float:
        ticket_words = {word.lower() for word in re.findall(r"\b\w+\b", ticket_summary) if len(word) > 3}
        reply_words = {word.lower() for word in re.findall(r"\b\w+\b", reply) if len(word) > 3}
        if not ticket_words:
            return 0.5
        overlap = len(ticket_words & reply_words)
        return min(1.0, overlap / max(4, len(ticket_words) * 0.3))

    def _check_toxicity(self, text: str) -> float:
        lowered = text.lower()
        toxic_count = sum(1 for keyword in self.TOXIC_KEYWORDS if keyword in lowered)
        return min(1.0, toxic_count / 5)

    def _check_hallucinations(self, text: str) -> bool:
        lowered = text.lower()
        for pattern in self.HALLUCINATION_PATTERNS:
            if re.search(pattern, lowered):
                logger.warning("Reply hallucination pattern matched: %s", pattern)
                return False
        return True

    def _score_factual_consistency(self, reply: str, ticket_summary: str) -> float:
        if not reply:
            return 0.0
        lowered_reply = reply.lower()
        penalty = 0.0
        if "refund" in lowered_reply and "refund" not in ticket_summary.lower():
            penalty += 0.2
        if "replacement" in lowered_reply and "replace" not in ticket_summary.lower() and "replacement" not in ticket_summary.lower():
            penalty += 0.15
        if "order number" in lowered_reply and "order" not in ticket_summary.lower():
            penalty += 0.05
        return max(0.3, 1.0 - penalty)
