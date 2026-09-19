"""
Responsible-AI layer — fairness audit, proxy register and DPDP governance evidence.

Track 02 differentiator
-----------------------
Every entrant will claim "explainable and compliant". This module *proves* it on
the live dataset, every time the page is loaded:

* which attributes the model is allowed to see, verified against the actual
  feature vector rather than a slide bullet;
* selection-rate parity across age, employment, geography and income, scored
  with the four-fifths (80%) rule used by fair-lending examiners;
* a proxy-risk register that names the features which *could* stand in for a
  protected attribute, and what caps that risk;
* explainability coverage — the share of leads that carry an adverse-action-ready
  reason, which is what an RBI/DPDP reviewer will actually ask for.

Findings are reported as they fall. A failing band is shown, not hidden.
"""

from __future__ import annotations

from app.features import FEATURE_NAMES

# Attributes that must never enter the model, directly or as a named field.
PROHIBITED_ATTRIBUTES = [
    ("gender / sex", "Protected attribute — not collected, not modelled."),
    ("religion", "Protected attribute — not collected, not modelled."),
    ("caste / community", "Protected attribute — not collected, not modelled."),
    ("race / ethnicity", "Protected attribute — not collected, not modelled."),
    ("marital status", "Not collected — historically correlated with gender-based denial."),
    ("disability / health", "Not collected — sensitive personal data under DPDP s.2."),
    ("political affiliation", "Not collected."),
    ("trade-union membership", "Not collected."),
    ("mother tongue / region of origin", "Not collected."),
    (
        "customer name / surname",
        "Present in the record for RM display only and excluded from every model feature — "
        "surname is a caste and community proxy in the Indian context.",
    ),
]

_PROHIBITED_TOKENS = (
    "gender", "sex", "religio", "caste", "race", "ethnic", "marital", "spouse",
    "disab", "pregnan", "health", "politic", "union", "community", "mother_tongue",
    "surname", "name",
)

# Features that are legitimate but could proxy a protected attribute.
PROXY_REGISTER = [
    {
        "feature": "age",
        "used": True,
        "proxy_for": "Age (protected in several fair-lending regimes)",
        "why_used": "Tenor feasibility — a 25-year home loan must mature before retirement.",
        "mitigation": "Product-fit preference only (+15 of 100 on home loan for ages 28–50). "
                      "No product is zeroed out on age; the affordability gate is what excludes.",
        "monitored": True,
    },
    {
        "feature": "employment_ordinal (salaried / self-employed / gig)",
        "used": True,
        "proxy_for": "Informal-sector and younger workers",
        "why_used": "Income volatility is a genuine repayment risk and is sized for, not penalised.",
        "mitigation": "Gig/self-employed receive conservative EMI sizing and an industry-margin "
                      "income model rather than exclusion. Selection-rate gap is reported below.",
        "monitored": True,
    },
    {
        "feature": "city (metro bonus in geo stability)",
        "used": False,
        "proxy_for": "Geography — the classic redlining vector",
        "why_used": "Metro presence is used only as a stability signal, not a scoring input.",
        "mitigation": "Capped at +15 of a 100-point geo sub-score that does not enter the composite "
                      "directly. Metro vs non-metro parity is reported below.",
        "monitored": True,
    },
    {
        "feature": "monthly_income / disposable income",
        "used": True,
        "proxy_for": "Socio-economic status",
        "why_used": "Repayment capacity is the lawful basis of the assessment.",
        "mitigation": "Affordability is assessed as a *ratio* (DTI, disposable share), so a "
                      "₹35k salaried customer can out-score a ₹1.2L over-leveraged one.",
        "monitored": True,
    },
    {
        "feature": "upi_*_share (merchant categories)",
        "used": True,
        "proxy_for": "Lifestyle, and indirectly diet/religion via merchant type",
        "why_used": "Spend mix is a discipline signal required by the Track 02 brief.",
        "mitigation": "Only five neutral aggregates (food, mobility, retail, entertainment, "
                      "utilities) are stored. No merchant name, no individual transaction, "
                      "reaches the model.",
        "monitored": False,
    },
]

