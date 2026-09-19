"""Tests for hybrid ML layer — quality must not degrade."""

from __future__ import annotations

import pytest

from app.data_generator import generate_dataset
from app.ml_model import MAX_ML_NUDGE, blend_with_rules
from app.scoring import score_customer, score_customer_rules


@pytest.fixture(scope="session")
def trained_model():
    """Provided by tests/conftest.py — no-op alias for clarity."""
    yield


def test_ml_nudge_bounded(quality_customer, trained_model):
    rules = score_customer_rules(quality_customer)
    hybrid = score_customer(quality_customer, use_ml=True)
    delta = abs(hybrid["composite_lead_score"] - rules["composite_lead_score"])
    assert delta <= MAX_ML_NUDGE + 0.1
    assert hybrid.get("scoring_mode") in ("hybrid", "rules_primary", "rules_fallback")


def test_quality_leads_not_demoted(quality_customer, trained_model):
    rules = score_customer_rules(quality_customer)
    hybrid = score_customer(quality_customer, use_ml=True)
    if rules["lead_tier"] == "Quality Lead":
        assert hybrid["lead_tier"] == "Quality Lead"


def test_hybrid_improves_or_matches_window_shop_detection(trained_model):
    data = generate_dataset(500, seed=99)
    rule_windows = 0
    hybrid_windows = 0
    for c in data:
        if c.get("window_shopping_flag"):
            r = score_customer_rules(c)
            h = score_customer(c, use_ml=True)
            if r["lead_tier"] == "Window-shop Risk":
                rule_windows += 1
            if h["lead_tier"] == "Window-shop Risk":
                hybrid_windows += 1
    assert hybrid_windows >= rule_windows * 0.85


def test_blend_never_below_rules_for_serious_plus(trained_model):
    data = generate_dataset(300, seed=7)
    for c in data:
        rules = score_customer_rules(c)
        hybrid = score_customer(c, use_ml=True)
        if rules["lead_tier"] in ("Quality Lead", "Serious"):
            assert hybrid["composite_lead_score"] >= rules["composite_lead_score"] - 0.1


def test_blend_low_confidence_keeps_rules(window_shopper, trained_model):
    rules = score_customer_rules(window_shopper)
    fake_ml = {
        "enabled": True,
        "ml_composite_score": 95.0,
        "ml_tier": "Quality Lead",
        "ml_tier_probability": 0.99,
        "ml_confidence": 0.1,
        "ml_reasons": [],
    }
    out = blend_with_rules(rules, window_shopper, fake_ml)
    assert out["composite_lead_score"] == rules["composite_lead_score"]
    assert out["lead_tier"] == rules["lead_tier"]



def test_window_shop_catch_is_not_reverted_by_the_score_floor():
    """
    A confident ML risk downgrade must survive the Quality/Serious score floor.

    The floor previously restored `rule_tier` unconditionally, so the
    window-shopping catch in _safe_tier_fusion could never fire for a Serious
    lead — the branch was dead and the reported detection lift was pinned at 0%.
    """
    rule_profile = {
        "customer_id": "IDBI-L99001",
        "name": "Test Serious Browser",
        "composite_lead_score": 65.0,
        "lead_tier": "Serious",
        "top_product": "personal_loan",
        "recommended_action": "Schedule assisted journey",
        "purchase_intent": {"score": 61, "reasons": ["Deep engagement"], "details": {}},
    }
    customer = {"window_shopping_flag": True, "salary_day_spend_ratio": 0.8}
    ml = {
        "enabled": True,
        "ml_composite_score": 45.0,
        "ml_tier": "Window-shop Risk",
        "ml_tier_probability": 0.91,
        "ml_confidence": 0.8,
        "ml_reasons": ["ML: Window-shopping pattern reduces lead quality (-1.20)"],
    }

    out = blend_with_rules(dict(rule_profile), customer, ml)

    assert out["lead_tier"] == "Window-shop Risk", "the risk downgrade was reverted"
    assert out["rm_call_eligible"] is False
    # the score floor still holds for the Serious rule tier
    assert out["composite_lead_score"] >= rule_profile["composite_lead_score"]


def test_score_floor_still_protects_serious_leads_from_noise():
    """A non-risk ML disagreement must still leave a Serious lead untouched."""
    rule_profile = {
        "customer_id": "IDBI-L99002",
        "name": "Test Serious",
        "composite_lead_score": 65.0,
        "lead_tier": "Serious",
        "top_product": "personal_loan",
        "recommended_action": "Schedule assisted journey",
        "purchase_intent": {"score": 61, "reasons": ["Deep engagement"], "details": {}},
    }
    customer = {"window_shopping_flag": False, "salary_day_spend_ratio": 0.2}
    ml = {
        "enabled": True,
        "ml_composite_score": 50.0,
        "ml_tier": "Interested",
        "ml_tier_probability": 0.95,
        "ml_confidence": 0.9,
        "ml_reasons": [],
    }

    out = blend_with_rules(dict(rule_profile), customer, ml)

    assert out["lead_tier"] == "Serious"
    assert out["composite_lead_score"] == rule_profile["composite_lead_score"]
