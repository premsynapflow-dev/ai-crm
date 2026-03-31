RBI_REGULATED_SECTORS = {
    "bank": "Bank / Co-operative Bank / Small Finance Bank / Payment Bank",
    "nbfc_hfc": "NBFC / HFC",
    "fintech_payments": "Fintech / Payments / PPI / Payment Aggregator / Payment System Operator",
    "other_rbi_regulated": "Other RBI-regulated financial entity",
    "not_rbi_regulated": "Not RBI-regulated / Non-financial company",
}


def is_rbi_regulated_sector(value: str | None) -> bool:
    return value in {
        "bank",
        "nbfc_hfc",
        "fintech_payments",
        "other_rbi_regulated",
    }
