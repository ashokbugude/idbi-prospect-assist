"""
Lead Uplift Simulator — counterfactual "what would move this lead" engine.

Track 02 differentiator
-----------------------
A lead score tells an RM *who* to call. It does not tell them *what to do* about
the 77% of the book that is not yet callable. The uplift simulator answers that
question by re-running the **same deterministic rule engine** on perturbed copies
of the customer record and measuring the real tier/score movement.

Every number produced here is an actual re-score, not a regression coefficient or
an LLM guess — so the output is fully explainable to an underwriter and safe to
show a customer-facing RM.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from app.scoring import LEAD_TIERS, TIER_CSS, TIER_ORDER, score_customer_rules

# Composite floors used by assign_lead_tier() — surfaced so the UI can show the
# arithmetic gap to the next tier alongside the dimension gates.
TIER_COMPOSITE_FLOOR: dict[str, float] = {
    "Quality Lead": 78.0,
    "Serious": 62.0,
    "Interested": 38.0,
    "Window-shop Risk": 0.0,
}

TIER_DIMENSION_GATES: dict[str, dict[str, float]] = {
    "Quality Lead": {"repayment": 62, "intent": 55, "discipline": 52},
    "Serious": {"repayment": 48, "intent": 42, "discipline": 40},
}

MAX_PATH_STEPS = 4


# --------------------------------------------------------------------------- #
# Lever definitions
# --------------------------------------------------------------------------- #
@dataclass
class Lever:
    code: str
    label: str
    category: str
    owner: str
    horizon: str
    effort: str
    note: str
    apply: Callable[[dict], None]
    applicable: Callable[[dict], bool] = field(default=lambda c: True)


def _f(customer: dict, key: str, default: float = 0.0) -> float:
    value = customer.get(key)
    if isinstance(value, bool) or value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _income(customer: dict) -> float:
    return _f(customer, "monthly_income", 0.0)


# --- consent & data ------------------------------------------------------- #
def _apply_aa_consent(c: dict) -> None:
    c["has_other_bank_accounts"] = True
    c["multi_bank_income_share"] = max(_f(c, "multi_bank_income_share"), 0.25)


# --- assisted journey ----------------------------------------------------- #
def _apply_calculator(c: dict) -> None:
    c["loan_calculator_uses"] = max(int(_f(c, "loan_calculator_uses")), 3)
    c["avg_session_minutes"] = max(_f(c, "avg_session_minutes"), 5.5)
    c["loan_page_visits_30d"] = max(int(_f(c, "loan_page_visits_30d")), 2)


def _apply_application(c: dict) -> None:
    c["application_started"] = True
    c["window_shopping_flag"] = False


# --- obligation relief ---------------------------------------------------- #
def _apply_close_emi(c: dict) -> None:
    c["debt_to_income_ratio"] = max(0.0, _f(c, "debt_to_income_ratio") - 0.10)
    c["estimated_monthly_disposable"] = int(
        _f(c, "estimated_monthly_disposable") + _income(c) * 0.10
    )


def _apply_card_paydown(c: dict) -> None:
    c["credit_utilization_pct"] = min(_f(c, "credit_utilization_pct", 0.5), 0.30)


def _apply_enquiry_cooloff(c: dict) -> None:
    c["bureau_enquiries_90d"] = min(int(_f(c, "bureau_enquiries_90d")), 1)


# --- spending discipline -------------------------------------------------- #
def _apply_savings_nudge(c: dict) -> None:
    c["savings_transfer_ratio"] = min(_f(c, "savings_transfer_ratio") + 0.08, 0.35)


def _apply_day1_discipline(c: dict) -> None:
    c["salary_day_spend_ratio"] = max(_f(c, "salary_day_spend_ratio") - 0.20, 0.12)


def _apply_luxury_trim(c: dict) -> None:
    luxury = _f(c, "luxury_spend_ratio")
    c["luxury_spend_ratio"] = max(luxury - 0.06, 0.03)
    c["want_spend_ratio"] = _f(c, "want_spend_ratio") + min(0.06, luxury)
    c["estimated_monthly_disposable"] = int(
        _f(c, "estimated_monthly_disposable") + _income(c) * 0.04
    )


# --- relationship deepening ----------------------------------------------- #
def _apply_salary_routing(c: dict) -> None:
    c["monthly_credit_inflow"] = int(max(_f(c, "monthly_credit_inflow"), _income(c)) * 1.25)
    c["salary_stability_months"] = max(int(_f(c, "salary_stability_months")), 12)


def _apply_balance_buildup(c: dict) -> None:
    c["avg_monthly_balance"] = int(max(_f(c, "avg_monthly_balance"), _income(c) * 0.5))


LEVERS: list[Lever] = [
    Lever(
        code="aa_consent",
        label="Obtain Account Aggregator consent (fetch other-bank statements)",
        category="Consent & data",
        owner="RM",
        horizon="Same day",
        effort="Low",
        note="RBI AA framework — DPDP-compliant consented pull. Reveals income held outside IDBI.",
        apply=_apply_aa_consent,
        applicable=lambda c: not c.get("has_other_bank_accounts"),
    ),
    Lever(
        code="emi_calculator",
        label="Walk customer through EMI calculator (assisted digital journey)",
        category="Assisted journey",
        owner="RM",
        horizon="Same day",
        effort="Low",
        note="Converts passive browsing into a measured intent signal.",
        apply=_apply_calculator,
        applicable=lambda c: _f(c, "loan_calculator_uses") < 3 or _f(c, "avg_session_minutes") < 5.0,
    ),
    Lever(
        code="start_application",
        label="Convert enquiry into a started application",
        category="Assisted journey",
        owner="RM",
        horizon="7 days",
        effort="Medium",
        note="Strongest single intent signal in the model (+40 intent points).",
        apply=_apply_application,
        applicable=lambda c: not c.get("application_started"),
    ),
    Lever(
        code="close_one_emi",
        label="Consolidate / close one existing obligation (DTI −10 pts)",
        category="Obligation relief",
        owner="RM + Customer",
        horizon="1–3 months",
        effort="Medium",
        note="RM lever: balance-transfer or top-up offer that retires a costlier external EMI.",
        apply=_apply_close_emi,
        applicable=lambda c: _f(c, "debt_to_income_ratio") > 0.15,
    ),
    Lever(
        code="card_paydown",
        label="Reduce revolving credit utilization to ≤30%",
        category="Obligation relief",
        owner="Customer",
        horizon="1–3 months",
        effort="Medium",
        note="Utilization above 75% costs the bureau sub-score 28 points.",
        apply=_apply_card_paydown,
        applicable=lambda c: _f(c, "credit_utilization_pct", 0.5) > 0.35,
    ),
    Lever(
        code="enquiry_cooloff",
        label="90-day credit-enquiry cool-off",
        category="Obligation relief",
        owner="Customer",
        horizon="1–3 months",
        effort="Low",
        note="Rate-shopping (4+ enquiries) is read as weak commitment and bureau stress.",
        apply=_apply_enquiry_cooloff,
        applicable=lambda c: _f(c, "bureau_enquiries_90d") >= 2,
    ),
    Lever(
        code="savings_nudge",
        label="Auto-sweep / RD standing instruction (savings ratio +8 pts)",
        category="Spending discipline",
        owner="RM + Customer",
        horizon="1–3 months",
        effort="Low",
        note="Cross-sell that is also a scoring lever — retained income is observable next cycle.",
        apply=_apply_savings_nudge,
        applicable=lambda c: _f(c, "savings_transfer_ratio") < 0.20,
    ),
    Lever(
        code="day1_discipline",
        label="Spread salary-day spending (day-1 depletion −20 pts)",
        category="Spending discipline",
        owner="Customer",
        horizon="1–3 months",
        effort="High",
        note="Day-1 salary depletion is the single strongest delinquency predictor in the engine.",
        apply=_apply_day1_discipline,
        applicable=lambda c: _f(c, "salary_day_spend_ratio") > 0.35,
    ),
    Lever(
        code="luxury_trim",
        label="Trim discretionary/luxury spend by 6 pts",
        category="Spending discipline",
        owner="Customer",
        horizon="1–3 months",
        effort="Medium",
        note="Frees repayment buffer and lifts behavioural discipline simultaneously.",
        apply=_apply_luxury_trim,
        applicable=lambda c: _f(c, "luxury_spend_ratio") > 0.10,
    ),
    Lever(
        code="salary_routing",
        label="Route salary credit to IDBI (primary-bank conversion)",
        category="Relationship deepening",
        owner="RM",
        horizon="1–3 months",
        effort="Medium",
        note="Deepens the liability relationship and makes income directly observable.",
        apply=_apply_salary_routing,
        applicable=lambda c: c.get("employment_type", "salaried") == "salaried"
        and (_f(c, "salary_stability_months") < 12 or _f(c, "monthly_credit_inflow") < _income(c)),
    ),
    Lever(
        code="balance_buildup",
        label="Maintain average balance at ≥50% of monthly income",
        category="Relationship deepening",
        owner="Customer",
        horizon="1–3 months",
        effort="Medium",
        note="Balance cushion is a direct repayment-capacity and discipline input.",
        apply=_apply_balance_buildup,
        applicable=lambda c: _f(c, "avg_monthly_balance") < _income(c) * 0.5,
    ),
]

LEVERS_BY_CODE = {lever.code: lever for lever in LEVERS}

# Adverse scenario used for the resilience / stress test.
STRESS_SCENARIO = {
    "label": "Adverse 6-month scenario",
    "description": (
        "DTI +12 pts · day-1 salary depletion +18 pts · luxury spend +5 pts · "
        "2 additional bureau enquiries · disposable income −12%"
    ),
}


def _apply_stress(c: dict) -> None:
    c["debt_to_income_ratio"] = min(_f(c, "debt_to_income_ratio") + 0.12, 0.95)
    c["salary_day_spend_ratio"] = min(_f(c, "salary_day_spend_ratio") + 0.18, 0.98)
    c["luxury_spend_ratio"] = min(_f(c, "luxury_spend_ratio") + 0.05, 0.60)
    c["bureau_enquiries_90d"] = int(_f(c, "bureau_enquiries_90d") + 2)
    c["estimated_monthly_disposable"] = int(_f(c, "estimated_monthly_disposable") * 0.88)


# --------------------------------------------------------------------------- #
# Engine
# --------------------------------------------------------------------------- #
def _rescore(raw: dict, levers: list[Lever]) -> dict:
    """Apply levers to a copy of the raw record and re-run the rule engine."""
    candidate = dict(raw)
    for lever in levers:
        lever.apply(candidate)
    return score_customer_rules(candidate)


def _tier_index(tier: str) -> int:
    return TIER_ORDER.get(tier, len(LEAD_TIERS) - 1)


def _next_tier(tier: str) -> str | None:
    idx = _tier_index(tier)
    return LEAD_TIERS[idx - 1] if idx > 0 else None


def _applicable_levers(raw: dict) -> list[Lever]:
    out: list[Lever] = []
    for lever in LEVERS:
        try:
            if lever.applicable(raw):
                out.append(lever)
        except Exception:  # defensive — a malformed record must not break the page
            continue
    return out


def _override_gaps(profile: dict, customer: dict) -> list[str]:
    """Hard overrides in assign_lead_tier() that cap the tier regardless of composite."""
    gaps: list[str] = []
    intent = profile["purchase_intent"]["score"]
    if customer.get("window_shopping_flag") and intent < 60:
        gaps.append(
            f"Window-shopping override active — purchase intent {intent:.0f} must reach 60 "
            "(or an application must be started) before any tier above Window-shop Risk"
        )
    delinq = profile.get("delinquency_risk", {}) or {}
    if delinq.get("risk_band") == "High" and profile["behavioral_discipline"]["score"] < 48:
        gaps.append(
            f"High delinquency band with discipline {profile['behavioral_discipline']['score']:.0f} "
            "— capped at Interested until discipline reaches 48"
        )
    return gaps


def _gate_gaps(profile: dict, target_tier: str) -> list[str]:
    """Dimension gates still unmet for the target tier."""
    gates = TIER_DIMENSION_GATES.get(target_tier)
    if not gates:
        return []
    actual = {
        "repayment": profile["repayment_capacity"]["score"],
        "intent": profile["purchase_intent"]["score"],
        "discipline": profile["behavioral_discipline"]["score"],
    }
    labels = {
        "repayment": "Repayment capacity",
        "intent": "Purchase intent",
        "discipline": "Behavioural discipline",
    }
    return [
        f"{labels[k]} {actual[k]:.0f} → needs {v:.0f}"
        for k, v in gates.items()
        if actual[k] < v
    ]


def _greedy_path(raw: dict, ordered: list[Lever], target_tier: str | None, base: dict) -> dict:
    """Smallest greedy combination of levers that reaches the next tier."""
    chosen: list[Lever] = []
    best_profile: dict | None = None
    best_score = -1.0
    target_idx = _tier_index(target_tier) if target_tier else -1

    for lever in ordered:
        if len(chosen) >= MAX_PATH_STEPS:
            break
        trial = chosen + [lever]
        profile = _rescore(raw, trial)
        score = profile["composite_lead_score"]
        if score <= best_score + 0.05:
            continue  # lever adds nothing on top of what is already chosen
        chosen, best_profile, best_score = trial, profile, score
        if target_tier and _tier_index(profile["lead_tier"]) <= target_idx:
            break

    if best_profile is None:
        # No lever improves this profile — return the unchanged baseline in the same shape.
        return {
            "levers": [],
            "labels": [],
            "owners": [],
            "steps": 0,
            "score_after": base["composite_lead_score"],
            "tier_after": base["lead_tier"],
            "tier_after_css": TIER_CSS.get(base["lead_tier"], ""),
            "affordable_emi_after": base.get("affordable_emi_estimate"),
            "achieves_next_tier": False,
            "remaining_gates": _gate_gaps(base, target_tier) if target_tier else [],
            "at_top_tier": target_tier is None,
            "note": (
                "No modelled lever improves this profile further."
                if target_tier is None
                else "No modelled lever moves this lead closer to the next tier."
            ),
        }

    achieved = bool(target_tier) and _tier_index(best_profile["lead_tier"]) <= target_idx
    if target_tier is None:
        note = (
            f"Already at the top tier — these {len(chosen)} action(s) add "
            f"{best_score - base['composite_lead_score']:+.1f} points of headroom "
            "and protect the tier under stress."
        )
    elif achieved:
        note = f"{len(chosen)} action(s) move this lead to {best_profile['lead_tier']}."
    else:
        note = "Best achievable combination — lead stays below the next tier gate."
    return {
        "levers": [lv.code for lv in chosen],
        "labels": [lv.label for lv in chosen],
        "owners": sorted({lv.owner for lv in chosen}),
        "steps": len(chosen),
        "score_after": best_profile["composite_lead_score"],
        "tier_after": best_profile["lead_tier"],
        "tier_after_css": TIER_CSS.get(best_profile["lead_tier"], ""),
        "affordable_emi_after": best_profile.get("affordable_emi_estimate"),
        "achieves_next_tier": achieved,
        "remaining_gates": [] if achieved or not target_tier else _gate_gaps(best_profile, target_tier),
        "at_top_tier": target_tier is None,
        "note": note,
    }


def simulate_uplift(raw: dict, base_profile: dict | None = None) -> dict:
    """
    Full counterfactual report for one customer.

    Returns individual lever impact, the smallest path to the next tier, and an
    adverse-scenario stress test (tier resilience).
    """
    base = base_profile or score_customer_rules(raw)
    base_score = base["composite_lead_score"]
    base_tier = base["lead_tier"]
    base_emi = base.get("affordable_emi_estimate") or 0
    target = _next_tier(base_tier)

    results: list[dict] = []
    for lever in _applicable_levers(raw):
        profile = _rescore(raw, [lever])
        delta = round(profile["composite_lead_score"] - base_score, 1)
        emi_after = profile.get("affordable_emi_estimate") or 0
        results.append(
            {
                "code": lever.code,
                "label": lever.label,
                "category": lever.category,
                "owner": lever.owner,
                "horizon": lever.horizon,
                "effort": lever.effort,
                "note": lever.note,
                "delta_points": delta,
                "score_after": profile["composite_lead_score"],
                "tier_after": profile["lead_tier"],
                "tier_after_css": TIER_CSS.get(profile["lead_tier"], ""),
                "tier_moves": profile["lead_tier"] != base_tier,
                "tier_jump": max(0, _tier_index(base_tier) - _tier_index(profile["lead_tier"])),
                "emi_headroom_delta": int(emi_after - base_emi),
                "rm_controllable": lever.owner in ("RM", "RM + Customer"),
            }
        )

    results.sort(key=lambda r: (-r["delta_points"], r["effort"] != "Low"))
    ordered_levers = [LEVERS_BY_CODE[r["code"]] for r in results if r["delta_points"] > 0]
    path = _greedy_path(raw, ordered_levers, target, base)

    stressed = dict(raw)
    _apply_stress(stressed)
    stress_profile = score_customer_rules(stressed)
    demotes = _tier_index(stress_profile["lead_tier"]) > _tier_index(base_tier)

    floor = TIER_COMPOSITE_FLOOR.get(target or base_tier, 0.0)
    gap = round(max(0.0, floor - base_score), 1) if target else 0.0

    return {
        "customer_id": raw.get("customer_id"),
        "current_tier": base_tier,
        "current_tier_css": TIER_CSS.get(base_tier, ""),
        "current_score": base_score,
        "next_tier": target,
        "next_tier_css": TIER_CSS.get(target, "") if target else "",
        "gap_points": gap,
        "gap_gates": (_override_gaps(base, raw) + (_gate_gaps(base, target) if target else [])),
        "at_top_tier": target is None,
        "levers": results,
        "rm_controllable_count": sum(1 for r in results if r["rm_controllable"] and r["delta_points"] > 0),
        "best_single_lever": results[0] if results else None,
        "recommended_path": path,
        "stress_test": {
            **STRESS_SCENARIO,
            "score_after": stress_profile["composite_lead_score"],
            "score_drop": round(base_score - stress_profile["composite_lead_score"], 1),
            "tier_after": stress_profile["lead_tier"],
            "tier_after_css": TIER_CSS.get(stress_profile["lead_tier"], ""),
            "demotes": demotes,
            "resilience": "Fragile" if demotes else "Resilient",
            "resilience_note": (
                "Tier survives the adverse scenario — safe to underwrite on current signals."
                if not demotes
                else f"Tier falls to {stress_profile['lead_tier']} under stress — size the ticket conservatively."
            ),
        },
        "method": (
            "Each row is a real re-score: the raw customer record is copied, the lever is applied, "
            "and the identical deterministic rule engine (scoring.py) is re-run. No ML, no estimation — "
            "the delta shown is exactly what the production scorer would output."
        ),
        "disclaimer": (
            "Simulation on synthetic round-1 data. Lever magnitudes are RM-negotiable assumptions, "
            "not commitments to the customer. No automated credit decision is implied."
        ),
    }


def uplift_summary(raw: dict, base_profile: dict | None = None) -> dict:
    """Lightweight variant for list views — top lever + path only."""
    full = simulate_uplift(raw, base_profile)
    return {
        "customer_id": full["customer_id"],
        "current_tier": full["current_tier"],
        "next_tier": full["next_tier"],
        "gap_points": full["gap_points"],
        "best_single_lever": full["best_single_lever"],
        "recommended_path": full["recommended_path"],
        "resilience": full["stress_test"]["resilience"],
    }
