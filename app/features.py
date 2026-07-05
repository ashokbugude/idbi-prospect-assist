"""Feature extraction for ML lead scoring."""

from __future__ import annotations

import math

CREDIT_ORDINAL = {"A": 4, "B": 3, "C": 2, "D": 1, "": 2}
EMPLOYMENT_ORDINAL = {"salaried": 0, "self_employed": 1, "gig": 2}

FEATURE_NAMES: list[str] = [
    "log_monthly_income",
    "log_disposable",
    "salary_stability_months",
    "log_avg_balance",
    "need_spend_ratio",
    "luxury_spend_ratio",
    "savings_transfer_ratio",
    "salary_day_spend_ratio",
    "debt_to_income_ratio",
    "monthly_commute_spend",
    "upi_retail_transactions",
    "relationship_years",
    "age",
    "loan_page_visits_30d",
    "loan_calculator_uses",
    "bureau_enquiries_90d",
    "bureau_normalized_score",
    "credit_score_ordinal",
    "employment_ordinal",
    "upi_discipline_hint",
    "merchant_diversity_score",
    "pays_rent",
    "has_existing_home_loan",
    "has_auto_emi",
    "has_consumer_loan",
    "recent_large_debit",
    "electronics_shopping_flag",
    "festival_season_spend_spike",
    "has_other_bank_accounts",
    "multi_bank_income_share",
    "geo_transaction_consistency",
    "avg_session_minutes",
    "has_mortgage",
    "application_started",
    "window_shopping_flag",
]

FEATURE_LABELS: dict[str, str] = {
    "log_monthly_income": "Income level",
    "log_disposable": "Disposable cashflow",
    "salary_stability_months": "Salary stability",
    "log_avg_balance": "Average balance cushion",
    "need_spend_ratio": "Essential spend share",
    "luxury_spend_ratio": "Discretionary spend share",
    "savings_transfer_ratio": "Savings/investment transfers",
    "salary_day_spend_ratio": "Early-month spend intensity",
    "debt_to_income_ratio": "Debt-to-income load",
    "monthly_commute_spend": "Mobility/commute spend",
    "upi_retail_transactions": "UPI retail velocity",
    "relationship_years": "Bank relationship tenure",
    "age": "Customer age profile",
    "loan_page_visits_30d": "Loan page engagement",
    "loan_calculator_uses": "EMI calculator usage",
    "bureau_enquiries_90d": "Recent credit enquiries",
    "bureau_normalized_score": "Bureau underwriting score",
    "credit_score_ordinal": "Credit bureau band",
    "employment_ordinal": "Employment type",
    "upi_discipline_hint": "UPI spend discipline",
    "merchant_diversity_score": "UPI merchant diversity",
    "pays_rent": "Rent payment pattern",
    "has_existing_home_loan": "Existing home loan",
    "has_auto_emi": "Existing auto EMI",
    "has_consumer_loan": "Existing consumer loan",
    "recent_large_debit": "Recent large debit",
    "electronics_shopping_flag": "Electronics spend signal",
    "festival_season_spend_spike": "Seasonal spend spike",
    "has_other_bank_accounts": "Multi-bank footprint",
    "multi_bank_income_share": "Income share at other banks",
    "geo_transaction_consistency": "Geo spend consistency",
    "avg_session_minutes": "Session depth on loan journeys",
    "has_mortgage": "Existing mortgage exposure",
    "application_started": "Application started",
    "window_shopping_flag": "Window-shopping pattern",
}


def _log1p(value: float) -> float:
    return math.log1p(max(0.0, value))


def extract_features(customer: dict) -> list[float]:
    from app.enrichment import enrich_customer

    customer = enrich_customer(customer)
    income = float(customer.get("monthly_income_for_scoring") or customer.get("monthly_income", 0))
    disposable = float(customer.get("estimated_monthly_disposable", income * 0.25))
    balance = float(customer.get("avg_monthly_balance", 0))
    bureau = customer.get("bureau_analysis", {})
    upi = customer.get("upi_behavior", {})

    return [
        _log1p(income),
        _log1p(disposable),
        float(customer.get("salary_stability_months", 0)),
        _log1p(balance),
        float(customer.get("need_spend_ratio", 0.5)),
        float(customer.get("luxury_spend_ratio", 0.15)),
        float(customer.get("savings_transfer_ratio", 0.05)),
        float(customer.get("salary_day_spend_ratio", 0.5)),
        float(customer.get("debt_to_income_ratio", 0.35)),
        float(customer.get("monthly_commute_spend", 0)),
        float(customer.get("upi_retail_transactions", 0)),
        float(customer.get("relationship_years", 0)),
        float(customer.get("age", 30)),
        float(customer.get("loan_page_visits_30d", 0)),
        float(customer.get("loan_calculator_uses", 0)),
        float(customer.get("bureau_enquiries_90d", 0)),
        float(bureau.get("normalized_score", 55)),
        float(CREDIT_ORDINAL.get(customer.get("credit_score_band", "C"), 2)),
        float(EMPLOYMENT_ORDINAL.get(customer.get("employment_type", "salaried"), 0)),
        float(upi.get("discipline_hint", 50)),
        float(upi.get("merchant_diversity_score", 0.5)),
        1.0 if customer.get("pays_rent", False) else 0.0,
        1.0 if customer.get("has_existing_home_loan", False) else 0.0,
        1.0 if customer.get("has_auto_emi", False) else 0.0,
        1.0 if customer.get("has_consumer_loan", False) else 0.0,
        1.0 if customer.get("recent_large_debit", False) else 0.0,
        1.0 if customer.get("electronics_shopping_flag", False) else 0.0,
        1.0 if customer.get("festival_season_spend_spike", False) else 0.0,
        1.0 if customer.get("has_other_bank_accounts", False) else 0.0,
        float(customer.get("multi_bank_income_share", 0)),
        float(customer.get("geo_transaction_consistency", 0.7)),
        float(customer.get("avg_session_minutes", 0)),
        1.0 if customer.get("has_mortgage", False) else 0.0,
        1.0 if customer.get("application_started", False) else 0.0,
        1.0 if customer.get("window_shopping_flag", False) else 0.0,
    ]


def features_to_vector(customers: list[dict]) -> list[list[float]]:
    return [extract_features(c) for c in customers]
