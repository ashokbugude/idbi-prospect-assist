"""Behavioral lead scoring for IDBI Prospect Assist AI (Track 02)."""

from __future__ import annotations

from dataclasses import dataclass


PRODUCTS = ("home_loan", "auto_loan", "personal_loan", "consumer_durable")

PRODUCT_LABELS = {
    "home_loan": "Home Loan",
    "auto_loan": "Auto Loan",
    "personal_loan": "Personal Loan",
    "consumer_durable": "Consumer Durable Loan",
}

LEAD_TIERS = ("Quality Lead", "Serious", "Interested", "Window-shop Risk")

TIER_ORDER = {tier: idx for idx, tier in enumerate(LEAD_TIERS)}

TIER_CSS = {
    "Quality Lead": "quality-lead",
    "Serious": "serious",
    "Interested": "interested",
    "Window-shop Risk": "window-shop-risk",
}

# Minimum indicative EMI capacity required per product (₹/month).
PRODUCT_MIN_EMI = {
    "home_loan": 15000,
    "auto_loan": 7000,
    "personal_loan": 3500,
    "consumer_durable": 2000,
}

BASELINE_CONVERSION_RATE = 0.01  # IDBI stated ~1% lead conversion today


@dataclass
class DimensionScore:
    name: str
    score: float
    reasons: list[str]
    details: dict


@dataclass
class ScoreResult:
    product: str
    score: float
    reasons: list[str]


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def score_repayment_capacity(customer: dict) -> DimensionScore:
    score = 0.0
    reasons: list[str] = []

    disposable = customer.get("estimated_monthly_disposable")
    if disposable is None:
        income = customer.get("monthly_income", 0)
        disposable = int(income * 0.25) if income else 0
    income = customer.get("monthly_income", 1)
    disposable_ratio = disposable / income if income else 0

    if disposable_ratio >= 0.35:
        score += 30
        reasons.append(f"Strong disposable income (~₹{disposable:,}/mo retained after needs)")
    elif disposable_ratio >= 0.2:
        score += 18
        reasons.append(f"Moderate disposable capacity (~₹{disposable:,}/mo)")
    else:
        score += 6
        reasons.append("Thin disposable income after mandatory spends")

    dti = customer.get("debt_to_income_ratio", 0)
    if dti <= 0.3:
        score += 25
        reasons.append("Low existing debt burden supports new EMI")
    elif dti <= 0.45:
        score += 14
        reasons.append("Manageable debt-to-income ratio")
    else:
        score += 4
        reasons.append("High debt obligations limit repayment headroom")

    savings_ratio = customer.get("savings_transfer_ratio", 0)
    if savings_ratio >= 0.15:
        score += 20
        reasons.append("Regular transfers to savings/investments indicate retained income")
    elif savings_ratio >= 0.08:
        score += 10
        reasons.append("Some savings discipline observed in cashflows")

    employment = customer.get("employment_type", "salaried")
    if employment == "salaried" and customer.get("salary_stability_months", 0) >= 6:
        score += 15
        reasons.append("Stable salaried credits improve repayment predictability")
    elif employment == "self_employed":
        score += 10
        reasons.append("Self-employed inflows require margin-based capacity view")
    elif employment == "gig":
        score += 5
        reasons.append("Gig income volatility needs conservative EMI sizing")

    if customer.get("credit_score_band", "C") in ("A", "B"):
        score += 10
        reasons.append("Favorable bureau/credit band")

    if customer.get("has_other_bank_accounts"):
        score += 8
        reasons.append("Multi-account view enables holistic repayment assessment")

    affordable_emi = int(disposable * 0.45)
    return DimensionScore(
        name="Repayment Capacity",
        score=_clamp(score),
        reasons=reasons[:4],
        details={
            "estimated_monthly_disposable": disposable,
            "affordable_emi_estimate": affordable_emi,
            "debt_to_income_ratio": dti,
        },
    )


