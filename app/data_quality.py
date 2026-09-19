"""
Data quality and graceful degradation — what happens when the sandbox is messy.

Round 2 is an integration exercise. Synthetic data is complete by construction;
real bank data is not. Bureau pulls fail, digital footprints are absent for
branch-acquired customers, AA consent is declined, and fields arrive out of range.

Two questions get answered here, both computed rather than asserted:

* **Completeness** — per field, against the sandbox contract, with required and
  optional separated so a missing optional field is not reported as a failure.
* **Degradation** — for each sandbox field group, the whole book is re-scored
  with that group removed and the resulting tier churn is measured. That turns
  "the engine degrades gracefully" from a claim into a number.
"""

from __future__ import annotations

from typing import Any

from app.scoring import TIER_ORDER, score_customer_rules

# Field groups mirror the three sandbox endpoints in
# docs/SANDBOX_DATA_FIELD_SUBMISSION.md, so this page reads as an integration
# readiness check rather than a generic data audit.
FIELD_GROUPS: dict[str, dict[str, Any]] = {
    "transactions": {
        "label": "Transactions API",
        "endpoint": "/sandbox/v1/customers/{id}/transactions",
        "required": [
            "monthly_credit_inflow", "avg_monthly_balance", "need_spend_ratio",
            "luxury_spend_ratio", "savings_transfer_ratio", "salary_day_spend_ratio",
            "debt_to_income_ratio", "estimated_monthly_disposable",
        ],
        "optional": ["monthly_commute_spend", "multi_bank_income_share", "upi_retail_transactions"],
        "degradation": (
            "Income falls back to the stated salary and the inference confidence is "
            "published as low; affordability is sized on stated income only."
        ),
    },
    "bureau": {
        "label": "Bureau API",
        "endpoint": "/sandbox/v1/customers/{id}/bureau",
        "required": [
            "credit_score_band", "bureau_enquiries_90d", "active_credit_accounts",
            "credit_utilization_pct", "bureau_repayment_history_months",
        ],
        "optional": [],
        "degradation": (
            "Bureau contribution is neutralised rather than assumed good; the lead is "
            "flagged for manual underwriter review before any offer is made."
        ),
    },
    "digital": {
        "label": "Digital footprint API",
        "endpoint": "/sandbox/v1/customers/{id}/digital",
        "required": [
            "loan_page_visits_30d", "loan_calculator_uses", "avg_session_minutes",
            "application_started", "window_shopping_flag",
        ],
        "optional": [],
        "degradation": (
            "Purchase intent is scored from transaction signals alone. Branch-acquired "
            "customers must not be penalised for having no digital trail."
        ),
    },
    "multi_bank": {
        "label": "Account Aggregator (consented)",
        "endpoint": "AA consent + FIP fetch",
        "required": [],
        "optional": ["has_other_bank_accounts", "multi_bank_income_share"],
        "degradation": (
            "Single-bank IDBI view only. Expected for any customer who declines consent — "
            "declining must never reduce the score, only the ceiling."
        ),
    },
    "identity": {
        "label": "Customer profile (shared header)",
        "endpoint": "All three endpoints",
        "required": ["customer_id", "monthly_income", "employment_type", "city", "age"],
        "optional": ["business_type", "relationship_years", "segment"],
        "degradation": (
            "customer_id and monthly_income are hard requirements — a record missing "
            "either is rejected at ingest rather than scored on defaults."
        ),
    },
}

# Fields that must sit inside a range to be believable.
RANGE_RULES: dict[str, tuple[float, float]] = {
    "need_spend_ratio": (0.0, 1.0),
    "luxury_spend_ratio": (0.0, 1.0),
    "want_spend_ratio": (0.0, 1.0),
    "savings_transfer_ratio": (0.0, 1.0),
    "salary_day_spend_ratio": (0.0, 1.0),
    "debt_to_income_ratio": (0.0, 1.5),
    "credit_utilization_pct": (0.0, 1.0),
    "geo_transaction_consistency": (0.0, 1.0),
    "multi_bank_income_share": (0.0, 1.0),
    "avg_session_minutes": (0.0, 600.0),
    "age": (18.0, 100.0),
    "monthly_income": (0.0, 100_000_000.0),
}

CRITICAL_FIELDS = {"customer_id", "monthly_income"}


def _field_stats(customers: list[dict], field: str) -> dict[str, Any]:
    n = len(customers) or 1
    present = 0
    nulls = 0
    zeros = 0
    out_of_range = 0
    lo, hi = RANGE_RULES.get(field, (None, None))

    for c in customers:
        if field not in c or c[field] is None:
            nulls += 1
            continue
        present += 1
        value = c[field]
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            if value == 0:
                zeros += 1
            if lo is not None and not (lo <= float(value) <= hi):
                out_of_range += 1
        elif isinstance(value, str) and not value.strip():
            zeros += 1

    return {
        "field": field,
        "present_pct": round(present / n * 100, 1),
        "missing_pct": round(nulls / n * 100, 1),
        "zero_pct": round(zeros / n * 100, 1),
        "out_of_range_pct": round(out_of_range / n * 100, 1),
        "range_rule": f"{lo:g} – {hi:g}" if lo is not None else "—",
        "critical": field in CRITICAL_FIELDS,
        "status": (
            "fail" if nulls and field in CRITICAL_FIELDS
            else "fail" if out_of_range
            else "warn" if nulls
            else "pass"
        ),
    }


