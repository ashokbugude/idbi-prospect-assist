"""Enrich raw customer records before scoring."""

from __future__ import annotations

from app.bureau import analyze_bureau
from app.income_inference import infer_monthly_income
from app.multibank import analyze_multibank
from app.upi_signals import analyze_upi_behavior

# Metro cities — higher geo stability baseline for lending
METRO_CITIES = {"Mumbai", "Delhi", "Bengaluru", "Hyderabad", "Chennai", "Pune"}


def score_delinquency_risk(customer: dict) -> dict:
    """Future repayment stress signal from spending behaviour (AMA)."""
    score = 25.0
    reasons: list[str] = []

    day1 = customer.get("salary_day_spend_ratio", 0)
    if day1 >= 0.75:
        score += 35
        reasons.append("High day-1 salary depletion elevates delinquency risk")
    elif day1 >= 0.55:
        score += 18
        reasons.append("Early-month spend spike may precede repayment stress")

    if customer.get("debt_to_income_ratio", 0) >= 0.5:
        score += 22
        reasons.append("Elevated DTI increases 12-month stress probability")
    if customer.get("credit_score_band") == "D":
        score += 20
        reasons.append("Weak bureau band correlates with prior stress")
    if customer.get("luxury_spend_ratio", 0) > 0.25:
        score += 12
        reasons.append("Discretionary leakage reduces repayment buffer")

    upi_hint = customer.get("upi_behavior", {}).get("discipline_hint", 0)
    if upi_hint >= 65:
        score -= 8
        reasons.append("Healthy UPI spend mix lowers stress probability")
    elif upi_hint < 45:
        score += 10
        reasons.append("UPI spend pattern suggests lifestyle overstretch")

    if customer.get("savings_transfer_ratio", 0) >= 0.12:
        score -= 15
        reasons.append("Regular savings transfers mitigate delinquency risk")
    if customer.get("behavioral_discipline_hint", 0) > 60:
        score -= 10

    score = max(0, min(100, score))
    band = "Low" if score < 35 else "Medium" if score < 60 else "High"
    rag = "green" if band == "Low" else "amber" if band == "Medium" else "red"

    if not reasons:
        reasons.append("Neutral transaction pattern — standard monitoring")

    return {
        "score": round(score, 1),
        "risk_band": band,
        "rag": rag,
        "reasons": reasons[:3],
    }


def score_geo_stability(customer: dict) -> dict:
    """Geolocation / spend-location consistency from city + commute (AMA)."""
    city = customer.get("city", "")
    geo_consistency = float(customer.get("geo_transaction_consistency", 0.7))
    score = 50.0
    reasons: list[str] = []

    if city in METRO_CITIES:
        score += 15
        reasons.append(f"Metro presence ({city}) — stable economic catchment")
    if geo_consistency >= 0.8:
        score += 20
        reasons.append("UPI spend geolocation highly consistent with declared city")
    elif geo_consistency < 0.5:
        score -= 15
        reasons.append("Geographic spend mismatch — verify customer location")

    if customer.get("monthly_commute_spend", 0) >= 3000:
        score += 10
        reasons.append("Commute spend aligns with urban mobility pattern")

    score = max(0, min(100, score))
    return {
        "score": round(score, 1),
        "city": city,
        "geo_consistency": geo_consistency,
        "reasons": reasons[:2],
    }


def enrich_customer(customer: dict) -> dict:
    """Return enriched copy used by scoring engine."""
    c = dict(customer)
    income = infer_monthly_income(c)
    c.update(income)

    # Use inferred income for capacity when confidence is reasonable
    if income["income_confidence"] >= 0.55:
        c["monthly_income_for_scoring"] = income["inferred_monthly_income"]
    else:
        c["monthly_income_for_scoring"] = income["stated_monthly_income"]

    c["upi_behavior"] = analyze_upi_behavior(c)
    c["behavioral_discipline_hint"] = c["upi_behavior"]["discipline_hint"]
    c["delinquency_risk"] = score_delinquency_risk(c)
    c["geo_stability"] = score_geo_stability(c)
    c["bureau_analysis"] = analyze_bureau(c)
    c["multibank_analysis"] = analyze_multibank(c)

    holistic = c["multibank_analysis"]["holistic_monthly_income"]
    c["holistic_monthly_income"] = holistic
    if c["multibank_analysis"]["has_other_bank_accounts"]:
        c["monthly_income_for_scoring"] = max(
            c.get("monthly_income_for_scoring", income["stated_monthly_income"]),
            holistic,
        ) if income["income_confidence"] >= 0.55 else holistic

    return c
