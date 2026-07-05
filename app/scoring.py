"""Behavioral lead scoring for IDBI Prospect Assist AI (Track 02)."""

from __future__ import annotations

from dataclasses import dataclass


PRODUCTS = ("home_loan", "mortgage_loan", "auto_loan", "personal_loan", "consumer_durable")

PRODUCT_LABELS = {
    "home_loan": "Home Loan",
    "mortgage_loan": "Mortgage Loan",
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
    "mortgage_loan": 18000,
    "auto_loan": 7000,
    "personal_loan": 3500,
    "consumer_durable": 2000,
}

TARGET_QUALITY_CONVERSION_PCT = 32.0  # Hack2skill Track 02 expected outcome

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

    income = customer.get("monthly_income_for_scoring") or customer.get("monthly_income", 0)
    inferred = customer.get("inferred_monthly_income")
    if inferred and inferred != customer.get("monthly_income"):
        reasons.append(
            f"Txn-inferred income ₹{inferred:,}/mo (confidence {customer.get('income_confidence', 0):.0%})"
        )

    disposable = customer.get("estimated_monthly_disposable")
    if disposable is None:
        disposable = int(income * 0.25) if income else 0
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

    bureau = customer.get("bureau_analysis", {})
    if bureau.get("normalized_score", 0) >= 75:
        score += 12
        reasons.append(f"Strong bureau profile ({bureau.get('bureau_score', 0)} score)")
    elif bureau.get("normalized_score", 100) < 45:
        score -= 10
        reasons.append(bureau.get("underwriting_hint", "Weak bureau — capacity capped"))

    if customer.get("has_other_bank_accounts"):
        score += 8
        holistic = customer.get("holistic_monthly_income", income)
        reasons.append(f"Multi-bank holistic income view ~₹{holistic:,}/mo")

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

    upi = customer.get("upi_behavior", {})
    if upi.get("discipline_hint", 50) >= 65:
        score += 10
        if upi.get("reasons"):
            reasons.append(upi["reasons"][0])
    elif upi.get("discipline_hint", 50) < 42:
        score -= 12
        reasons.append("UPI spend mix indicates weak financial discipline")

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
    session_mins = float(customer.get("avg_session_minutes", 0))
    if session_mins >= 5 and calc >= 1:
        score += 15
        reasons.append(f"Deep engagement — avg {session_mins:.1f} min/session on loan journeys")
    elif session_mins < 1.5 and visits >= 4:
        score -= 12
        reasons.append("Shallow browsing — low time-on-site suggests window shopping")

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
            "avg_session_minutes": session_mins,
            "application_started": customer.get("application_started", False),
            "window_shopping_flag": customer.get("window_shopping_flag", False),
        },
    )


def _composite_score(
    repayment: DimensionScore,
    behavior: DimensionScore,
    intent: DimensionScore,
    customer: dict,
) -> float:
    """Four-pillar composite: repayment, intent, discipline, delinquency safety."""
    delinq = customer.get("delinquency_risk", {})
    delinq_safety = max(0, 100 - float(delinq.get("score", 25)))

    composite = (
        0.33 * repayment.score
        + 0.28 * intent.score
        + 0.22 * behavior.score
        + 0.17 * delinq_safety
    )

    bureau = customer.get("bureau_analysis", {})
    norm = bureau.get("normalized_score", 55)
    if norm >= 75:
        composite += 3
    elif norm < 45:
        composite -= 5

    return round(_clamp(composite), 1)


def assign_lead_tier(
    repayment: DimensionScore,
    behavior: DimensionScore,
    intent: DimensionScore,
    customer: dict,
) -> str:
    delinq = customer.get("delinquency_risk", {})
    delinq_band = delinq.get("risk_band", "Low")
    composite = _composite_score(repayment, behavior, intent, customer)

    if customer.get("window_shopping_flag") and intent.score < 55:
        return "Window-shop Risk"

    if delinq_band == "High" and behavior.score < 48:
        if intent.score < 40 or customer.get("window_shopping_flag"):
            return "Window-shop Risk"
        return "Interested"

    if (
        composite >= 72
        and repayment.score >= 58
        and intent.score >= 50
        and behavior.score >= 48
        and delinq_band != "High"
    ):
        return "Quality Lead"
    if composite >= 55 and repayment.score >= 42 and intent.score >= 35 and delinq_band != "High":
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