def score_behavioral_discipline(customer: dict) -> DimensionScore:
    score = 50.0
    reasons: list[str] = []

    day1_ratio = customer.get("salary_day_spend_ratio", 0)
    if day1_ratio >= 0.75:
        score -= 25
        reasons.append("Spends most of salary within 1–2 days — weak financial discipline")
    elif day1_ratio >= 0.5:
        score -= 12
        reasons.append("High early-month spend pattern detected")
    else:
        score += 15
        reasons.append("Salary utilization spread across month — disciplined pattern")

    luxury = customer.get("luxury_spend_ratio", 0)
    need = customer.get("need_spend_ratio", 0)
    if luxury > 0.22 and customer.get("avg_monthly_balance", 0) < customer.get("monthly_income", 0) * 0.3:
        score -= 15
        reasons.append("Luxury spend high relative to balance buffer")
    elif luxury <= 0.15:
        score += 12
        reasons.append("Needs-focused spending with limited discretionary leakage")

    if customer.get("savings_transfer_ratio", 0) >= 0.12:
        score += 15
        reasons.append("Consistent savings/investment transfers")

    if customer.get("credit_score_band") == "D":
        score -= 18
        reasons.append("Weak credit band signals prior repayment stress")
    elif customer.get("credit_score_band") == "A":
        score += 12
        reasons.append("Strong credit discipline from bureau signals")

    if customer.get("bureau_enquiries_90d", 0) >= 4:
        score -= 10
        reasons.append("Multiple recent credit enquiries — possible rate shopping")

    balance = customer.get("avg_monthly_balance", 0)
    income = customer.get("monthly_income", 1)
    if balance >= income * 0.5:
        score += 10
        reasons.append("Healthy average balance cushion")

    return DimensionScore(
        name="Behavioral Discipline",
        score=_clamp(score),
        reasons=reasons[:4],
        details={
            "salary_day_spend_ratio": day1_ratio,
            "need_vs_luxury": f"{need:.0%} needs / {luxury:.0%} discretionary",
        },
    )


def score_intent(customer: dict) -> DimensionScore:
    score = 0.0
    reasons: list[str] = []

    if customer.get("application_started"):
        score += 40
        reasons.append("Loan application started — high purchase intent")
    elif customer.get("loan_calculator_uses", 0) >= 3:
        score += 28
        reasons.append("Repeated EMI calculator usage signals active evaluation")
    elif customer.get("loan_page_visits_30d", 0) >= 2:
        score += 15
        reasons.append("Multiple loan product page visits in last 30 days")

    if customer.get("recent_large_debit"):
        score += 18
        reasons.append("Recent large debit may indicate imminent funding need")

    if customer.get("window_shopping_flag"):
        score -= 30
        reasons.append("Browsing without application — possible window shopping")

    visits = customer.get("loan_page_visits_30d", 0)
    calc = customer.get("loan_calculator_uses", 0)
    if visits >= 8 and calc == 0 and not customer.get("application_started"):
        score -= 15
        reasons.append("High page views with no calculator use — low seriousness")

    relationship = customer.get("relationship_years", 0)
    if relationship >= 3:
        score += 10
        reasons.append("Established liability relationship increases conversion potential")

    if not reasons:
        reasons.append("Limited digital intent signals — rely on transaction behavior")

    return DimensionScore(
        name="Purchase Intent",
        score=_clamp(score),
        reasons=reasons[:4],
        details={
            "loan_page_visits_30d": visits,
            "loan_calculator_uses": calc,
            "application_started": customer.get("application_started", False),
            "window_shopping_flag": customer.get("window_shopping_flag", False),
        },
    )


def assign_lead_tier(
    repayment: DimensionScore,
    behavior: DimensionScore,
    intent: DimensionScore,
    customer: dict,
) -> str:
    if customer.get("window_shopping_flag") and intent.score < 55:
        return "Window-shop Risk"

    composite = (
        0.40 * repayment.score
        + 0.35 * intent.score
        + 0.25 * behavior.score
    )

    if (
        composite >= 72
        and repayment.score >= 58
        and intent.score >= 50
        and behavior.score >= 48
    ):
        return "Quality Lead"
    if composite >= 55 and repayment.score >= 42 and intent.score >= 35:
        return "Serious"
    if composite >= 32:
        return "Interested"
    return "Window-shop Risk"


def _affordable_emi(customer: dict) -> int:
    disposable = customer.get("estimated_monthly_disposable", 0)
    if disposable <= 0 and customer.get("monthly_income"):
        disposable = int(customer["monthly_income"] * 0.2)
    return int(disposable * 0.45)


def _product_eligible(customer: dict, product: str, affordable: int) -> bool:
    return affordable >= PRODUCT_MIN_EMI.get(product, 0)


