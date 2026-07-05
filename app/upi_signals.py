"""UPI merchant-category behavioural signals (AMA: what/where customer spends)."""

from __future__ import annotations

CATEGORIES = ("food", "mobility", "retail", "entertainment", "utilities", "other")


def _normalize_shares(customer: dict) -> dict[str, float]:
    shares = {
        "food": float(customer.get("upi_food_share", 0)),
        "mobility": float(customer.get("upi_mobility_share", 0)),
        "retail": float(customer.get("upi_retail_share", 0)),
        "entertainment": float(customer.get("upi_entertainment_share", 0)),
        "utilities": float(customer.get("upi_utilities_share", 0)),
    }
    total = sum(shares.values())
    if total <= 0:
        # Derive plausible split from legacy fields when category data absent
        retail_n = int(customer.get("upi_retail_transactions", 8))
        luxury = float(customer.get("luxury_spend_ratio", 0.15))
        need = float(customer.get("need_spend_ratio", 0.5))
        commute = min(1.0, customer.get("monthly_commute_spend", 0) / max(customer.get("monthly_income", 1), 1))
        shares = {
            "food": round(need * 0.35, 3),
            "mobility": round(commute * 0.8, 3),
            "retail": round(min(0.35, retail_n / 40 + luxury * 0.5), 3),
            "entertainment": round(luxury * 0.4, 3),
            "utilities": round(need * 0.25, 3),
        }
        total = sum(shares.values()) or 1.0
    return {k: round(v / total, 3) for k, v in shares.items()}


def analyze_upi_behavior(customer: dict) -> dict:
    """Merchant-level spend mix from UPI transaction footprint."""
    shares = _normalize_shares(customer)
    txn_count = int(customer.get("upi_retail_transactions", 0))
    merchant_diversity = round(min(1.0, txn_count / 20 + len([v for v in shares.values() if v > 0.08]) * 0.12), 2)
    dominant = max(shares, key=shares.get)
    reasons: list[str] = []

    if shares["food"] >= 0.28:
        reasons.append(f"Food/dining UPI share {shares['food']:.0%} — lifestyle spend visible")
    if shares["mobility"] >= 0.18:
        reasons.append(f"Mobility UPI {shares['mobility']:.0%} — commute/transport pattern")
    if shares["retail"] >= 0.22:
        reasons.append(f"Retail UPI {shares['retail']:.0%} — durable/consumption intent signal")
    if shares["entertainment"] >= 0.15 and customer.get("luxury_spend_ratio", 0) > 0.2:
        reasons.append("Entertainment-heavy UPI mix with high discretionary ratio")

    discipline_score = 50.0
    if shares["utilities"] >= 0.15:
        discipline_score += 12
    if shares["entertainment"] <= 0.1:
        discipline_score += 10
    if merchant_diversity >= 0.6:
        discipline_score += 8
        reasons.append(f"Diverse merchant footprint ({merchant_diversity:.0%}) — stable lifestyle")

    if not reasons:
        reasons.append(f"Dominant UPI category: {dominant} ({shares[dominant]:.0%})")

    return {
        "category_shares": shares,
        "dominant_category": dominant,
        "merchant_diversity_score": merchant_diversity,
        "monthly_upi_transactions": txn_count,
        "discipline_hint": round(max(0, min(100, discipline_score)), 1),
        "reasons": reasons[:3],
    }