DATA_INVENTORY = [
    {
        "category": "Account & transaction data",
        "fields": "credit inflow, average balance, spend ratios, EMI debits, UPI category shares",
        "purpose": "Repayment capacity and behavioural discipline assessment",
        "lawful_basis": "Existing customer relationship + DPDP notice at onboarding",
        "retention": "Rolling 90 days of derived aggregates; no raw statement retained",
        "minimisation": "Aggregated ratios only — individual merchant lines are not persisted",
    },
    {
        "category": "Other-bank data (Account Aggregator)",
        "fields": "other-bank monthly inflow, holistic income estimate",
        "purpose": "Holistic income view where income sits outside IDBI",
        "lawful_basis": "Explicit, revocable, purpose-limited AA consent artefact",
        "retention": "Consent validity window (30 days), then derived figure only",
        "minimisation": "Only inflow aggregates are pulled — DEPOSIT / RECURRING_DEPOSIT scope",
    },
    {
        "category": "Bureau data",
        "fields": "band, enquiries 90d, utilisation, active lines, repayment history",
        "purpose": "Cross-check of stated obligations and delinquency safety",
        "lawful_basis": "Credit Information Companies (Regulation) Act purpose test",
        "retention": "Per bureau contract; normalised score cached for the scoring run",
        "minimisation": "No account-level tradeline detail is surfaced to the RM",
    },
    {
        "category": "Digital footprint",
        "fields": "loan page visits, calculator uses, session minutes, application started",
        "purpose": "Purchase intent and window-shopping detection",
        "lawful_basis": "First-party analytics on IDBI-owned journeys, consented",
        "retention": "30-day rolling window",
        "minimisation": "First-party only — no third-party tracking or device fingerprinting",
    },
    {
        "category": "Identity",
        "fields": "customer id, display name, city",
        "purpose": "RM workflow only",
        "lawful_basis": "Existing relationship",
        "retention": "System of record",
        "minimisation": "Excluded from every model feature; maskable for demo and audit review",
    },
]

FOUR_FIFTHS = 0.80
WATCH_THRESHOLD = 0.60

METRO_CITIES = {"Mumbai", "Delhi", "Bengaluru", "Hyderabad", "Chennai", "Pune"}


# --------------------------------------------------------------------------- #
# Segment definitions
# --------------------------------------------------------------------------- #
def _age_band(age: int) -> str:
    if age < 31:
        return "24–30"
    if age < 41:
        return "31–40"
    if age < 51:
        return "41–50"
    return "51+"


def _income_band(income: int) -> str:
    if income < 40_000:
        return "< ₹40k"
    if income < 70_000:
        return "₹40k–₹70k"
    if income < 100_000:
        return "₹70k–₹1L"
    return "≥ ₹1L"


SEGMENTS = [
    {
        "dimension": "Age band",
        "model_input": True,
        "key": lambda raw, prof: _age_band(int(raw.get("age") or 35)),
        "order": ["24–30", "31–40", "41–50", "51+"],
    },
    {
        "dimension": "Employment type",
        "model_input": True,
        "key": lambda raw, prof: str(raw.get("employment_type") or "salaried").replace("_", " ").title(),
        "order": ["Salaried", "Self Employed", "Gig"],
    },
    {
        "dimension": "Geography",
        "model_input": False,
        "key": lambda raw, prof: "Metro" if raw.get("city") in METRO_CITIES else "Non-metro",
        "order": ["Metro", "Non-metro"],
    },
    {
        "dimension": "Income band",
        "model_input": True,
        "key": lambda raw, prof: _income_band(int(raw.get("monthly_income") or 0)),
        "order": ["< ₹40k", "₹40k–₹70k", "₹70k–₹1L", "≥ ₹1L"],
    },
]


def _status(ratio: float) -> str:
    if ratio >= FOUR_FIFTHS:
        return "pass"
    if ratio >= WATCH_THRESHOLD:
        return "watch"
    return "review"