def score_home_loan(customer: dict, affordable: int) -> ScoreResult:
    score = 0.0
    reasons: list[str] = []

    if not _product_eligible(customer, "home_loan", affordable):
        return ScoreResult(
            "home_loan",
            0.0,
            [f"Affordable EMI (~₹{affordable:,}) below home loan threshold"],
        )

    if customer.get("salary_stability_months", 0) >= 6:
        score += 25
        reasons.append(f"Stable salary credits for {customer['salary_stability_months']} months")
    elif customer.get("salary_stability_months", 0) >= 3:
        score += 12
        reasons.append("Emerging salary stability pattern")

    if customer.get("avg_monthly_balance", 0) >= 80000:
        score += 20
        reasons.append("Balance supports home loan EMI capacity")
    if customer.get("pays_rent"):
        score += 15
        reasons.append("Rent outflows suggest housing upgrade need")
    if 28 <= customer.get("age", 0) <= 50:
        score += 15
        reasons.append("Age profile fits home loan eligibility")
    if not customer.get("has_existing_home_loan"):
        score += 15
        reasons.append("No existing home loan exposure")
    else:
        score -= 20
        reasons.append("Existing home loan reduces cross-sell fit")

    if not reasons:
        reasons.append("General liability profile reviewed for housing need")

    return ScoreResult("home_loan", _clamp(score), reasons[:3])


def score_auto_loan(customer: dict, affordable: int) -> ScoreResult:
    score = 0.0
    reasons: list[str] = []

    if not _product_eligible(customer, "auto_loan", affordable):
        return ScoreResult(
            "auto_loan",
            0.0,
            [f"Affordable EMI (~₹{affordable:,}) below auto loan threshold"],
        )

    if customer.get("monthly_income", 0) >= 50000:
        score += 25
        reasons.append("Income supports auto loan EMI")
    elif customer.get("monthly_income", 0) >= 30000:
        score += 15
        reasons.append("Income supports entry-level vehicle financing")
    if not customer.get("has_auto_emi"):
        score += 25
        reasons.append("No active auto loan EMI")
    else:
        score -= 10
        reasons.append("Existing auto EMI on books")
    if customer.get("monthly_commute_spend", 0) >= 5000:
        score += 20
        reasons.append("High commute spend suggests vehicle need")

    if not reasons:
        reasons.append("Auto loan fit assessed from mobility spend")

    return ScoreResult("auto_loan", _clamp(score), reasons[:3])


def score_personal_loan(customer: dict, affordable: int) -> ScoreResult:
    score = 0.0
    reasons: list[str] = []

    if not _product_eligible(customer, "personal_loan", affordable):
        return ScoreResult(
            "personal_loan",
            0.0,
            [f"Affordable EMI (~₹{affordable:,}) below personal loan threshold"],
        )

    if customer.get("debt_to_income_ratio", 0) <= 0.35:
        score += 25
        reasons.append("Low DTI suitable for personal loan")
    if customer.get("recent_large_debit"):
        score += 20
        reasons.append("Recent large debit indicates liquidity need")
    if customer.get("relationship_years", 0) >= 2:
        score += 15
        reasons.append("Established bank relationship")

    if not reasons:
        reasons.append("Short-term credit need possible from cashflow pattern")

    return ScoreResult("personal_loan", _clamp(score), reasons[:3])


def score_consumer_durable(customer: dict, affordable: int) -> ScoreResult:
    score = 0.0
    reasons: list[str] = []

    if not _product_eligible(customer, "consumer_durable", affordable):
        return ScoreResult(
            "consumer_durable",
            0.0,
            [f"Affordable EMI (~₹{affordable:,}) below consumer loan threshold"],
        )

    if customer.get("electronics_shopping_flag"):
        score += 30
        reasons.append("Electronics retail spend pattern")
    if customer.get("festival_season_spend_spike"):
        score += 20
        reasons.append("Seasonal spend spike")
    if customer.get("upi_retail_transactions", 0) >= 8:
        score += 15
        reasons.append("Frequent UPI retail transactions")

    if not reasons:
        reasons.append("Retail transaction velocity supports durable financing")

    return ScoreResult("consumer_durable", _clamp(score), reasons[:3])


SCORERS = {
    "home_loan": score_home_loan,
    "auto_loan": score_auto_loan,
    "personal_loan": score_personal_loan,
    "consumer_durable": score_consumer_durable,
}


def _score_products(customer: dict, affordable: int) -> list[ScoreResult]:
    results = [scorer(customer, affordable) for scorer in SCORERS.values()]
    results.sort(key=lambda r: r.score, reverse=True)
    return results


