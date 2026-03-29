from typing import Optional

from sqlalchemy.orm import Session

from app.db.models import RBIComplaintCategory


class RBITaxonomyClassifier:
    """Lightweight RBI category classifier."""

    CATEGORY_KEYWORDS = {
        "ATM": ["atm", "debit card", "cash withdrawal", "card declined", "dispensed"],
        "CC": ["credit card", "billing", "unauthorized charge", "statement"],
        "LOAN": ["loan", "emi", "disbursement", "interest rate", "foreclosure"],
        "DEP": ["deposit", "fixed deposit", "fd", "savings account", "interest not credited"],
        "NB": ["net banking", "online banking", "login", "password reset", "transaction failed"],
        "MOBILE": ["mobile banking", "app", "upi", "mobile app not working"],
        "BRANCH": ["branch", "customer service", "staff behavior", "waiting time"],
    }

    def __init__(self, db: Session):
        self.db = db

    def classify(self, complaint_text: str) -> tuple[Optional[str], Optional[str], float]:
        lowered = (complaint_text or "").lower()

        scores: dict[str, int] = {}
        for category_code, keywords in self.CATEGORY_KEYWORDS.items():
            score = sum(1 for keyword in keywords if keyword in lowered)
            if score > 0:
                scores[category_code] = score

        if not scores:
            return "OTHER", "OTHER", 0.3

        best_category = max(scores, key=scores.get)
        confidence = min(1.0, scores[best_category] / 3)
        subcategory = self._find_subcategory(best_category, lowered)
        return best_category, subcategory, confidence

    def _find_subcategory(self, category: str, text: str) -> str:
        subcategories = (
            self.db.query(RBIComplaintCategory)
            .filter(
                RBIComplaintCategory.category_code == category,
                RBIComplaintCategory.is_active == True,
            )
            .all()
        )
        for subcategory in subcategories:
            if subcategory.subcategory_name and subcategory.subcategory_name.lower() in text:
                return subcategory.subcategory_code or f"{category}_OTHER"
        if subcategories:
            return subcategories[0].subcategory_code or f"{category}_OTHER"
        return f"{category}_OTHER"
