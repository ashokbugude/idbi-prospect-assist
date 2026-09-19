"""
Next Best Action (NBA) engine — turns a lead score into a costed RM work item.

Track 02 differentiator
-----------------------
Most lead-scoring prototypes stop at a ranked list. An RM still has to decide
*what* to do, *through which channel*, *by when*, and *whether it is worth the
12 minutes it takes*. This module answers all four, and ranks every action by
**expected rupees of disbursal per RM minute** — the only currency a branch
actually budgets in.

Where the Lead Uplift Simulator (uplift.py) is available, the conversion delta
for consent/journey actions is taken from a *real re-score* rather than an
assumption, so the ranking is grounded in the same engine that produced the tier.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

from app.impact import TIER_CONVERSION_RATES
from app.scoring import PRODUCT_LABELS

# Indicative tenor (months) per product, used to convert an affordable EMI into
# an indicative ticket size. Discounted by INTEREST_DISCOUNT for interest content.
PRODUCT_TENOR_MONTHS = {
    "home_loan": 180,
    "mortgage_loan": 144,
    "auto_loan": 60,
    "personal_loan": 48,
    "consumer_durable": 18,
}
INTEREST_DISCOUNT = 0.72

# Minutes of RM/ops capacity consumed by one execution of each channel.
CHANNEL_EFFORT_MINUTES = {
    "RM call": 12,
    "Assisted digital journey": 20,
    "WhatsApp / SMS nudge": 2,
    "Email nurture": 0,      # marketing automation — consumes no RM capacity
    "Branch appointment": 45,
    "Underwriter desk": 15,
    "Automated content": 0,
    "No contact": 0,
}

# Relative lift on the lead's tier base conversion rate. POC assumptions — each
# one is listed on /impact and is a calibration target for the 4-week RM A/B.
ACTION_RELATIVE_LIFT = {
    "priority_call": 0.35,
    "aa_consent_request": 0.12,
    "assisted_journey": 0.45,
    "application_assist": 0.50,
    "calculator_walkthrough": 0.30,
    "obligation_relief_offer": 0.28,
    "salary_routing_offer": 0.18,
    "digital_nurture": 0.22,
    "literacy_content": 0.0,
    "suppress_outbound": 0.0,
    "underwriter_prep": 0.0,
    "conservative_ticket": 0.0,
    "secured_pivot": 0.15,
    "rescore_trigger": 0.0,
}

# Minutes an RM would have burned on a lead the engine suppresses.
SUPPRESSED_CALL_MINUTES = 12

# Channels that put a human in front of the customer. For a Window-shop Risk lead
# these are removed structurally, not left to a scoring threshold — suppression is
# the product's core promise and must not depend on a priority calculation.
OUTBOUND_CHANNELS = {
    "RM call",
    "Assisted digital journey",
    "Branch appointment",
    "WhatsApp / SMS nudge",
}

# Product-agnostic labels used when the same action is aggregated across the book.
PLAYBOOK_LABELS = {
    "priority_call": "Priority callback — pre-qualified Quality Leads",
    "assisted_journey": "Assisted digital journey — Serious leads",
    "application_assist": "Close the application gap",
    "calculator_walkthrough": "EMI calculator walkthrough",
    "aa_consent_request": "Request Account Aggregator consent",
    "obligation_relief_offer": "Offer balance transfer / consolidation",
    "salary_routing_offer": "Offer salary-account conversion",
    "digital_nurture": "Digital nurture sequence (no RM call)",
    "literacy_content": "Financial-literacy content only",
    "suppress_outbound": "Suppress outbound — no RM call",
    "underwriter_prep": "Pre-build underwriter packet",
    "conservative_ticket": "Cap ticket size — elevated delinquency band",
    "secured_pivot": "Pivot to a secured product",
    "rescore_trigger": "Auto re-score in 30 days",
}


@dataclass
class Action:
    code: str
    title: str
    channel: str
    owner: str
    category: str
    sla_hours: int | None
    rationale: str
    script: str
    effort_minutes: int
    expected_conversion_delta_pp: float
    expected_value_inr: int
    value_per_rm_minute: int
    rm_minutes_saved: int
    priority: float
    evidence: str
    compliance_note: str


def _num(value, default: float = 0.0) -> float:
    """Tolerant numeric read — raw records may carry strings or nulls."""
    if isinstance(value, bool) or value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def indicative_ticket_inr(profile: dict) -> int:
    """Indicative disbursal size from affordable EMI × product tenor."""
    emi = int(profile.get("affordable_emi_estimate") or 0)
    tenor = PRODUCT_TENOR_MONTHS.get(profile.get("top_product", ""), 48)
    return max(0, int(emi * tenor * INTEREST_DISCOUNT))


def _base_rate(profile: dict) -> float:
    return TIER_CONVERSION_RATES.get(profile.get("lead_tier", "Interested"), 0.02)


def _tier_rate(tier: str) -> float:
    return TIER_CONVERSION_RATES.get(tier, 0.02)


def _make(
    profile: dict,
    code: str,
    title: str,
    channel: str,
    owner: str,
    category: str,
    sla_hours: int | None,
    rationale: str,
    script: str,
    evidence: str,
    compliance_note: str = "AI-assisted recommendation — RM/underwriter retains the decision.",
    delta_pp: float | None = None,
    minutes_saved: int = 0,
) -> Action:
    if delta_pp is None:
        delta_pp = round(_base_rate(profile) * 100 * ACTION_RELATIVE_LIFT.get(code, 0.0), 2)
    effort = CHANNEL_EFFORT_MINUTES.get(channel, 10)
    ticket = indicative_ticket_inr(profile)
    value = int(delta_pp / 100 * ticket)
    per_minute = int(value / effort) if effort else value
    # Priority blends value density with a floor so zero-revenue governance and
    # suppression actions still surface in the queue.
    priority = round(min(100.0, (per_minute / 1200) + delta_pp * 2.2 + (12 if minutes_saved else 0)), 1)
    return Action(
        code=code,
        title=title,
        channel=channel,
        owner=owner,
        category=category,
        sla_hours=sla_hours,
        rationale=rationale,
        script=script,
        effort_minutes=effort,
        expected_conversion_delta_pp=round(delta_pp, 2),
        expected_value_inr=value,
        value_per_rm_minute=per_minute,
        rm_minutes_saved=minutes_saved,
        priority=priority,
        evidence=evidence,
        compliance_note=compliance_note,
    )


def _lever(uplift: dict | None, code: str) -> dict | None:
    if not uplift:
        return None
    return next((l for l in uplift.get("levers", []) if l["code"] == code), None)


def _lever_delta_pp(profile: dict, lever: dict | None) -> float | None:
    """Conversion delta implied by a *simulated* tier move — not an assumption."""
    if not lever or not lever.get("tier_moves"):
        return None
    before = _tier_rate(profile.get("lead_tier", "Interested"))
    after = _tier_rate(lever["tier_after"])
    return round(max(0.0, after - before) * 100, 2)


def build_next_best_actions(profile: dict, raw: dict, uplift: dict | None = None) -> dict:
    """Ranked, costed action list for one lead."""
    tier = profile.get("lead_tier", "Interested")
    product = profile.get("top_product_label", PRODUCT_LABELS.get(profile.get("top_product", ""), "Loan"))
    name = profile.get("name", "the customer")
    delinq = profile.get("delinquency_risk", {}) or {}
    bureau = profile.get("bureau_analysis", {}) or {}
    emi = int(profile.get("affordable_emi_estimate") or 0)
    actions: list[Action] = []

    # ---------------- tier-driven core action ----------------
    if tier == "Quality Lead":
        actions.append(_make(
            profile, "priority_call", f"Priority callback — pitch {product}", "RM call", "RM",
            "Convert", 24,
            f"Quality Lead (score {profile.get('composite_lead_score')}) with pre-qualified EMI capacity of ₹{emi:,}/mo.",
            f"“{name}, based on your account relationship you're pre-assessed for a {product} "
            f"with an EMI around ₹{emi:,}. Shall I hold a slot to complete it this week?”",
            "Lead tiering rules — repayment capacity gate",
        ))
        actions.append(_make(
            profile, "underwriter_prep", "Pre-build underwriter packet", "Underwriter desk", "Ops",
            "Governance", 24,
            "Explainability pack ready before the call shortens sanction cycle time.",
            "Attach the generated PDF (reasons, bureau view, income inference) to the lead record.",
            "Underwriter packet",
            compliance_note="Human-in-loop: packet supports an underwriter decision, never replaces it.",
        ))
    elif tier == "Serious":
        actions.append(_make(
            profile, "assisted_journey", f"Assisted digital journey for {product}", "Assisted digital journey", "RM",
            "Convert", 48,
            f"Serious lead — capacity confirmed (₹{emi:,}/mo) but the digital journey is incomplete.",
            f"“{name}, I can co-browse the {product} application with you — it takes about 10 minutes "
            "and I'll confirm your eligibility live.”",
            "Lead tiering rules — Serious gate (composite 62+)",
        ))
    elif tier == "Interested":
        actions.append(_make(
            profile, "digital_nurture", "Digital nurture sequence (no RM call yet)", "Email nurture", "Marketing",
            "Nurture", None,
            "Capacity or intent not yet sufficient for RM time — nurture until a trigger fires.",
            f"Send the {product} explainer + EMI calculator link; escalate on calculator use.",
            "Lead tiering rules — Interested band (composite 38–62)",
        ))
    else:  # Window-shop Risk
        actions.append(_make(
            profile, "suppress_outbound", "Suppress outbound — do not place an RM call", "No contact", "System",
            "Protect capacity", None,
            "Browsing-heavy, commitment-light pattern. Calling this lead is the ~1% conversion trap.",
            "No sales contact. Lead stays visible to the RM for context only.",
            "Window-shopping override",
            compliance_note="Suppression is a prioritisation decision, not a credit rejection. No adverse credit action is recorded.",
            minutes_saved=SUPPRESSED_CALL_MINUTES,
        ))
        actions.append(_make(
            profile, "literacy_content", "Financial-literacy content only", "Automated content", "Marketing",
            "Nurture", None,
            "Keeps the relationship warm at zero RM cost while discipline signals mature.",
            "Enrol in the budgeting / credit-health drip. Re-evaluate on the next scoring run.",
            "Deprioritisation brief",
        ))

    # ---------------- uplift-grounded actions ----------------
    aa = _lever(uplift, "aa_consent")
    aa_delta = _lever_delta_pp(profile, aa)
    if aa and (aa_delta or not raw.get("has_other_bank_accounts")):
        moves = f" Simulation moves this lead {tier} → {aa['tier_after']}." if aa and aa.get("tier_moves") else ""
        actions.append(_make(
            profile, "aa_consent_request", "Request Account Aggregator consent", "RM call", "RM",
            "Unlock data", 72,
            f"Income held at other banks is invisible to IDBI today.{moves}",
            f"“{name}, if you share your other bank statements through the RBI Account Aggregator — "
            "it's a one-tap consent, we never see your login — I can often improve the eligibility we can offer.”",
            "Uplift simulator — measured re-score" if aa_delta else "Account Aggregator flow",
            compliance_note="Explicit, revocable, purpose-limited consent under the AA framework and DPDP Act, 2023.",
            delta_pp=aa_delta,
        ))

    app_lever = _lever(uplift, "start_application")
    if not raw.get("application_started") and tier in ("Quality Lead", "Serious"):
        actions.append(_make(
            profile, "application_assist", "Close the application gap", "Assisted digital journey", "RM",
            "Convert", 48,
            "Capacity and intent both clear the gate but no application exists — the highest-value gap in the book."
            + (f" Simulation: {app_lever['delta_points']:+.1f} composite points." if app_lever else ""),
            "Offer to complete the application on the call; pre-fill from the existing KYC record.",
            "Uplift simulator — measured re-score" if app_lever else "Purchase intent model",
            delta_pp=_lever_delta_pp(profile, app_lever),
        ))

    calc_lever = _lever(uplift, "emi_calculator")
    if tier in ("Serious", "Interested") and _num(raw.get("loan_calculator_uses")) < 3:
        actions.append(_make(
            profile, "calculator_walkthrough", "EMI calculator walkthrough", "WhatsApp / SMS nudge", "RM",
            "Nurture", 72,
            "Calculator usage is the cheapest measurable intent signal available."
            + (f" Simulation: {calc_lever['delta_points']:+.1f} composite points." if calc_lever else ""),
            f"Send a pre-filled {product} EMI link at ₹{emi:,}/mo and ask which tenor suits them.",
            "Uplift simulator — measured re-score" if calc_lever else "Purchase intent model",
        ))

    dti_lever = _lever(uplift, "close_one_emi")
    if _num(raw.get("debt_to_income_ratio")) >= 0.40 and tier != "Window-shop Risk":
        actions.append(_make(
            profile, "obligation_relief_offer", "Offer balance transfer / consolidation", "RM call", "RM",
            "Convert", 96,
            f"DTI at {_num(raw.get('debt_to_income_ratio')):.0%} is the binding constraint."
            + (f" Retiring one obligation is worth {dti_lever['delta_points']:+.1f} points." if dti_lever else ""),
            "Position a balance transfer that retires a costlier external EMI — improves eligibility and wins the asset.",
            "Uplift simulator — measured re-score" if dti_lever else "Repayment capacity model",
            delta_pp=_lever_delta_pp(profile, dti_lever),
        ))

    salary_lever = _lever(uplift, "salary_routing")
    if salary_lever:
        actions.append(_make(
            profile, "salary_routing_offer", "Offer salary-account conversion", "RM call", "RM",
            "Deepen relationship", 168,
            "Routing salary to IDBI makes income directly observable and deepens the liability relationship."
            + f" Simulation: {salary_lever['delta_points']:+.1f} composite points.",
            "“Moving your salary credit to IDBI unlocks better pricing and speeds up any future loan approval.”",
            "Uplift simulator — measured re-score",
        ))

    # ---------------- risk overlays ----------------
    if delinq.get("risk_band") in ("Medium", "High"):
        actions.append(_make(
            profile, "conservative_ticket", f"Cap ticket size — {delinq.get('risk_band')} delinquency band", "Underwriter desk", "Underwriter",
            "Risk control", 24,
            f"Delinquency score {delinq.get('score')} ({delinq.get('risk_band')}). "
            + (delinq.get("reasons") or ["Forward-looking stress signal."])[0],
            f"Size to ≤₹{int(emi * 0.7):,}/mo and document the rationale in the packet.",
            "Delinquency risk model",
            compliance_note="Risk-based pricing/sizing — must be recorded with reasons for audit.",
        ))

    if bureau.get("rag") == "red" and profile.get("top_product") in ("personal_loan", "consumer_durable"):
        actions.append(_make(
            profile, "secured_pivot", "Pivot to a secured product", "RM call", "RM",
            "Risk control", 72,
            f"Bureau normalized {bureau.get('normalized_score')}/100 — unsecured pricing will not clear underwriting.",
            "Lead with a secured/collateral-backed option instead of the unsecured top match.",
            "Bureau assessment",
        ))

    if tier in ("Interested", "Window-shop Risk"):
        actions.append(_make(
            profile, "rescore_trigger", "Auto re-score in 30 days", "Automated content", "System",
            "Nurture", None,
            "Behavioural signals are monthly; a fresh salary cycle can change the tier without any RM cost.",
            "Schedule re-scoring; alert the RM only on a tier upgrade.",
            "Scheduled re-scoring",
        ))

    if tier == "Window-shop Risk":
        actions = [a for a in actions if a.channel not in OUTBOUND_CHANNELS]

    ranked = sorted(actions, key=lambda a: (-a.priority, a.effort_minutes))
    total_value = sum(a.expected_value_inr for a in ranked)
    return {
        "customer_id": profile.get("customer_id"),
        "name": name,
        "lead_tier": tier,
        "lead_tier_css": profile.get("lead_tier_css", ""),
        "composite_lead_score": profile.get("composite_lead_score"),
        "indicative_ticket_inr": indicative_ticket_inr(profile),
        "next_best_action": asdict(ranked[0]) if ranked else None,
        "actions": [asdict(a) for a in ranked],
        "total_expected_value_inr": total_value,
        "total_rm_minutes": sum(a.effort_minutes for a in ranked),
        "rm_minutes_saved": sum(a.rm_minutes_saved for a in ranked),
        "method": (
            "Expected value = (conversion delta in percentage points) × (indicative ticket size from "
            "affordable EMI × product tenor). Actions are ranked by expected rupees per RM minute. "
            "Deltas marked 'real re-score' come from the uplift simulator; the rest are documented "
            "POC assumptions to be calibrated in the 4-week RM A/B pilot."
        ),
    }


# --------------------------------------------------------------------------- #
# Portfolio view — "what should the branch do this morning"
# --------------------------------------------------------------------------- #
DEFAULT_RM_COUNT = 6
DEFAULT_PRODUCTIVE_MINUTES = 360  # 6 productive hours per RM per day


def build_portfolio_actions(
    ranked_profiles: list[dict],
    raw_by_id: dict[str, dict],
    rm_count: int = DEFAULT_RM_COUNT,
    minutes_per_rm: int = DEFAULT_PRODUCTIVE_MINUTES,
) -> dict:
    """Aggregate the NBA of every lead into a single day's branch work plan."""
    per_customer: list[dict] = []
    for profile in ranked_profiles:
        raw = raw_by_id.get(profile["customer_id"], {})
        nba = build_next_best_actions(profile, raw)
        top = nba["next_best_action"]
        if not top:
            continue
        per_customer.append(
            {
                "customer_id": nba["customer_id"],
                "name": nba["name"],
                "lead_tier": nba["lead_tier"],
                "lead_tier_css": nba["lead_tier_css"],
                "composite_lead_score": nba["composite_lead_score"],
                "action": top,
                "indicative_ticket_inr": nba["indicative_ticket_inr"],
            }
        )

    work_items = [c for c in per_customer if c["action"]["effort_minutes"] > 0]

    # SLA commitments (<=24h) are scheduled first — they are promises, not options.
    # Everything else is packed by expected rupees per RM minute.
    def _density(c: dict) -> int:
        return -c["action"]["value_per_rm_minute"]

    committed = sorted(
        [c for c in work_items if (c["action"]["sla_hours"] or 999) <= 24], key=_density
    )
    discretionary = sorted(
        [c for c in work_items if (c["action"]["sla_hours"] or 999) > 24], key=_density
    )

    capacity = rm_count * minutes_per_rm
    spent = 0
    scheduled: list[dict] = []
    for item in committed + discretionary:
        cost = item["action"]["effort_minutes"]
        if spent + cost > capacity:
            continue
        scheduled.append(item)
        spent += cost

    total_pipeline_value = sum(c["action"]["expected_value_inr"] for c in per_customer)
    scheduled_value = sum(c["action"]["expected_value_inr"] for c in scheduled)
    minutes_saved = sum(c["action"]["rm_minutes_saved"] for c in per_customer)

    by_code: dict[str, dict] = {}
    for item in per_customer:
        a = item["action"]
        row = by_code.setdefault(
            a["code"],
            {
                "code": a["code"],
                "title": PLAYBOOK_LABELS.get(a["code"], a["title"]),
                "channel": a["channel"],
                "owner": a["owner"],
                "category": a["category"],
                "sla_hours": a["sla_hours"],
                "leads": 0,
                "rm_minutes": 0,
                "expected_value_inr": 0,
                "rm_minutes_saved": 0,
            },
        )
        row["leads"] += 1
        row["rm_minutes"] += a["effort_minutes"]
        row["expected_value_inr"] += a["expected_value_inr"]
        row["rm_minutes_saved"] += a["rm_minutes_saved"]

    playbook = sorted(by_code.values(), key=lambda r: -r["expected_value_inr"])

    return {
        "total_leads": len(per_customer),
        "playbook": playbook,
        "today_queue": scheduled[:50],
        "queue_size": len(scheduled),
        "capacity_plan": {
            "rm_count": rm_count,
            "minutes_per_rm": minutes_per_rm,
            "total_minutes_available": capacity,
            "minutes_scheduled": spent,
            "utilisation_pct": round(spent / capacity * 100, 1) if capacity else 0,
            "actions_scheduled": len(scheduled),
            "actions_deferred": len(work_items) - len(scheduled),
            "scheduled_value_inr": scheduled_value,
            "pipeline_value_inr": total_pipeline_value,
            "value_captured_pct": round(scheduled_value / total_pipeline_value * 100, 1)
            if total_pipeline_value
            else 0,
        },
        "rm_minutes_saved_by_suppression": minutes_saved,
        "rm_hours_saved_by_suppression": round(minutes_saved / 60, 1),
        "suppressed_leads": sum(1 for c in per_customer if c["action"]["code"] == "suppress_outbound"),
        "sla_commitments": len([c for c in work_items if (c["action"]["sla_hours"] or 999) <= 24]),
        "method": (
            f"Every lead's top action is costed in RM minutes and expected rupees, then packed into "
            f"one day of branch capacity ({rm_count} RMs × {minutes_per_rm} productive minutes). "
            "24-hour SLA commitments are scheduled first; the rest is packed by expected rupees per "
            "RM minute. Suppressed leads return their 12 minutes to the queue."
        ),
    }
