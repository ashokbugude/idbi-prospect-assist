"""Generate synthetic IDBI liability customer profiles for round-1 prototype."""

from __future__ import annotations

import json
import random
from pathlib import Path

CITIES = [
    "Mumbai",
    "Pune",
    "Delhi",
    "Bengaluru",
    "Hyderabad",
    "Chennai",
    "Ahmedabad",
    "Jaipur",
    "Lucknow",
    "Indore",
]

FIRST_NAMES = [
    "Aarav", "Priya", "Rohan", "Sneha", "Karthik", "Ananya", "Vikram",
    "Meera", "Arjun", "Divya", "Suresh", "Kavya", "Rahul", "Pooja", "Nikhil",
]

LAST_NAMES = [
    "Sharma", "Patel", "Iyer", "Reddy", "Gupta", "Nair", "Singh",
    "Desai", "Menon", "Kulkarni",
]

EMPLOYMENT_TYPES = ("salaried", "self_employed", "gig")


def _estimate_disposable(
    monthly_income: int,
    need_ratio: float,
    luxury_ratio: float,
    dti: float,
    savings_ratio: float,
    employment_type: str,
) -> int:
    """Approximate retained monthly capacity after needs and obligations."""
    base = monthly_income * (1 - need_ratio - luxury_ratio - dti * 0.5)
    if employment_type in ("self_employed", "gig"):
        base *= 0.85
    base += monthly_income * savings_ratio * 0.3
    return max(0, int(base))


def generate_customer(index: int, rng: random.Random) -> dict:
    age = rng.randint(24, 55)
    employment_type = rng.choices(EMPLOYMENT_TYPES, weights=[62, 28, 10])[0]
    monthly_income = rng.choice(
        [28000, 35000, 45000, 55000, 68000, 82000, 95000, 120000, 150000]
    )
    if employment_type == "gig":
        monthly_income = int(monthly_income * rng.uniform(0.75, 1.15))
    elif employment_type == "self_employed":
        monthly_income = int(monthly_income * rng.uniform(0.9, 1.4))

    salary_stability = rng.randint(2, 18)
    need_spend_ratio = round(rng.uniform(0.38, 0.62), 2)
    luxury_spend_ratio = round(rng.uniform(0.05, 0.32), 2)
    savings_transfer_ratio = round(rng.uniform(0.02, 0.28), 2)
    salary_day_spend_ratio = round(rng.uniform(0.15, 0.95), 2)
    dti = round(rng.uniform(0.1, 0.65), 2)

    avg_balance = int(monthly_income * rng.uniform(0.2, 2.2))
    pays_rent = rng.random() < 0.55
    has_home = rng.random() < 0.22
    has_auto = rng.random() < 0.18
    has_consumer = rng.random() < 0.12
    credit_band = rng.choices(["A", "B", "C", "D"], weights=[15, 35, 35, 15])[0]

    loan_page_visits = rng.randint(0, 18)
    calculator_uses = rng.randint(0, 8)
    avg_session_minutes = round(rng.uniform(0.5, 12.0), 1)
    application_started = rng.random() < 0.22
    window_shopping = (
        loan_page_visits >= 5
        and calculator_uses >= 2
        and not application_started
        and avg_session_minutes < 3.0
        and rng.random() < 0.55
    )
    city = rng.choice(CITIES)
    has_other_bank = rng.random() < 0.38
    multi_bank_share = round(rng.uniform(0.05, 0.35), 2) if has_other_bank else 0.0
    monthly_credit_inflow = int(monthly_income * rng.uniform(0.85, 1.15))
    geo_consistency = round(rng.uniform(0.45, 0.98), 2)
    has_mortgage = rng.random() < 0.15

    # Bureau depth (synthetic sandbox fields)
    active_credit_accounts = rng.randint(0, 5)
    credit_utilization = round(rng.uniform(0.1, 0.85), 2)
    bureau_history_months = rng.randint(6, 84)

    # UPI merchant-category mix (sums ~1.0)
    food = round(rng.uniform(0.12, 0.35), 3)
    mobility = round(rng.uniform(0.08, 0.25), 3)
    retail = round(rng.uniform(0.1, 0.3), 3)
    entertainment = round(rng.uniform(0.03, 0.2), 3)
    utilities = round(rng.uniform(0.1, 0.28), 3)
    upi_total = food + mobility + retail + entertainment + utilities
    food, mobility, retail, entertainment, utilities = (
        round(food / upi_total, 3),
        round(mobility / upi_total, 3),
        round(retail / upi_total, 3),
        round(entertainment / upi_total, 3),
        round(utilities / upi_total, 3),
    )

    disposable = _estimate_disposable(
        monthly_income, need_spend_ratio, luxury_spend_ratio, dti,
        savings_transfer_ratio, employment_type,
    )

    return {
        "customer_id": f"IDBI-L{10000 + index}",
        "name": f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}",
        "age": age,
        "city": city,
        "segment": "Retail Liability",
        "employment_type": employment_type,
        "monthly_income": monthly_income,
        "estimated_monthly_disposable": disposable,
        "salary_stability_months": salary_stability,
        "avg_monthly_balance": avg_balance,
        "pays_rent": pays_rent,
        "has_existing_home_loan": has_home,
        "has_mortgage": has_mortgage,
        "has_auto_emi": has_auto,
        "has_consumer_loan": has_consumer,
        "monthly_commute_spend": rng.randint(1500, 12000),
        "need_spend_ratio": need_spend_ratio,
        "luxury_spend_ratio": luxury_spend_ratio,
        "savings_transfer_ratio": savings_transfer_ratio,
        "salary_day_spend_ratio": salary_day_spend_ratio,
        "discretionary_spend_ratio": luxury_spend_ratio,
        "debt_to_income_ratio": dti,
        "recent_large_debit": rng.random() < 0.25,
        "relationship_years": rng.randint(1, 12),
        "electronics_shopping_flag": rng.random() < 0.3,
        "festival_season_spend_spike": rng.random() < 0.35,
        "upi_retail_transactions": rng.randint(2, 25),
        "credit_score_band": credit_band,
        "has_other_bank_accounts": has_other_bank,
        "multi_bank_income_share": multi_bank_share,
        "monthly_credit_inflow": monthly_credit_inflow,
        "geo_transaction_consistency": geo_consistency,
        "avg_session_minutes": avg_session_minutes,
        "bureau_enquiries_90d": rng.randint(0, 6),
        "active_credit_accounts": active_credit_accounts,
        "credit_utilization_pct": credit_utilization,
        "bureau_repayment_history_months": bureau_history_months,
        "upi_food_share": food,
        "upi_mobility_share": mobility,
        "upi_retail_share": retail,
        "upi_entertainment_share": entertainment,
        "upi_utilities_share": utilities,
        "loan_page_visits_30d": loan_page_visits,
        "loan_calculator_uses": calculator_uses,
        "application_started": application_started,
        "window_shopping_flag": window_shopping,
    }


def generate_dataset(count: int = 200, seed: int = 42) -> list[dict]:
    rng = random.Random(seed)
    return [generate_customer(i, rng) for i in range(count)]


def save_dataset(path: Path, count: int = 200) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = generate_dataset(count)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


if __name__ == "__main__":
    out = Path(__file__).resolve().parent / "data" / "customers.json"
    save_dataset(out)
    print(f"Wrote {out}")