def score_mortgage_loan(customer: dict, affordable: int) -> ScoreResult:
    score = 0.0
    reasons: list[str] = []

    if not _product_eligible(customer, "mortgage_loan", affordable):
        return ScoreResult(
            "mortgage_loan",
            0.0,
            [f"Affordable EMI (~₹{affordable:,}) below mortgage threshold"],
        )

    income = customer.get("monthly_income_for_scoring") or customer.get("monthly_income", 0)
    if income >= 80000:
        score += 25
        reasons.append("Income supports mortgage refinance/top-up capacity")
    if customer.get("has_existing_home_loan") or customer.get("has_mortgage"):
        score += 30
        reasons.append("Existing housing exposure — mortgage product fit")
    if customer.get("pays_rent") and not customer.get("has_existing_home_loan"):
        score += 10
        reasons.append("Rent payer may convert to mortgage-backed housing")
    if customer.get("salary_stability_months", 0) >= 6:
        score += 15
        reasons.append("Stable income supports long-tenor mortgage")

    if not reasons:
        reasons.append("Mortgage assessed from property and cashflow signals")

    return ScoreResult("mortgage_loan", _clamp(score), reasons[:3])


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
    "mortgage_loan": score_mortgage_loan,
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
    from app.enrichment import enrich_customer

    customer = enrich_customer(customer)
    repayment = score_repayment_capacity(customer)
    behavior = score_behavioral_discipline(customer)
    intent = score_intent(customer)
    lead_tier = assign_lead_tier(repayment, behavior, intent, customer)
    affordable = _affordable_emi(customer)

    product_results = _score_products(customer, affordable)
    top = product_results[0]

    composite_lead_score = _composite_score(repayment, behavior, intent, customer)

    return {
        "customer_id": customer["customer_id"],
        "name": customer["name"],
        "city": customer["city"],
        "segment": customer.get("segment", "Retail"),
        "employment_type": customer.get("employment_type", "salaried"),
        "monthly_income": customer.get("monthly_income", 0),
        "inferred_monthly_income": customer.get("inferred_monthly_income"),
        "income_confidence": customer.get("income_confidence"),
        "holistic_monthly_income": customer.get("holistic_monthly_income"),
        "has_other_bank_accounts": customer.get("has_other_bank_accounts", False),
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
        "delinquency_risk": customer.get("delinquency_risk", {}),
        "geo_stability": customer.get("geo_stability", {}),
        "bureau_analysis": customer.get("bureau_analysis", {}),
        "upi_behavior": customer.get("upi_behavior", {}),
        "multibank_analysis": customer.get("multibank_analysis", {}),
        "income_analysis": {
            "inferred_monthly_income": customer.get("inferred_monthly_income"),
            "stated_monthly_income": customer.get("stated_monthly_income"),
            "income_confidence": customer.get("income_confidence"),
            "method": customer.get("income_inference_method"),
            "variance_pct": customer.get("income_variance_pct"),
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
        "rm_workflow": _rm_workflow(lead_tier, top.product, customer),
    }


def _rm_workflow(tier: str, product: str, customer: dict) -> dict:
    """RM-facing next steps — speaks loan officer language (AMA)."""
    product_label = PRODUCT_LABELS[product]
    delinq = customer.get("delinquency_risk", {})
    steps = {
        "Quality Lead": [
            "Priority callback within 24h",
            f"Pitch {product_label} with pre-qualified EMI capacity",
            "Share bureau + income inference summary with underwriter",
        ],
        "Serious": [
            "Schedule assisted digital journey within 48h",
            f"EMI calculator follow-up for {product_label}",
            "Confirm multi-bank income if holistic view applied",
        ],
        "Interested": [
            "Automated nurture — financial literacy + EMI nudge",
            "Re-score after 30d if application started",
        ],
        "Window-shop Risk": [
            "No RM call — deprioritize queue",
            "Send education content only",
        ],
    }
    return {
        "steps": steps.get(tier, ["Manual review"]),
        "sla_hours": 24 if tier == "Quality Lead" else 48 if tier == "Serious" else None,
        "delinquency_flag": delinq.get("rag") == "red",
        "underwriter_packet": tier in ("Quality Lead", "Serious"),
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
    """Business impact metrics — delegates to documented impact model."""
    from app.impact import compute_business_impact

    impact = compute_business_impact(customers)
    # Legacy keys used by dashboard
    impact["projected_conversion_pct"] = impact.get("rm_queue_conversion_pct", 0)
    return impact


def rank_customers(customers: list[dict]) -> list[dict]:
    scored = [score_customer(c) for c in customers]
    scored.sort(
        key=lambda c: (
            TIER_ORDER.get(c["lead_tier"], 99),
            -c["composite_lead_score"],
        )
    )
    return scored
