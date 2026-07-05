"""Shared pytest fixtures."""

from __future__ import annotations

import random

import pytest

from app.data_generator import generate_customer


@pytest.fixture
def quality_customer() -> dict:
    return {
        "customer_id": "IDBI-L99999",
        "name": "Test Quality",
        "age": 35,
        "city": "Mumbai",
        "segment": "Retail Liability",
        "employment_type": "salaried",
        "monthly_income": 120000,
        "estimated_monthly_disposable": 48000,
        "salary_stability_months": 12,
        "avg_monthly_balance": 90000,
        "pays_rent": True,
        "has_existing_home_loan": False,
        "has_auto_emi": False,
        "has_consumer_loan": False,
        "monthly_commute_spend": 8000,
        "need_spend_ratio": 0.45,
        "luxury_spend_ratio": 0.08,
        "savings_transfer_ratio": 0.18,
        "salary_day_spend_ratio": 0.25,
        "debt_to_income_ratio": 0.22,
        "recent_large_debit": False,
        "relationship_years": 5,
        "electronics_shopping_flag": False,
        "festival_season_spend_spike": False,
        "upi_retail_transactions": 10,
        "credit_score_band": "A",
        "has_other_bank_accounts": True,
        "multi_bank_income_share": 0.2,
        "monthly_credit_inflow": 115000,
        "geo_transaction_consistency": 0.88,
        "bureau_enquiries_90d": 1,
        "loan_page_visits_30d": 6,
        "loan_calculator_uses": 4,
        "avg_session_minutes": 8.5,
        "application_started": True,
        "window_shopping_flag": False,
    }


@pytest.fixture
def window_shopper() -> dict:
    base = generate_customer(0, random.Random(99))
    base.update(
        {
            "loan_page_visits_30d": 12,
            "loan_calculator_uses": 3,
            "application_started": False,
            "window_shopping_flag": True,
            "estimated_monthly_disposable": 5000,
            "salary_day_spend_ratio": 0.9,
            "credit_score_band": "D",
            "debt_to_income_ratio": 0.6,
        }
    )
    return base


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