def completeness_report(customers: list[dict]) -> list[dict]:
    groups = []
    for key, spec in FIELD_GROUPS.items():
        required = [_field_stats(customers, f) for f in spec["required"]]
        optional = [_field_stats(customers, f) for f in spec["optional"]]
        worst = "pass"
        for row in required:
            if row["status"] == "fail":
                worst = "fail"
                break
            if row["status"] == "warn":
                worst = "warn"
        required_present = (
            round(sum(r["present_pct"] for r in required) / len(required), 1) if required else 100.0
        )
        groups.append({
            "key": key,
            "label": spec["label"],
            "endpoint": spec["endpoint"],
            "degradation": spec["degradation"],
            "required_fields": required,
            "optional_fields": optional,
            "required_completeness_pct": required_present,
            "status": worst,
        })
    return groups


def _strip_group(customer: dict, group_key: str) -> dict:
    spec = FIELD_GROUPS[group_key]
    stripped = dict(customer)
    for field in spec["required"] + spec["optional"]:
        if field in CRITICAL_FIELDS:
            continue  # ingest would have rejected the record, not scored it
        stripped.pop(field, None)
    return stripped


def degradation_impact(customers: list[dict], baseline: list[dict] | None = None) -> list[dict]:
    """
    Re-score the whole book with each sandbox group removed and measure what
    actually changes. Nothing here is asserted — every number is a re-score.
    """
    base = baseline or [score_customer_rules(c) for c in customers]
    base_by_id = {p["customer_id"]: p for p in base}
    base_queue = {p["customer_id"] for p in base if p.get("rm_call_eligible")}

    results = []
    for key, spec in FIELD_GROUPS.items():
        if not (spec["required"] or spec["optional"]):
            continue
        changed = 0
        promoted = 0
        demoted = 0
        score_delta_total = 0.0
        errors = 0
        after_queue: set[str] = set()

        for customer in customers:
            try:
                scored = score_customer_rules(_strip_group(customer, key))
            except Exception:
                errors += 1
                continue
            before = base_by_id.get(customer["customer_id"])
            if not before:
                continue
            if scored.get("rm_call_eligible"):
                after_queue.add(customer["customer_id"])
            score_delta_total += scored["composite_lead_score"] - before["composite_lead_score"]
            if scored["lead_tier"] != before["lead_tier"]:
                changed += 1
                if TIER_ORDER[scored["lead_tier"]] < TIER_ORDER[before["lead_tier"]]:
                    promoted += 1
                else:
                    demoted += 1

        n = len(customers) or 1
        churn_pct = round(changed / n * 100, 1)
        results.append({
            "key": key,
            "label": spec["label"],
            "degradation": spec["degradation"],
            "fields_removed": len(spec["required"]) + len(spec["optional"]),
            "tier_churn_pct": churn_pct,
            "tiers_changed": changed,
            "promoted": promoted,
            "demoted": demoted,
            "avg_score_delta": round(score_delta_total / n, 2),
            "rm_queue_before": len(base_queue),
            "rm_queue_after": len(after_queue),
            "rm_queue_delta": len(after_queue) - len(base_queue),
            "crashes": errors,
            "resilience": (
                "fail" if errors
                else "high" if churn_pct < 10
                else "moderate" if churn_pct < 30
                else "low"
            ),
        })
    results.sort(key=lambda r: -r["tier_churn_pct"])
    return results


def build_data_quality_report(customers: list[dict], baseline: list[dict] | None = None) -> dict[str, Any]:
    from app.ingest import ingest_report

    groups = completeness_report(customers)
    degradation = degradation_impact(customers, baseline)
    failing = [g for g in groups if g["status"] == "fail"]
    crashes = sum(d["crashes"] for d in degradation)
    worst = degradation[0] if degradation else None

    return {
        "population": len(customers),
        "ingest": ingest_report(customers),
        "groups": groups,
        "degradation": degradation,
        "failing_groups": [g["label"] for g in failing],
        "total_crashes": crashes,
        "survives_every_group_loss": crashes == 0,
        "most_load_bearing": worst["label"] if worst else None,
        "headline": (
            f"Every sandbox field group can be removed without a single scoring failure; "
            f"the most load-bearing is {worst['label']} at {worst['tier_churn_pct']}% tier churn."
            if crashes == 0 and worst
            else f"{crashes} scoring failures under missing-data conditions — fix before integration."
        ),
        "method": (
            "Completeness is measured per field against the sandbox contract. Degradation is "
            "measured by removing each group from every record and re-scoring the whole book "
            "through the production rule engine — the churn shown is what would actually happen."
        ),
        "ingest_rules": [
            ("customer_id, monthly_income", "Hard reject at ingest — never scored on a default. Enforced by ingest.validate_customer()."),
            ("Numbers sent as strings", "Coerced (\"1,25,000\" and \"85000\" both parse); unparseable values are dropped, not zeroed."),
            ("null instead of an absent key", "Treated as absent so the scorer's unknown handling applies."),
            ("Negative amounts", "Floored to zero and flagged — a negative income must never outscore a zero one."),
            ("Ratio fields outside 0–1", "Clamped and flagged; the record is scored but marked for review."),
            ("Bureau group absent", "Neutral contribution, routed to manual underwriter review."),
            ("Digital group absent", "Intent scored from transactions only — no penalty for branch-acquired customers."),
            ("AA declined", "Single-bank view. Declining consent lowers the ceiling, never the score."),
        ],
    }
