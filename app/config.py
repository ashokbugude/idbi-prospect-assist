"""Application configuration."""

from __future__ import annotations

import os

APP_VERSION = "0.7.0"
APP_TITLE = "IDBI Prospect Assist AI"

# Demo RM login PIN (override via RM_DEMO_PIN env in production)
RM_DEMO_PIN = os.environ.get("RM_DEMO_PIN", "idbi2026")
AUTH_COOKIE = "prospect_rm_session"
AUTH_EXEMPT_PREFIXES = (
    "/static",
    "/login",
    "/api/health",
    "/api/impact",
    "/api/sandbox",
    "/api/demo-comparison",
    "/api/ml/model-card",
    "/api/ml/evaluation",
    "/api/stats",
)

# Documented demo walkthrough customers (seed=42 dataset)
HERO_CUSTOMERS = {
    "quality_lead": "IDBI-L10010",
    "window_shopper": "IDBI-L10121",
    "multibank_uplift": "IDBI-L10033",
}

# Self-employed net margin by business type (AMA: industry margin assumptions)
SELF_EMPLOYED_MARGINS: dict[str, float] = {
    "retail_trade": 0.32,
    "services": 0.48,
    "professional": 0.62,
    "manufacturing": 0.28,
    "gig_platform": 0.55,
}
