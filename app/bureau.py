"""Credit bureau signal parsing for Track 02 underwriting support."""

from __future__ import annotations

BAND_SCORE = {"A": 780, "B": 710, "C": 640, "D": 560, "": 640}
BAND_LABELS = {
    "A": "Excellent",
    "B": "Good",
    "C": "Fair",
    "D": "Weak",
}


def analyze_bureau(customer: dict) -> dict:
    """Structured bureau view beyond raw band — supports explainability."""
    band = customer.get("credit_score_band", "C")
    enquiries = int(customer.get("bureau_enquiries_90d", 0))
    dti = float(customer.get("debt_to_income_ratio", 0.35))
    active_loans = int(customer.get("active_credit_accounts", 0))
    utilization = float(customer.get("credit_utilization_pct", 0))
    history_months = int(customer.get("bureau_repayment_history_months", 0))

    score = float(BAND_SCORE.get(band, 640))
    reasons: list[str] = []

    if enquiries >= 4:
        score -= 35
        reasons.append(f"{enquiries} bureau enquiries in 90d — active rate shopping")
    elif enquiries >= 2:
        score -= 12
        reasons.append(f"{enquiries} recent enquiries — monitor credit appetite")

    if utilization >= 0.75:
        score -= 28
        reasons.append(f"High credit utilization ({utilization:.0%}) limits headroom")
    elif utilization >= 0.5:
        score -= 10
        reasons.append(f"Moderate utilization ({utilization:.0%})")

    if history_months >= 36 and band in ("A", "B"):
        score += 15
        reasons.append(f"{history_months}mo clean repayment history on bureau")
    elif history_months < 12:
        score -= 8
        reasons.append("Thin bureau vintage — limited repayment track record")

    if active_loans >= 4:
        score -= 15
        reasons.append(f"{active_loans} active credit lines — stacked obligations")
    elif active_loans == 0 and band in ("A", "B"):
        score += 8
        reasons.append("No active external loans — clean bureau footprint")

    if dti >= 0.5:
        score -= 12
        reasons.append("Bureau DTI alignment shows elevated obligation load")

    score = max(300, min(900, score))
    normalized = round((score - 300) / 6, 1)  # 0–100 underwriting scale

    if normalized >= 75:
        rag, underwriting = "green", "Approve with standard terms"
    elif normalized >= 55:
        rag, underwriting = "amber", "Approve with enhanced monitoring"
    else:
        rag, underwriting = "red", "Decline or manual underwriter review"

    if not reasons:
        reasons.append(f"Bureau band {band} ({BAND_LABELS.get(band, 'Fair')}) — baseline assessment")

    return {
        "bureau_score": int(score),
        "normalized_score": normalized,
        "credit_band": band,
        "band_label": BAND_LABELS.get(band, "Fair"),
        "enquiries_90d": enquiries,
        "active_credit_accounts": active_loans,
        "credit_utilization_pct": round(utilization * 100, 1),
        "repayment_history_months": history_months,
        "rag": rag,
        "underwriting_hint": underwriting,
        "reasons": reasons[:4],
    }
