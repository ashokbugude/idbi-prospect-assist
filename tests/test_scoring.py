"""Unit tests for IDBI Prospect Assist AI scoring engine."""

from __future__ import annotations

import pytest

from app.data_generator import generate_customer, generate_dataset
from app.scoring import (
    LEAD_TIERS,
    rank_customers,
    score_customer,
    score_customer_rules,
)


def test_scores_stay_in_range(quality_customer):
    profile = score_customer(quality_customer)
    assert 0 <= profile["composite_lead_score"] <= 100
    assert profile["repayment_capacity"]["score"] <= 100
    assert profile["behavioral_discipline"]["score"] <= 100
    assert profile["purchase_intent"]["score"] <= 100


def test_quality_profile_tiers_well(quality_customer):
    profile = score_customer_rules(quality_customer)
    assert profile["lead_tier"] in LEAD_TIERS
    assert profile["lead_tier"] in ("Quality Lead", "Serious")
    assert len(profile["repayment_capacity"]["reasons"]) >= 2
    assert len(profile["purchase_intent"]["reasons"]) >= 1
    assert profile["all_scores"][0]["reasons"]


def test_window_shopper_demoted(window_shopper):
    profile = score_customer(window_shopper)
    assert profile["lead_tier"] in ("Window-shop Risk", "Interested")
    assert profile["recommended_action"]


def test_product_affordability_gate(window_shopper):
    profile = score_customer(window_shopper)
    for product in profile["all_scores"]:
        assert product["reasons"]


def test_ranking_is_deterministic():
    data = generate_dataset(50, seed=7)
    a = rank_customers(data)
    b = rank_customers(data)
    assert [c["customer_id"] for c in a] == [c["customer_id"] for c in b]


def test_dataset_has_required_fields():
    row = generate_dataset(1)[0]
    required = {
        "customer_id", "employment_type", "estimated_monthly_disposable",
        "window_shopping_flag", "loan_page_visits_30d", "credit_score_band",
    }
    assert required.issubset(row.keys())


def test_missing_fields_use_defaults():
    minimal = {
        "customer_id": "X1",
        "name": "Min",
        "city": "Pune",
        "monthly_income": 40000,
    }
    profile = score_customer(minimal)
    assert profile["lead_tier"] in LEAD_TIERS


def test_impact_distribution_realistic():
    ranked = rank_customers(generate_dataset(200, seed=42))
    tiers = {t: sum(1 for c in ranked if c["lead_tier"] == t) for t in LEAD_TIERS}
    assert tiers["Quality Lead"] >= 1
    assert tiers["Window-shop Risk"] >= 1
    rm_ready = tiers["Quality Lead"] + tiers["Serious"]
    assert rm_ready < len(ranked) * 0.5
