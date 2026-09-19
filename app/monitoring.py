"""
Population drift monitoring — PSI, the second question model governance asks.

The first is "is it fair" (see fairness.py). The second is "will it still be
right in six months". Population Stability Index compares the distribution the
model was trained on against the distribution it is scoring now, feature by
feature, using the industry-standard bands:

    PSI < 0.10   stable
    0.10 – 0.25  moderate shift — investigate
    PSI > 0.25   significant shift — retrain

A monitor nobody has seen alarm is not a monitor, so the page also runs a
deliberately shifted intake scenario and shows the thresholds firing.
"""

from __future__ import annotations

import math
from typing import Any

from app.features import FEATURE_LABELS

# Features worth watching: the ones that carry the scoring decision and the ones
# most likely to move with the economy or a change in acquisition mix.
MONITORED_FIELDS = [
    ("monthly_income", "log_monthly_income"),
    ("estimated_monthly_disposable", "log_disposable"),
    ("debt_to_income_ratio", "debt_to_income_ratio"),
    ("salary_day_spend_ratio", "salary_day_spend_ratio"),
    ("savings_transfer_ratio", "savings_transfer_ratio"),
    ("luxury_spend_ratio", "luxury_spend_ratio"),
    ("avg_monthly_balance", "log_avg_balance"),
    ("loan_page_visits_30d", "loan_page_visits_30d"),
    ("loan_calculator_uses", "loan_calculator_uses"),
    ("bureau_enquiries_90d", "bureau_enquiries_90d"),
    ("geo_transaction_consistency", "geo_transaction_consistency"),
    ("avg_session_minutes", "avg_session_minutes"),
]

STABLE, MODERATE = 0.10, 0.25
BINS = 10
_EPS = 1e-6


def _values(rows: list[dict], field: str) -> list[float]:
    out = []
    for r in rows:
        v = r.get(field)
        if v is None or isinstance(v, bool):
            continue
        try:
            out.append(float(v))
        except (TypeError, ValueError):
            continue
    return out


def _quantile_edges(values: list[float], bins: int = BINS) -> list[float]:
    ordered = sorted(values)
    if not ordered:
        return []
    edges = [ordered[0]]
    for i in range(1, bins):
        idx = int(len(ordered) * i / bins)
        edges.append(ordered[min(idx, len(ordered) - 1)])
    edges.append(ordered[-1])
    # collapse duplicate edges (heavily tied fields such as calculator uses)
    unique: list[float] = []
    for e in edges:
        if not unique or e > unique[-1]:
            unique.append(e)
    return unique


def _share(values: list[float], edges: list[float]) -> list[float]:
    if not values or len(edges) < 2:
        return []
    counts = [0] * (len(edges) - 1)
    for v in values:
        placed = False
        for i in range(len(edges) - 1):
            upper = edges[i + 1]
            if v < upper or (i == len(edges) - 2 and v <= upper):
                counts[i] += 1
                placed = True
                break
        if not placed:
            counts[-1 if v >= edges[-1] else 0] += 1
    total = sum(counts) or 1
    return [c / total for c in counts]


def population_stability_index(reference: list[float], current: list[float]) -> float:
    """Standard PSI over reference deciles."""
    edges = _quantile_edges(reference)
    ref_share = _share(reference, edges)
    cur_share = _share(current, edges)
    if not ref_share or not cur_share or len(ref_share) != len(cur_share):
        return 0.0
    psi = 0.0
    for r, c in zip(ref_share, cur_share, strict=True):
        r = max(r, _EPS)
        c = max(c, _EPS)
        psi += (c - r) * math.log(c / r)
    return round(psi, 4)


def _band(psi: float) -> tuple[str, str]:
    if psi < STABLE:
        return "stable", "No action — distribution matches training."
    if psi < MODERATE:
        return "moderate", "Investigate — acquisition mix may be shifting."
    return "significant", "Retrain — the model is scoring a different population."


