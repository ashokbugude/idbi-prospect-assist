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
        "avg_session_minutes", "geo_transaction_consistency",
        "monthly_credit_inflow", "has_mortgage", "multi_bank_income_share",
        "upi_food_share", "active_credit_accounts", "credit_utilization_pct",
    }
    assert required.issubset(row.keys())


def test_enrichment_fields_in_profile(quality_customer):
    profile = score_customer(quality_customer)
    assert "delinquency_risk" in profile
    assert "geo_stability" in profile
    assert "income_analysis" in profile
    assert profile["income_analysis"]["inferred_monthly_income"] > 0


def test_mortgage_product_scored(quality_customer):
    profile = score_customer(quality_customer)
    products = {p["product"] for p in profile["all_scores"]}
    assert "mortgage_loan" in products


def test_delinquency_affects_high_risk_tier():
    risky = generate_customer(0, __import__("random").Random(42))
    risky.update({
        "salary_day_spend_ratio": 0.92,
        "debt_to_income_ratio": 0.62,
        "credit_score_band": "D",
        "luxury_spend_ratio": 0.35,
        "window_shopping_flag": True,
        "loan_page_visits_30d": 10,
        "application_started": False,
    })
    profile = score_customer(risky)
    assert profile["delinquency_risk"]["risk_band"] in ("Medium", "High")
    assert profile["lead_tier"] in ("Window-shop Risk", "Interested")


def test_bureau_and_upi_in_profile(quality_customer):
    profile = score_customer(quality_customer)
    assert "bureau_analysis" in profile
    assert profile["bureau_analysis"]["bureau_score"] >= 300
    assert "upi_behavior" in profile
    assert "category_shares" in profile["upi_behavior"]
    assert "rm_workflow" in profile
    assert profile["rm_workflow"]["steps"]


def test_multibank_analyze():
    from app.multibank import analyze_multibank

    c = generate_dataset(1)[0]
    c["has_other_bank_accounts"] = True
    result = analyze_multibank(c, other_bank_monthly_inflow=50000)
    assert result["holistic_monthly_income"] > result["idbi_inferred_income"]
    assert result["affordable_emi_holistic"] >= result["affordable_emi_idbi_only"]


def test_impact_has_backtest_and_scenarios():
    from app.impact import compute_business_impact, run_conversion_backtest

    impact = compute_business_impact(generate_dataset(200, seed=42))
    assert "conversion_backtest" in impact
    assert impact["proof_summary"]["backtest_quality_meets_target"] is True
    assert impact["scenario_analysis"]["conservative"]["quality_segment_pct"] >= 32
    assert impact["conversion_backtest"]["lift_vs_baseline"]["rm_queue_lift_multiplier"] > 1

    bt = run_conversion_backtest(generate_dataset(100, seed=7), trials=100)
    assert bt["strategies"]["quality_leads_only"]["mean_conversion_pct"] >= 32


def test_ml_credibility_report(trained_model):
    from app.ml_evaluation import get_ml_credibility_report

    report = get_ml_credibility_report(generate_dataset(100, seed=11))
    assert report["model_ready"] is True
    assert report["training"]["validation_score_mae"] <= 5
    assert report["credibility_checks"]["quality_never_demoted"] is True


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
    assert 0.2 <= rm_ready / len(ranked) <= 0.65
