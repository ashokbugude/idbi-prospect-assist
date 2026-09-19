"""
Ingest coercion and validation — the boundary between a bank feed and the scorer.

Synthetic data is clean by construction. A real sandbox feed is not: numbers
arrive as strings from CSV and JSON exports, absent values arrive as `null`
rather than a missing key, and ratios occasionally arrive outside 0–1.

Before this layer existed the engine assumed clean types and raised on contact
with any of them — `"85000"` for an income, or `null` for a ratio, returned an
HTTP 500. This module coerces what it can, records what it changed, and applies
the two hard requirements that `/governance` documents, so the ingest rules on
that page are enforced by code rather than asserted by prose.

Design rule: coercion never invents a value. An unparseable or null field is
dropped so the scorer's "unknown" handling applies, rather than being silently
replaced with a zero that would read as good news.
"""

from __future__ import annotations

from typing import Any

# Fields whose absence means the record cannot be scored at all.
REQUIRED_FIELDS = ("customer_id", "monthly_income")

INT_FIELDS = (
    "monthly_income", "estimated_monthly_disposable", "avg_monthly_balance",
    "monthly_credit_inflow", "monthly_commute_spend", "upi_retail_transactions",
    "salary_stability_months", "relationship_years", "age", "loan_page_visits_30d",
    "loan_calculator_uses", "bureau_enquiries_90d", "active_credit_accounts",
    "bureau_repayment_history_months", "inferred_monthly_income",
    "holistic_monthly_income",
)

# field -> (low, high); values outside are clamped and flagged, never dropped.
RATIO_FIELDS: dict[str, tuple[float, float]] = {
    "need_spend_ratio": (0.0, 1.0),
    "want_spend_ratio": (0.0, 1.0),
    "luxury_spend_ratio": (0.0, 1.0),
    "discretionary_spend_ratio": (0.0, 1.0),
    "savings_transfer_ratio": (0.0, 1.0),
    "salary_day_spend_ratio": (0.0, 1.0),
    "debt_to_income_ratio": (0.0, 1.5),
    "credit_utilization_pct": (0.0, 1.0),
    "geo_transaction_consistency": (0.0, 1.0),
    "multi_bank_income_share": (0.0, 1.0),
    "income_confidence": (0.0, 1.0),
    "upi_food_share": (0.0, 1.0),
    "upi_mobility_share": (0.0, 1.0),
    "upi_retail_share": (0.0, 1.0),
    "upi_entertainment_share": (0.0, 1.0),
    "upi_utilities_share": (0.0, 1.0),
}

FLOAT_FIELDS = ("avg_session_minutes",)

BOOL_FIELDS = (
    "pays_rent", "has_existing_home_loan", "has_mortgage", "has_auto_emi",
    "has_consumer_loan", "recent_large_debit", "electronics_shopping_flag",
    "festival_season_spend_spike", "has_other_bank_accounts",
    "application_started", "window_shopping_flag",
)

_TRUE = {"true", "t", "yes", "y", "1"}
_FALSE = {"false", "f", "no", "n", "0", ""}


def _as_number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace(",", "").replace("₹", "")
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in _TRUE:
            return True
        if lowered in _FALSE:
            return False
    return None


def coerce_customer(record: dict) -> tuple[dict, list[str]]:
    """
    Return a scoreable copy of the record plus a list of what had to be changed.

    Nothing is invented: a value that cannot be parsed is removed so the scorer's
    explicit unknown handling applies.
    """
    clean = dict(record)
    notes: list[str] = []

    for field in INT_FIELDS:
        if field not in clean:
            continue
        number = _as_number(clean[field])
        if number is None:
            del clean[field]
            notes.append(f"{field}: dropped (not a number)")
            continue
        if number < 0:
            # A negative income once scored *better* than a zero income.
            notes.append(f"{field}: negative value {number:g} floored to 0")
            number = 0.0
        if not isinstance(clean[field], int):
            notes.append(f"{field}: coerced to integer")
        clean[field] = int(number)

    for field, (low, high) in RATIO_FIELDS.items():
        if field not in clean:
            continue
        number = _as_number(clean[field])
        if number is None:
            del clean[field]
            notes.append(f"{field}: dropped (not a number)")
            continue
        if number < low or number > high:
            notes.append(f"{field}: {number:g} outside {low:g}–{high:g}, clamped")
            number = max(low, min(high, number))
        elif not isinstance(clean[field], float):
            notes.append(f"{field}: coerced to float")
        clean[field] = float(number)

    for field in FLOAT_FIELDS:
        if field not in clean:
            continue
        number = _as_number(clean[field])
        if number is None:
            del clean[field]
            notes.append(f"{field}: dropped (not a number)")
        else:
            clean[field] = max(0.0, float(number))

    for field in BOOL_FIELDS:
        if field not in clean:
            continue
        flag = _as_bool(clean[field])
        if flag is None:
            del clean[field]
            notes.append(f"{field}: dropped (not a boolean)")
        else:
            clean[field] = flag

    # A null string field is the same as an absent one.
    for field in ("customer_id", "name", "city", "segment", "employment_type",
                  "business_type", "credit_score_band"):
        if field in clean and clean[field] is None:
            del clean[field]

    return clean, notes


def validate_customer(record: dict) -> dict:
    """
    Apply the hard ingest gate documented on /governance.

    A record missing customer_id or monthly_income is rejected rather than scored
    on defaults — an empty record must never receive a plausible-looking tier.
    """
    clean, notes = coerce_customer(record)
    failures: list[str] = []

    identifier = str(clean.get("customer_id") or "").strip()
    if not identifier:
        failures.append("customer_id is missing or empty")

    income = clean.get("monthly_income")
    if income is None:
        failures.append("monthly_income is missing or not a number")
    elif income <= 0:
        failures.append(f"monthly_income must be positive (got {income})")

    return {
        "accepted": not failures,
        "customer_id": identifier or None,
        "failures": failures,
        "coercions": notes,
        "coercion_count": len(notes),
        "record": clean if not failures else None,
        "rule": (
            "customer_id and monthly_income are hard requirements. Everything else is "
            "coerced where possible and dropped where not, so an unparseable field is "
            "scored as unknown rather than as zero."
        ),
    }


def ingest_report(customers: list[dict]) -> dict[str, Any]:
    """Run the gate across a population — evidence for the data-quality page."""
    accepted = 0
    rejected: list[dict] = []
    coerced = 0
    reasons: dict[str, int] = {}

    for record in customers:
        result = validate_customer(record)
        if result["accepted"]:
            accepted += 1
        else:
            rejected.append({"customer_id": result["customer_id"], "failures": result["failures"]})
            for failure in result["failures"]:
                key = failure.split("(")[0].strip()
                reasons[key] = reasons.get(key, 0) + 1
        if result["coercion_count"]:
            coerced += 1

    total = len(customers) or 1
    return {
        "records": len(customers),
        "accepted": accepted,
        "rejected": len(rejected),
        "acceptance_pct": round(accepted / total * 100, 1),
        "records_needing_coercion": coerced,
        "rejection_reasons": [{"reason": k, "count": v} for k, v in sorted(reasons.items(), key=lambda kv: -kv[1])],
        "rejected_sample": rejected[:10],
    }