def _segment_report(spec: dict, rows: list[tuple[dict, dict]]) -> dict:
    buckets: dict[str, list[dict]] = {}
    for raw, prof in rows:
        buckets.setdefault(spec["key"](raw, prof), []).append(prof)

    groups: list[dict] = []
    for label, profiles in buckets.items():
        n = len(profiles)
        if n == 0:
            continue
        selected = sum(1 for p in profiles if p.get("rm_call_eligible"))
        quality = sum(1 for p in profiles if p["lead_tier"] == "Quality Lead")
        window = sum(1 for p in profiles if p["lead_tier"] == "Window-shop Risk")
        groups.append(
            {
                "group": label,
                "n": n,
                "share_pct": 0.0,
                "rm_queue_rate_pct": round(selected / n * 100, 1),
                "quality_rate_pct": round(quality / n * 100, 1),
                "window_shop_rate_pct": round(window / n * 100, 1),
                "avg_composite": round(sum(p["composite_lead_score"] for p in profiles) / n, 1),
            }
        )

    total = sum(g["n"] for g in groups) or 1
    best = max((g["rm_queue_rate_pct"] for g in groups), default=0.0)
    for g in groups:
        g["share_pct"] = round(g["n"] / total * 100, 1)
        # Groups below the minimum cell size are not scored — the ratio would be noise.
        if g["n"] < 15:
            g["disparate_impact_ratio"] = None
            g["status"] = "insufficient sample"
            continue
        ratio = round(g["rm_queue_rate_pct"] / best, 2) if best else 1.0
        g["disparate_impact_ratio"] = ratio
        g["status"] = _status(ratio)

    order = {label: i for i, label in enumerate(spec["order"])}
    groups.sort(key=lambda g: order.get(g["group"], 99))

    scored = [g for g in groups if g["disparate_impact_ratio"] is not None]
    min_ratio = min((g["disparate_impact_ratio"] for g in scored), default=1.0)
    failing = [g["group"] for g in scored if g["status"] == "review"]
    watching = [g["group"] for g in scored if g["status"] == "watch"]

    return {
        "dimension": spec["dimension"],
        "model_input": spec["model_input"],
        "groups": groups,
        "reference_group_rate_pct": best,
        "min_disparate_impact_ratio": min_ratio,
        "status": _status(min_ratio),
        "failing_groups": failing,
        "watch_groups": watching,
    }


# --------------------------------------------------------------------------- #
# Feature-level guarantees
# --------------------------------------------------------------------------- #
def audit_prohibited_attributes(customers: list[dict]) -> dict:
    """Verify against the live feature vector — not a slide bullet."""
    record_keys = sorted({k for c in customers[:50] for k in c.keys()})
    offending_features = [
        f for f in FEATURE_NAMES if any(tok in f.lower() for tok in _PROHIBITED_TOKENS)
    ]
    offending_fields = [
        k for k in record_keys if any(tok in k.lower() for tok in _PROHIBITED_TOKENS)
    ]
    return {
        "feature_count": len(FEATURE_NAMES),
        "record_field_count": len(record_keys),
        "prohibited_features_found": offending_features,
        "prohibited_fields_in_record": offending_fields,
        "passed": not offending_features,
        "note": (
            "Checked programmatically against FEATURE_NAMES on every page load. "
            "'name' exists on the customer record for RM display and is deliberately "
            "absent from the feature vector."
        ),
        "attributes": [{"attribute": a, "treatment": t} for a, t in PROHIBITED_ATTRIBUTES],
    }


def explainability_coverage(profiles: list[dict]) -> dict:
    total = len(profiles) or 1
    dims = ("repayment_capacity", "purchase_intent", "behavioral_discipline")
    full = sum(1 for p in profiles if all((p.get(d) or {}).get("reasons") for d in dims))
    suppressed = [p for p in profiles if not p.get("rm_call_eligible")]
    suppressed_with_reason = sum(
        1 for p in suppressed if (p.get("purchase_intent") or {}).get("reasons")
    )
    return {
        "leads_scored": len(profiles),
        "all_three_dimensions_explained_pct": round(full / total * 100, 1),
        "deprioritised_leads": len(suppressed),
        "deprioritised_with_reason_pct": round(
            suppressed_with_reason / (len(suppressed) or 1) * 100, 1
        ),
        "note": (
            "Every deprioritised lead carries a machine-readable reason, so a suppression can be "
            "explained to the customer or an examiner. Deprioritisation is a contact-prioritisation "
            "decision, not a credit rejection, and no adverse credit action is recorded against it."
        ),
    }


def governance_controls() -> list[dict]:
    return [
        {
            "control": "No automated credit decision",
            "detail": "The engine ranks and explains. Sanction authority stays with the underwriter.",
            "evidence": "/architecture · every RM brief carries the human-in-loop disclaimer",
        },
        {
            "control": "Model nudge ceiling",
            "detail": "XGBoost may move a composite score by at most ±8 points and may never demote a Quality Lead.",
            "evidence": "/api/ml/model-card → guardrails",
        },
        {
            "control": "Rules remain primary",
            "detail": "If the model is unavailable the service degrades to the deterministic rule engine "
                      "rather than failing — the tier a customer receives is always reproducible.",
            "evidence": "scoring.py → score_customer() fallback path",
        },
        {
            "control": "Deterministic reproducibility",
            "detail": "Fixed seed, versioned model artefact and pure-function scoring — the same record "
                      "always yields the same tier, which is what makes an audit possible.",
            "evidence": "tests/test_scoring.py → test_ranking_is_deterministic",
        },
        {
            "control": "Consent artefact per external pull",
            "detail": "Multi-bank data is only fetched against an explicit, time-boxed AA consent id.",
            "evidence": "/multi-bank · POST /api/aa/consent",
        },
        {
            "control": "Purpose limitation",
            "detail": "Scoring inputs are limited to repayment, intent, discipline and delinquency safety. "
                      "No marketing profile is built or sold.",
            "evidence": "Data inventory below",
        },
        {
            "control": "Access control",
            "detail": "RM session gate on all customer views; maps to IDBI SSO/LDAP in production.",
            "evidence": "auth.py · /login",
        },
    ]


