"""Infer actual income from transaction behaviour (Track 02 AMA requirement)."""

from __future__ import annotations


def infer_monthly_income(customer: dict) -> dict:
    """
    Estimate real income from cashflows — not only stated salary.
    Returns inferred income, confidence, and method notes.
    """
    stated = int(customer.get("monthly_income", 0))
    employment = customer.get("employment_type", "salaried")
    balance = int(customer.get("avg_monthly_balance", 0))
    savings_ratio = float(customer.get("savings_transfer_ratio", 0))
    need_ratio = float(customer.get("need_spend_ratio", 0.5))
    luxury_ratio = float(customer.get("luxury_spend_ratio", 0.1))
    upi_count = int(customer.get("upi_retail_transactions", 0))
    credit_inflow = int(customer.get("monthly_credit_inflow", 0))
    multi_bank_share = float(customer.get("multi_bank_income_share", 0))

    # Credit inflow proxy from recurring credits + balance turnover
    if credit_inflow <= 0:
        credit_inflow = int(balance * 0.35 + upi_count * 1200 + stated * savings_ratio * 0.5)

    retained = int(credit_inflow * (1 - need_ratio - luxury_ratio * 0.6))
    investment_transfers = int(stated * savings_ratio)

    if employment == "salaried":
        inferred = int(max(credit_inflow, stated * 0.92))
        confidence = 0.82 if customer.get("salary_stability_months", 0) >= 6 else 0.68
        method = "Salaried credit-inflow + stated salary reconciliation"
    elif employment == "self_employed":
        from app.config import SELF_EMPLOYED_MARGINS

        biz = customer.get("business_type", "services")
        margin = SELF_EMPLOYED_MARGINS.get(biz, 0.45)
        gross_inflow = credit_inflow
        inferred = int(gross_inflow * margin + investment_transfers * 0.35)
        confidence = 0.58 + margin * 0.15
        method = f"Self-employed net margin ({biz.replace('_', ' ')}, {margin:.0%}) on business inflows"
    else:
        inferred = int(credit_inflow * 0.88 + retained * 0.25)
        confidence = 0.55
        method = "Gig UPI/credit volatility adjusted retained income"

    if multi_bank_share > 0.15:
        inferred = int(inferred * (1 + multi_bank_share * 0.12))
        method += "; multi-bank inflow uplift applied"

    inferred = max(inferred, 0)
    variance = abs(inferred - stated) / stated if stated else 0
    if variance > 0.35:
        confidence = max(confidence - 0.15, 0.45)

    return {
        "inferred_monthly_income": inferred,
        "stated_monthly_income": stated,
        "income_confidence": round(confidence, 2),
        "income_inference_method": method,
        "monthly_credit_inflow_used": credit_inflow,
        "income_variance_pct": round(variance * 100, 1),
    }
