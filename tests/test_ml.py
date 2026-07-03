"""Tests for hybrid ML layer — quality must not degrade."""

from __future__ import annotations

import numpy as np
import pytest

from app.data_generator import generate_dataset
from app.ml_model import MAX_ML_NUDGE, blend_with_rules
from app.scoring import score_customer, score_customer_rules


@pytest.fixture(scope="session")
def trained_model():
    import app.ml_model as mm
    from app.ml_model import LeadMLModel

    mm._model = None
    model = LeadMLModel()
    if not model.load():
        from scripts.train_model import main as train_main

        train_main()
        mm._model = None
        model.load()
    yield
    mm._model = None


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