# --------------------------------------------------------------------------- #
# Mitigation: does the AA lever actually close the gap?
# --------------------------------------------------------------------------- #
BUSINESS_NECESSITY = {
    "Income band": (
        "Repayment capacity is the lawful and necessary basis of a lending decision, so some "
        "spread across income bands is expected and defensible. What is *not* defensible is "
        "excluding a band from credit altogether — so the audit also reports product eligibility, "
        "which shows lower bands are routed to smaller-ticket products rather than dropped."
    ),
    "Employment type": (
        "Income volatility in gig and self-employed cashflows is a genuine repayment risk. The "
        "engine's answer is conservative EMI sizing and an industry-margin income model, not "
        "exclusion — and the gap narrows materially once other-bank income is visible."
    ),
    "Age band": (
        "Age enters only as a tenor-feasibility preference on long-tenor products. No product is "
        "closed on age and the affordability gate is what actually binds."
    ),
    "Geography": (
        "City is not a scoring input. It contributes only to a geo-stability sub-score that does "
        "not enter the composite directly."
    ),
}

MITIGATION_ACTIONS = {
    "Employment type": [
        "Offer Account Aggregator consent first to every gig and self-employed lead — their income "
        "is the most likely to sit outside IDBI (simulated below).",
        "Keep the self-employed industry-margin model (config.SELF_EMPLOYED_MARGINS) under "
        "quarterly review against realised repayment.",
        "Track approval *and* realised delinquency by employment type in the pilot, so the risk "
        "premium can be justified or removed with evidence.",
    ],
    "Income band": [
        "Report product-ladder eligibility, not just RM-queue rate — a ₹35k customer eligible for a "
        "consumer-durable loan has not been denied credit.",
        "Route lower bands to assisted digital journeys, which cost no RM minutes, rather than "
        "suppressing them.",
        "Re-test parity after the AA uplift, which disproportionately helps thin-file customers.",
    ],
    "Age band": [
        "Monitor the 31–40 band each scoring run; investigate if the ratio falls below 0.8.",
    ],
    "Geography": [
        "Continue reporting metro vs non-metro parity every run.",
    ],
}


def _selection_rate(profiles: list[dict]) -> float:
    if not profiles:
        return 0.0
    return sum(1 for p in profiles if p.get("rm_call_eligible")) / len(profiles) * 100


def simulate_aa_mitigation(customers: list[dict], spec: dict) -> dict:
    """
    Counterfactual: if every lead in this dimension granted AA consent, does the
    selection-rate gap close? Uses the same rule engine as production scoring.
    """
    from app.scoring import score_customer_rules
    from app.uplift import LEVERS_BY_CODE

    lever = LEVERS_BY_CODE["aa_consent"]
    before: dict[str, list[dict]] = {}
    after: dict[str, list[dict]] = {}

    for raw in customers:
        base = score_customer_rules(raw)
        label = spec["key"](raw, base)
        before.setdefault(label, []).append(base)

        candidate = dict(raw)
        if not candidate.get("has_other_bank_accounts"):
            lever.apply(candidate)
        after.setdefault(label, []).append(score_customer_rules(candidate))

    rows: list[dict] = []
    best_before = max((_selection_rate(v) for v in before.values()), default=0.0)
    best_after = max((_selection_rate(v) for v in after.values()), default=0.0)
    for label in before:
        rate_b = _selection_rate(before[label])
        rate_a = _selection_rate(after[label])
        di_b = round(rate_b / best_before, 2) if best_before else 1.0
        di_a = round(rate_a / best_after, 2) if best_after else 1.0
        rows.append(
            {
                "group": label,
                "n": len(before[label]),
                "rate_before_pct": round(rate_b, 1),
                "rate_after_pct": round(rate_a, 1),
                "di_before": di_b,
                "di_after": di_a,
                "di_change": round(di_a - di_b, 2),
                "status_after": _status(di_a) if len(before[label]) >= 15 else "insufficient sample",
            }
        )

    order = {label: i for i, label in enumerate(spec["order"])}
    rows.sort(key=lambda r: order.get(r["group"], 99))
    scored = [r for r in rows if r["n"] >= 15]
    min_before = min((r["di_before"] for r in scored), default=1.0)
    min_after = min((r["di_after"] for r in scored), default=1.0)

    return {
        "dimension": spec["dimension"],
        "lever": lever.label,
        "rows": rows,
        "min_di_before": min_before,
        "min_di_after": min_after,
        "improvement": round(min_after - min_before, 2),
        "closes_gap": min_after >= FOUR_FIFTHS,
        "note": (
            "Counterfactual re-score: every lead without a multi-bank footprint is re-run as if "
            "Account Aggregator consent had been granted. This is the mitigation the RM can "
            "actually execute today — the engine quantifies whether it works."
        ),
    }


