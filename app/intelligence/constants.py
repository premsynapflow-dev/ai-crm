"""Single source of truth for all scoring thresholds, weights, and configuration constants.

Import from here — never hardcode these values inline.
"""
from __future__ import annotations

# ── Customer Risk Score thresholds (0–100 behavioral index) ────────────────────
RISK_HIGH_THRESHOLD   = 70      # cutoff for "high risk" in revenue calculations
RISK_LEVEL_HIGH       = 70      # label threshold: >= this → "high"
RISK_LEVEL_MEDIUM     = 40      # label threshold: >= this → "medium"
# below RISK_LEVEL_MEDIUM → "low"

# ── Sentiment (canonical scale: −1.0 to +1.0 float) ───────────────────────────
SENTIMENT_NEGATIVE      = -0.20   # label threshold: below this → "negative"
SENTIMENT_STRONG_NEG    = -0.45   # strong negative used in scoring
SENTIMENT_STREAK_NEG    = -0.25   # consecutive-message threshold for streak detection
SATISFACTION_LOW        = 3.0     # below this on a 1–5 scale → low satisfaction

# ── Churn probability calibration bands ────────────────────────────────────────
# Maps (risk_score_low, risk_score_high) → (prob_low, prob_high)
# Linear interpolation is used within each band.
# Probabilities are conservative — never claim >0.70 without a validated ML model.
CHURN_PROB_BANDS: list[tuple[float, float, float, float]] = [
    (0,   20,  0.01, 0.05),
    (20,  40,  0.05, 0.12),
    (40,  60,  0.12, 0.25),
    (60,  75,  0.25, 0.45),
    (75, 100,  0.45, 0.70),
]

# ── Grouped risk signal caps (Phase 3 scoring engine) ─────────────────────────
RISK_GROUP_CAPS = {
    "volume":     20,
    "sentiment":  25,
    "escalation": 20,
    "resolution": 20,
    "behavioral": 25,
}
RISK_LOYALTY_MAX_DISCOUNT = 10   # maximum loyalty discount (subtract from final score)

# Industry profiles that do NOT treat inactivity as a churn signal
# (SaaS / Insurance / Healthcare have natural low-contact periods)
INACTIVITY_EXEMPT_INDUSTRIES = frozenset({"SaaS", "Insurance", "Healthcare", "Fintech"})

# ── Forecasting ────────────────────────────────────────────────────────────────
FORECAST_MIN_DATA_DAYS           = 14     # minimum history before enabling seasonality
FORECAST_ALPHA                   = 0.3    # EWMA smoothing factor
FORECAST_ALERT_MULTIPLIER        = 1.5    # predicted > baseline * 1.5 → alert
FORECAST_CRITICAL_MULTIPLIER     = 2.0    # predicted > baseline * 2.0 → critical
# Confidence band multipliers (applied to point estimate)
FORECAST_CONFIDENCE_LOWER        = 0.70   # 30% below estimate
FORECAST_CONFIDENCE_UPPER        = 1.40   # 40% above estimate
# Wider bands when data is insufficient
FORECAST_LOW_DATA_LOWER          = 0.50
FORECAST_LOW_DATA_UPPER          = 2.00

# ── Spike detection ────────────────────────────────────────────────────────────
SPIKE_ZSCORE_HIGH       = 2.0    # z > this → "high" severity spike
SPIKE_ZSCORE_MEDIUM     = 1.5    # z > this → "medium" severity spike
SPIKE_MIN_COUNT         = 5      # minimum hourly count to even check for spikes
SPIKE_ROLLING_WINDOW_DAYS = 7    # rolling baseline window in days

# ── Team performance ───────────────────────────────────────────────────────────
TEAM_PERF_MIN_SAMPLE    = 5      # minimum tickets before reporting averages
TEAM_PERF_LOW_CONF_N    = 10     # below this → low_confidence = True

# ── Reply confidence ───────────────────────────────────────────────────────────
REPLY_CONFIDENCE_WEIGHTS = {
    "model_confidence":         0.25,
    "coherence":                0.20,
    "relevance":                0.20,
    "length":                   0.10,
    "non_toxicity":             0.10,
    "factual_consistency":      0.15,
}

# ── Revenue value source priority labels ──────────────────────────────────────
VALUE_SOURCE_ACTUAL    = "actual"
VALUE_SOURCE_CONTRACT  = "contract"
VALUE_SOURCE_MRR       = "mrr"
VALUE_SOURCE_ESTIMATED = "estimated"
VALUE_SOURCE_UNKNOWN   = "unknown"

# ── Risk score model version ───────────────────────────────────────────────────
RISK_MODEL_VERSION = "v2"   # increment when scoring algorithm changes materially