def compare_populations(reference: list[dict], current: list[dict]) -> dict[str, Any]:
    rows: list[dict] = []
    for field, feature in MONITORED_FIELDS:
        ref_vals = _values(reference, field)
        cur_vals = _values(current, field)
        psi = population_stability_index(ref_vals, cur_vals)
        band, action = _band(psi)
        rows.append({
            "field": field,
            "label": FEATURE_LABELS.get(feature, field.replace("_", " ").title()),
            "psi": psi,
            "band": band,
            "action": action,
            "reference_mean": round(sum(ref_vals) / len(ref_vals), 2) if ref_vals else None,
            "current_mean": round(sum(cur_vals) / len(cur_vals), 2) if cur_vals else None,
            "reference_n": len(ref_vals),
            "current_n": len(cur_vals),
        })
    rows.sort(key=lambda r: -r["psi"])
    worst = rows[0]["psi"] if rows else 0.0
    flagged = [r for r in rows if r["band"] != "stable"]
    return {
        "features": rows,
        "max_psi": worst,
        "overall_band": _band(worst)[0],
        "flagged_count": len(flagged),
        "flagged": [r["label"] for r in flagged],
        "retrain_recommended": worst >= MODERATE,
    }


def _shift_intake(customers: list[dict]) -> list[dict]:
    """
    A deliberately shifted next-quarter intake: more gig and informal income,
    thinner balances, heavier early-month spending. Used only to demonstrate that
    the thresholds actually fire.
    """
    shifted = []
    for i, c in enumerate(customers):
        s = dict(c)
        s["monthly_income"] = int(s.get("monthly_income", 40000) * 0.78)
        s["estimated_monthly_disposable"] = int(s.get("estimated_monthly_disposable", 8000) * 0.62)
        s["avg_monthly_balance"] = int(s.get("avg_monthly_balance", 30000) * 0.55)
        s["salary_day_spend_ratio"] = min(0.98, float(s.get("salary_day_spend_ratio", 0.5)) + 0.22)
        s["savings_transfer_ratio"] = max(0.0, float(s.get("savings_transfer_ratio", 0.1)) - 0.06)
        s["debt_to_income_ratio"] = min(0.95, float(s.get("debt_to_income_ratio", 0.35)) + 0.14)
        if i % 3 == 0:
            s["employment_type"] = "gig"
        shifted.append(s)
    return shifted


def build_monitoring_report(current: list[dict], reference: list[dict] | None = None) -> dict[str, Any]:
    from app.data_generator import generate_dataset

    # The model was trained on the seed-42 population; that is the reference.
    reference = reference or generate_dataset(200, seed=42)

    live = compare_populations(reference, current)
    scenario = compare_populations(reference, _shift_intake(current))

    return {
        "reference_population": "Training distribution (seed=42, n=200)",
        "current_population_size": len(current),
        "live": live,
        "alarm_scenario": {
            **scenario,
            "label": "Next-quarter intake stress scenario",
            "description": (
                "Income −22%, disposable −38%, balances −45%, day-1 spend +22 pts, DTI +14 pts, "
                "a third of the book reclassified as gig. Included so the thresholds can be seen "
                "firing rather than asserted."
            ),
        },
        "bands": [
            {"band": "stable", "range": f"PSI < {STABLE}", "action": "No action"},
            {"band": "moderate", "range": f"{STABLE} – {MODERATE}", "action": "Investigate acquisition mix"},
            {"band": "significant", "range": f"PSI > {MODERATE}", "action": "Retrain against current population"},
        ],
        "method": (
            "Population Stability Index computed over reference deciles per feature: "
            "PSI = Σ (current% − reference%) × ln(current% ÷ reference%). Bands are the "
            "conventional 0.10 / 0.25 thresholds used in credit model monitoring."
        ),
        "operating_rule": (
            "Monthly run against the live intake. Any feature above 0.25, or three features above "
            "0.10 in consecutive months, raises a retrain ticket for model risk — and the outcome "
            "feedback loop supplies the labels that retrain uses."
        ),
    }