def product_eligibility_by_segment(customers: list[dict], ranked_profiles: list[dict], spec: dict) -> list[dict]:
    """Share of each group eligible for at least one product — 'not called' is not 'not lendable'."""
    by_id = {p["customer_id"]: p for p in ranked_profiles}
    buckets: dict[str, list[dict]] = {}
    for raw in customers:
        prof = by_id.get(raw["customer_id"])
        if not prof:
            continue
        buckets.setdefault(spec["key"](raw, prof), []).append(prof)

    rows = []
    for label, profiles in buckets.items():
        n = len(profiles) or 1
        eligible = sum(1 for p in profiles if any(s["eligible"] for s in p.get("all_scores", [])))
        rows.append(
            {
                "group": label,
                "n": len(profiles),
                "any_product_eligible_pct": round(eligible / n * 100, 1),
                "rm_queue_rate_pct": round(_selection_rate(profiles), 1),
            }
        )
    order = {label: i for i, label in enumerate(spec["order"])}
    rows.sort(key=lambda r: order.get(r["group"], 99))
    return rows


def build_fairness_report(customers: list[dict], ranked_profiles: list[dict]) -> dict:
    by_id = {p["customer_id"]: p for p in ranked_profiles}
    rows = [(c, by_id[c["customer_id"]]) for c in customers if c["customer_id"] in by_id]

    segments = [_segment_report(spec, rows) for spec in SEGMENTS]
    for seg, spec in zip(segments, SEGMENTS, strict=True):
        seg["business_necessity"] = BUSINESS_NECESSITY.get(seg["dimension"], "")
        seg["mitigation_actions"] = MITIGATION_ACTIONS.get(seg["dimension"], [])
    worst = min((s["min_disparate_impact_ratio"] for s in segments), default=1.0)
    review = [s["dimension"] for s in segments if s["status"] == "review"]
    watch = [s["dimension"] for s in segments if s["status"] == "watch"]

    if review:
        headline = f"{len(review)} dimension(s) below the four-fifths threshold — mitigation required before pilot"
    elif watch:
        headline = f"All dimensions above the four-fifths threshold; {len(watch)} on watch"
    else:
        headline = "All audited dimensions pass the four-fifths rule"

    return {
        "population": len(rows),
        "headline": headline,
        "overall_status": "review" if review else ("watch" if watch else "pass"),
        "worst_disparate_impact_ratio": worst,
        "four_fifths_threshold": FOUR_FIFTHS,
        "segments": segments,
        "mitigation_simulations": [
            simulate_aa_mitigation(customers, spec)
            for spec in SEGMENTS
            if next(
                (s["status"] for s in segments if s["dimension"] == spec["dimension"]), "pass"
            ) in ("watch", "review")
        ],
        "product_eligibility": {
            spec["dimension"]: product_eligibility_by_segment(customers, ranked_profiles, spec)
            for spec in SEGMENTS
            if spec["dimension"] in ("Income band", "Employment type")
        },
        "prohibited_attribute_audit": audit_prohibited_attributes(customers),
        "proxy_register": PROXY_REGISTER,
        "explainability": explainability_coverage(ranked_profiles),
        "governance_controls": governance_controls(),
        "data_inventory": DATA_INVENTORY,
        "method": (
            "Selection rate = share of a group placed in the RM call queue (Quality + Serious). "
            "Disparate impact ratio = group selection rate ÷ highest group selection rate; the "
            "four-fifths (80%) rule is the fair-lending convention used by examiners. Groups with "
            "fewer than 15 leads are reported but not scored, because the ratio would be noise."
        ),
        "disclaimer": (
            "Audited on the synthetic round-1 dataset (n=200, seed=42). The same audit runs unchanged "
            "against IDBI sandbox data post-shortlist; the numbers will move, the method will not."
        ),
    }
