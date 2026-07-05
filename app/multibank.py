"""Multi-bank holistic income analysis (AMA: cross-bank statement view)."""

from __future__ import annotations

from app.income_inference import infer_monthly_income


def analyze_multibank(
    customer: dict,
    other_bank_monthly_inflow: int | None = None,
) -> dict:
    """
    Compare IDBI-only vs holistic income when customer has other bank accounts.
    Optional other_bank_monthly_inflow simulates uploaded statement parse.
    """
    idbi_income = infer_monthly_income(customer)
    stated = int(customer.get("monthly_income", 0))
    idbi_inferred = idbi_income["inferred_monthly_income"]
    has_other = bool(customer.get("has_other_bank_accounts"))
    share = float(customer.get("multi_bank_income_share", 0))

    if other_bank_monthly_inflow is not None and other_bank_monthly_inflow > 0:
        other_inflow = other_bank_monthly_inflow
        source = "uploaded_statement"
    elif has_other:
        other_inflow = int(idbi_inferred * share / max(1 - share, 0.05))
        source = "synthetic_sandbox"
    else:
        other_inflow = 0
        source = "idbi_only"

    holistic = idbi_inferred + other_inflow if has_other or other_bank_monthly_inflow else idbi_inferred
    hidden_income = max(0, holistic - stated)
    coverage_gap_pct = round(abs(holistic - stated) / stated * 100, 1) if stated else 0

    reasons: list[str] = []
    if has_other or other_bank_monthly_inflow:
        reasons.append(f"Other-bank inflow ~₹{other_inflow:,}/mo ({source.replace('_', ' ')})")
        if hidden_income > stated * 0.15:
            reasons.append(f"Holistic income ₹{holistic:,} exceeds stated by ₹{hidden_income:,}")
        reasons.append("Cross-bank view improves repayment capacity assessment")
    else:
        reasons.append("Single-bank IDBI view — no external accounts flagged")

    affordable_idbi = int((customer.get("estimated_monthly_disposable") or stated * 0.25) * 0.45)
    affordable_holistic = int(affordable_idbi * (holistic / max(idbi_inferred, 1)))

    return {
        "has_other_bank_accounts": has_other or bool(other_bank_monthly_inflow),
        "idbi_stated_income": stated,
        "idbi_inferred_income": idbi_inferred,
        "other_bank_monthly_inflow": other_inflow,
        "holistic_monthly_income": holistic,
        "hidden_income_detected": hidden_income,
        "coverage_gap_pct": coverage_gap_pct,
        "income_source": source,
        "affordable_emi_idbi_only": affordable_idbi,
        "affordable_emi_holistic": affordable_holistic,
        "emi_uplift_pct": round(
            (affordable_holistic - affordable_idbi) / max(affordable_idbi, 1) * 100, 1
        ),
        "reasons": reasons[:3],
    }
