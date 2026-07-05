"""Account Aggregator (AA) consent + fetch simulation for multi-bank view."""

from __future__ import annotations

import hashlib
import time
from typing import Any

from app.enrichment import idbi_only_baseline
from app.multibank import analyze_multibank
from app.scoring import TIER_CSS, score_customer

_CONSENTS: dict[str, dict[str, Any]] = {}


def initiate_aa_consent(customer_id: str, fip_ids: list[str] | None = None) -> dict:
    consent_id = hashlib.sha256(f"{customer_id}:{time.time()}".encode()).hexdigest()[:16]
    _CONSENTS[consent_id] = {
        "customer_id": customer_id,
        "status": "approved",
        "fip_ids": fip_ids or ["HDFC-FIP", "ICICI-FIP", "SBI-FIP"],
        "consent_scope": ["DEPOSIT", "RECURRING_DEPOSIT"],
        "valid_days": 30,
        "dpdp_notice": "Customer consented via AA framework; data used only for repayment assessment.",
    }
    return {
        "consent_id": consent_id,
        "status": "approved",
        "message": "AA consent granted — fetching other-bank statements",
        "fip_ids": _CONSENTS[consent_id]["fip_ids"],
        "dpdp_notice": _CONSENTS[consent_id]["dpdp_notice"],
    }


def fetch_aa_statements(customer: dict, consent_id: str) -> dict:
    consent = _CONSENTS.get(consent_id)
    if not consent or consent["customer_id"] != customer.get("customer_id"):
        return {"error": "Invalid or expired AA consent", "status": "failed"}

    import random

    rng = random.Random(hash(consent_id) % 2**32)
    stated = int(customer.get("monthly_income", 0))
    share = float(customer.get("multi_bank_income_share", 0.2))
    other_inflow = int(stated * share / max(1 - share, 0.1) * rng.uniform(0.9, 1.15))

    profile_before = score_customer(idbi_only_baseline(customer))
    analysis = analyze_multibank(customer, other_bank_monthly_inflow=other_inflow)
    enriched = dict(customer)
    enriched["has_other_bank_accounts"] = True
    enriched["multi_bank_income_share"] = round(
        other_inflow / max(analysis["holistic_monthly_income"], 1), 2
    )
    enriched["holistic_monthly_income"] = analysis["holistic_monthly_income"]
    profile = score_customer(enriched)

    return {
        "status": "success",
        "consent_id": consent_id,
        "income_source": "account_aggregator",
        "fetched_accounts": [
            {"fip": fip, "account_type": "Savings", "monthly_credits": other_inflow // len(consent["fip_ids"])}
            for fip in consent["fip_ids"][:2]
        ],
        "multibank_analysis": analysis,
        "rescored_profile": {
            "lead_tier": profile["lead_tier"],
            "lead_tier_css": TIER_CSS.get(profile["lead_tier"], ""),
            "composite_lead_score": profile["composite_lead_score"],
            "affordable_emi_estimate": profile.get("affordable_emi_estimate"),
            "holistic_monthly_income": profile.get("holistic_monthly_income"),
            "previous_tier": profile_before["lead_tier"],
            "previous_tier_css": TIER_CSS.get(profile_before["lead_tier"], ""),
            "previous_composite_lead_score": profile_before["composite_lead_score"],
            "tier_changed": profile_before["lead_tier"] != profile["lead_tier"],
        },
    }