def score_customer_rules(customer: dict) -> dict:
    """Rule-based scoring only — used as ML teacher labels and safe fallback."""
    repayment = score_repayment_capacity(customer)
    behavior = score_behavioral_discipline(customer)
    intent = score_intent(customer)
    lead_tier = assign_lead_tier(repayment, behavior, intent, customer)
    affordable = _affordable_emi(customer)

    product_results = _score_products(customer, affordable)
    top = product_results[0]

    composite_lead_score = round(
        0.40 * repayment.score + 0.35 * intent.score + 0.25 * behavior.score,
        1,
    )

    return {
        "customer_id": customer["customer_id"],
        "name": customer["name"],
        "city": customer["city"],
        "segment": customer.get("segment", "Retail"),
        "employment_type": customer.get("employment_type", "salaried"),
        "monthly_income": customer.get("monthly_income", 0),
        "affordable_emi_estimate": affordable,
        "lead_tier": lead_tier,
        "lead_tier_css": TIER_CSS[lead_tier],
        "composite_lead_score": composite_lead_score,
        "repayment_capacity": {
            "score": round(repayment.score, 1),
            "reasons": repayment.reasons,
            "details": repayment.details,
        },
        "behavioral_discipline": {
            "score": round(behavior.score, 1),
            "reasons": behavior.reasons,
            "details": behavior.details,
        },
        "purchase_intent": {
            "score": round(intent.score, 1),
            "reasons": intent.reasons,
            "details": intent.details,
        },
        "top_product": top.product,
        "top_product_label": PRODUCT_LABELS[top.product],
        "top_score": round(top.score, 1),
        "all_scores": [
            {
                "product": r.product,
                "label": PRODUCT_LABELS[r.product],
                "score": round(r.score, 1),
                "reasons": r.reasons,
                "eligible": r.score > 0,
            }
            for r in product_results
        ],
        "recommended_action": _recommended_action(lead_tier, top.product),
        "lead_priority": lead_tier,
        "rm_call_eligible": lead_tier in ("Quality Lead", "Serious"),
    }


def score_customer(customer: dict, use_ml: bool = True) -> dict:
    """Hybrid scoring: rules first, XGBoost nudges when confident."""
    rule_profile = score_customer_rules(customer)
    if not use_ml:
        rule_profile["scoring_mode"] = "rules_only"
        return rule_profile

    from app.ml_model import blend_with_rules, get_model

    try:
        model = get_model()
        if not model.is_ready:
            rule_profile["scoring_mode"] = "rules_only"
            rule_profile["ml_enhancement"] = {"enabled": False, "reason": "model_not_trained"}
            return rule_profile
        ml = model.predict(customer)
        return blend_with_rules(rule_profile, customer, ml)
    except Exception:
        rule_profile["scoring_mode"] = "rules_fallback"
        rule_profile["ml_enhancement"] = {"enabled": False, "error": "model_unavailable"}
        return rule_profile


def _recommended_action(tier: str, product: str) -> str:
    product_label = PRODUCT_LABELS[product]
    if tier == "Window-shop Risk":
        return "Deprioritize — send financial literacy content, no RM call"
    actions = {
        "Quality Lead": f"Priority RM callback within 24h — pitch {product_label}",
        "Serious": f"Schedule assisted journey for {product_label}",
        "Interested": f"Nurture with EMI calculator follow-up for {product_label}",
    }
    return actions.get(tier, "Review manually")


def compute_impact_metrics(customers: list[dict]) -> dict:
    """Simulate operational lift vs IDBI's ~1% baseline conversion."""
    ranked = rank_customers(customers)
    total = len(ranked)
    if total == 0:
        return {}

    quality = sum(1 for c in ranked if c["lead_tier"] == "Quality Lead")
    serious = sum(1 for c in ranked if c["lead_tier"] == "Serious")
    window = sum(1 for c in ranked if c["lead_tier"] == "Window-shop Risk")
    rm_queue = quality + serious

    # Illustrative projected conversion on RM-actionable queue only.
    projected_rate = min(
        0.38,
        BASELINE_CONVERSION_RATE
        + (quality / total) * 0.28
        + (serious / total) * 0.12,
    )

    return {
        "total_leads": total,
        "baseline_conversion_pct": round(BASELINE_CONVERSION_RATE * 100, 1),
        "projected_conversion_pct": round(projected_rate * 100, 1),
        "rm_actionable_leads": rm_queue,
        "rm_queue_pct": round(rm_queue / total * 100, 1),
        "window_shop_filtered_pct": round(window / total * 100, 1),
        "estimated_rm_time_saved_pct": round(window / total * 100 * 0.7, 1),
        "tier_distribution": {
            t: sum(1 for c in ranked if c["lead_tier"] == t) for t in LEAD_TIERS
        },
    }


def rank_customers(customers: list[dict]) -> list[dict]:
    scored = [score_customer(c) for c in customers]
    scored.sort(
        key=lambda c: (
            TIER_ORDER.get(c["lead_tier"], 99),
            -c["composite_lead_score"],
        )
    )
    return scored
