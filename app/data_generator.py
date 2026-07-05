"""Generate synthetic IDBI liability customer profiles for round-1 prototype."""

from __future__ import annotations

import json
import random
from pathlib import Path

CITIES = [
    "Mumbai", "Pune", "Delhi", "Bengaluru", "Hyderabad",
    "Chennai", "Ahmedabad", "Jaipur", "Lucknow", "Indore",
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
BUSINESS_TYPES = ("retail_trade", "services", "professional", "manufacturing", "gig_platform")

# Target tier mix for realistic RM queue (~25%) and window-shop (~30%)
ARCHETYPE_WEIGHTS = (
    ("quality", 0.12),
    ("serious", 0.13),
    ("interested", 0.50),
    ("window_shop", 0.25),
)


def _estimate_disposable(
    monthly_income: int,
    need_ratio: float,
    luxury_ratio: float,
    dti: float,
    savings_ratio: float,
    employment_type: str,
) -> int:
    base = monthly_income * (1 - need_ratio - luxury_ratio - dti * 0.5)
    if employment_type in ("self_employed", "gig"):
        base *= 0.85
    base += monthly_income * savings_ratio * 0.3
    return max(0, int(base))


def _pick_archetype(rng: random.Random) -> str:
    roll = rng.random()
    cumulative = 0.0
    for name, weight in ARCHETYPE_WEIGHTS:
        cumulative += weight
        if roll <= cumulative:
            return name
    return "interested"


def _apply_archetype(fields: dict, archetype: str, rng: random.Random) -> None:
    if archetype == "quality":
        fields.update({
            "monthly_income": rng.choice([68000, 82000, 95000, 120000, 150000]),
            "need_spend_ratio": round(rng.uniform(0.38, 0.48), 2),
            "luxury_spend_ratio": round(rng.uniform(0.05, 0.12), 2),
            "savings_transfer_ratio": round(rng.uniform(0.12, 0.28), 2),
            "salary_day_spend_ratio": round(rng.uniform(0.15, 0.38), 2),
            "debt_to_income_ratio": round(rng.uniform(0.1, 0.32), 2),
            "credit_score_band": rng.choices(["A", "B", "C"], weights=[40, 45, 15])[0],
            "loan_page_visits_30d": rng.randint(3, 10),
            "loan_calculator_uses": rng.randint(2, 6),
            "avg_session_minutes": round(rng.uniform(4.0, 12.0), 1),
            "application_started": rng.random() < 0.55,
            "window_shopping_flag": False,
            "salary_stability_months": rng.randint(8, 18),
        })
    elif archetype == "serious":
        fields.update({
            "need_spend_ratio": round(rng.uniform(0.42, 0.55), 2),
            "luxury_spend_ratio": round(rng.uniform(0.08, 0.18), 2),
            "savings_transfer_ratio": round(rng.uniform(0.06, 0.18), 2),
            "salary_day_spend_ratio": round(rng.uniform(0.25, 0.52), 2),
            "debt_to_income_ratio": round(rng.uniform(0.2, 0.42), 2),
            "credit_score_band": rng.choices(["A", "B", "C"], weights=[20, 50, 30])[0],
            "loan_page_visits_30d": rng.randint(2, 8),
            "loan_calculator_uses": rng.randint(1, 4),
            "avg_session_minutes": round(rng.uniform(2.5, 7.0), 1),
            "application_started": rng.random() < 0.28,
            "window_shopping_flag": False,
        })
    elif archetype == "window_shop":
        fields.update({
            "need_spend_ratio": round(rng.uniform(0.45, 0.62), 2),
            "luxury_spend_ratio": round(rng.uniform(0.18, 0.35), 2),
            "savings_transfer_ratio": round(rng.uniform(0.01, 0.06), 2),
            "salary_day_spend_ratio": round(rng.uniform(0.65, 0.95), 2),
            "debt_to_income_ratio": round(rng.uniform(0.35, 0.65), 2),
            "credit_score_band": rng.choices(["B", "C", "D"], weights=[25, 45, 30])[0],
            "loan_page_visits_30d": rng.randint(6, 18),
            "loan_calculator_uses": rng.randint(0, 2),
            "avg_session_minutes": round(rng.uniform(0.5, 2.5), 1),
            "application_started": False,
            "window_shopping_flag": True,
            "bureau_enquiries_90d": rng.randint(3, 6),
        })
    else:  # interested
        fields.update({
            "need_spend_ratio": round(rng.uniform(0.40, 0.58), 2),
            "luxury_spend_ratio": round(rng.uniform(0.10, 0.25), 2),
            "savings_transfer_ratio": round(rng.uniform(0.03, 0.14), 2),
            "salary_day_spend_ratio": round(rng.uniform(0.35, 0.65), 2),
            "debt_to_income_ratio": round(rng.uniform(0.25, 0.50), 2),
            "loan_page_visits_30d": rng.randint(1, 6),
            "loan_calculator_uses": rng.randint(0, 3),
            "avg_session_minutes": round(rng.uniform(1.5, 5.0), 1),
            "application_started": rng.random() < 0.12,
            "window_shopping_flag": rng.random() < 0.15,
        })


def generate_customer(index: int, rng: random.Random) -> dict:
    archetype = _pick_archetype(rng)
    age = rng.randint(24, 55)
    employment_type = rng.choices(EMPLOYMENT_TYPES, weights=[58, 30, 12])[0]
    if archetype == "window_shop" and rng.random() < 0.4:
        employment_type = rng.choice(["gig", "self_employed"])

    monthly_income = rng.choice([28000, 35000, 45000, 55000, 68000, 82000, 95000, 120000])
    if employment_type == "gig":
        monthly_income = int(monthly_income * rng.uniform(0.75, 1.1))
    elif employment_type == "self_employed":
        monthly_income = int(monthly_income * rng.uniform(0.95, 1.35))

    business_type = rng.choice(BUSINESS_TYPES) if employment_type in ("self_employed", "gig") else None

    fields: dict = {
        "monthly_income": monthly_income,
        "need_spend_ratio": round(rng.uniform(0.38, 0.62), 2),
        "luxury_spend_ratio": round(rng.uniform(0.05, 0.32), 2),
        "savings_transfer_ratio": round(rng.uniform(0.02, 0.28), 2),
        "salary_day_spend_ratio": round(rng.uniform(0.15, 0.95), 2),
        "debt_to_income_ratio": round(rng.uniform(0.1, 0.65), 2),
        "credit_score_band": rng.choices(["A", "B", "C", "D"], weights=[15, 35, 35, 15])[0],
        "loan_page_visits_30d": rng.randint(0, 18),
        "loan_calculator_uses": rng.randint(0, 8),
        "avg_session_minutes": round(rng.uniform(0.5, 12.0), 1),
        "application_started": rng.random() < 0.22,
        "window_shopping_flag": False,
        "salary_stability_months": rng.randint(2, 18),
    }
    _apply_archetype(fields, archetype, rng)

    need_spend_ratio = fields["need_spend_ratio"]
    luxury_spend_ratio = fields["luxury_spend_ratio"]
    want_spend_ratio = round(max(0, 1 - need_spend_ratio - luxury_spend_ratio), 2)
    savings_transfer_ratio = fields["savings_transfer_ratio"]
    salary_day_spend_ratio = fields["salary_day_spend_ratio"]
    dti = fields["debt_to_income_ratio"]
    monthly_income = fields.get("monthly_income", monthly_income)

    salary_stability = fields["salary_stability_months"]
    avg_balance = int(monthly_income * rng.uniform(0.2, 2.2))
    pays_rent = rng.random() < 0.55
    has_home = rng.random() < 0.22
    has_auto = rng.random() < 0.18
    has_consumer = rng.random() < 0.12
    credit_band = fields["credit_score_band"]

    loan_page_visits = fields["loan_page_visits_30d"]
    calculator_uses = fields["loan_calculator_uses"]
    avg_session_minutes = fields["avg_session_minutes"]
    application_started = fields["application_started"]
    window_shopping = fields["window_shopping_flag"]

    city = rng.choice(CITIES)
    has_other_bank = rng.random() < 0.38
    multi_bank_share = round(rng.uniform(0.05, 0.35), 2) if has_other_bank else 0.0
    monthly_credit_inflow = int(monthly_income * rng.uniform(0.85, 1.15))
    geo_consistency = round(rng.uniform(0.45, 0.98), 2)
    has_mortgage = rng.random() < 0.15

    active_credit_accounts = rng.randint(0, 5)
    credit_utilization = round(rng.uniform(0.1, 0.85), 2)
    bureau_history_months = rng.randint(6, 84)

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
        "business_type": business_type,
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
        "want_spend_ratio": want_spend_ratio,
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
        "bureau_enquiries_90d": fields.get("bureau_enquiries_90d", rng.randint(0, 6)),
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
        "_archetype": archetype,
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
