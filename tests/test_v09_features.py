"""Tests for v0.9.0 — outcome loop, audit log, drift monitoring, data quality, vernacular."""

from __future__ import annotations

import re

import pytest

from app.data_generator import generate_dataset
from app.scoring import LEAD_TIERS, rank_customers, score_customer_rules


# --------------------------------------------------------------------------- #
# Outcome feedback loop
# --------------------------------------------------------------------------- #
@pytest.fixture
def outcome_store(tmp_path, monkeypatch):
    """Point the append-only store at a temp file so tests never touch real data."""
    import app.outcomes as outcomes

    monkeypatch.setattr(outcomes, "DATA_DIR", tmp_path)
    monkeypatch.setattr(outcomes, "OUTCOME_LOG", tmp_path / "outcomes.jsonl")
    monkeypatch.setattr(outcomes, "_cache", None)
    yield outcomes
    monkeypatch.setattr(outcomes, "_cache", None)


def test_outcome_is_appended_and_persisted(outcome_store):
    rec = outcome_store.record_outcome("IDBI-L10010", "loan_booked", "Quality Lead", rm_id="RM-01")
    assert rec["persisted"] is True
    assert rec["converted"] is True and rec["contacted"] is True
    assert outcome_store.OUTCOME_LOG.exists()
    assert len(outcome_store.OUTCOME_LOG.read_text(encoding="utf-8").strip().splitlines()) == 1


def test_a_correction_supersedes_without_rewriting_history(outcome_store):
    outcome_store.record_outcome("IDBI-L10010", "not_interested", "Quality Lead")
    outcome_store.record_outcome("IDBI-L10010", "loan_booked", "Quality Lead")

    lines = outcome_store.OUTCOME_LOG.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2, "the earlier record must still be on disk"
    latest = outcome_store.latest_per_customer()
    assert latest["IDBI-L10010"]["disposition"] == "loan_booked"


def test_unknown_disposition_is_rejected(outcome_store):
    with pytest.raises(ValueError):
        outcome_store.record_outcome("IDBI-L10010", "sold_them_a_boat", "Quality Lead")


def test_unreachable_leads_are_excluded_from_the_denominator(outcome_store):
    """An unreachable customer is not a failed pitch."""
    for i in range(10):
        outcome_store.record_outcome(f"IDBI-L{i:05d}", "not_reachable", "Serious")
    for i in range(10, 14):
        outcome_store.record_outcome(f"IDBI-L{i:05d}", "loan_booked", "Serious")

    row = next(r for r in outcome_store.calibration_by_tier() if r["tier"] == "Serious")
    assert row["contacted"] == 4, "not_reachable must not count as contact"
    assert row["converted"] == 4
    assert row["observed_conversion_pct"] == 100.0


def test_calibration_flags_divergence_from_the_assumption(outcome_store):
    for i in range(40):
        # Quality Lead is assumed at 38%; book every one of them.
        outcome_store.record_outcome(f"IDBI-L{i:05d}", "loan_booked", "Quality Lead")
    row = next(r for r in outcome_store.calibration_by_tier() if r["tier"] == "Quality Lead")
    assert row["status"] == "diverging"
    assert row["delta_pp"] > 5


def test_retrain_readiness_requires_labels_and_positives(outcome_store):
    assert outcome_store.training_readiness()["ready_to_retrain"] is False
    for i in range(outcome_store.RETRAIN_THRESHOLD + 5):
        disposition = "loan_booked" if i < 25 else "not_interested"
        outcome_store.record_outcome(f"IDBI-L{i:05d}", disposition, "Serious")
    readiness = outcome_store.training_readiness()
    assert readiness["usable_labels"] >= outcome_store.RETRAIN_THRESHOLD
    assert readiness["positive_labels"] >= 20
    assert readiness["ready_to_retrain"] is True
    assert readiness["blocker"] is None


# --------------------------------------------------------------------------- #
# Decision audit log
# --------------------------------------------------------------------------- #
@pytest.fixture
def audit_store(tmp_path, monkeypatch):
    import app.audit as audit

    monkeypatch.setattr(audit, "DATA_DIR", tmp_path)
    monkeypatch.setattr(audit, "AUDIT_LOG", tmp_path / "audit_log.jsonl")
    monkeypatch.setattr(audit, "_cache", None)
    yield audit
    monkeypatch.setattr(audit, "_cache", None)


def test_audit_entry_carries_versions_and_reasons(audit_store):
    entry = audit_store.record(
        "lead_decision",
        customer_id="IDBI-L10010",
        summary="Quality Lead",
        reason_codes=["Strong disposable income", "Application started"],
    )
    assert entry["engine_version"]
    assert entry["model_version"]
    assert entry["reason_codes"] == ["Strong disposable income", "Application started"]
    assert entry["at"].endswith("+00:00"), "timestamps must be UTC"


def test_audit_log_is_append_only_and_queryable(audit_store):
    audit_store.record("lead_decision", customer_id="A")
    audit_store.record("outcome_recorded", customer_id="A")
    audit_store.record("lead_decision", customer_id="B")

    assert len(audit_store.query(limit=50)) == 3
    assert len(audit_store.query(event_type="lead_decision")) == 2
    assert len(audit_store.query(customer_id="A")) == 2
    # newest first
    assert audit_store.query(limit=1)[0]["customer_id"] == "B"


def test_audit_report_summarises_coverage(audit_store):
    data = generate_dataset(20, seed=42)
    audit_store.record_lead_decisions(rank_customers(data))
    report = audit_store.build_audit_report()
    assert report["leads_with_decision_record"] == 20
    assert report["total_entries"] == 20
    assert any(e["event_type"] == "lead_decision" for e in report["entries_by_type"])


# --------------------------------------------------------------------------- #
# Drift monitoring
# --------------------------------------------------------------------------- #
def test_psi_is_zero_for_an_identical_population():
    from app.monitoring import population_stability_index

    values = [float(v) for v in range(200)]
    assert population_stability_index(values, list(values)) == 0.0


def test_psi_detects_a_shifted_population():
    from app.monitoring import population_stability_index

    reference = [float(v) for v in range(200)]
    shifted = [v * 3 + 400 for v in reference]
    assert population_stability_index(reference, shifted) > 0.25


def test_live_population_matches_its_training_reference():
    from app.monitoring import build_monitoring_report

    data = generate_dataset(200, seed=42)
    report = build_monitoring_report(data)
    assert report["live"]["overall_band"] == "stable"
    assert report["live"]["retrain_recommended"] is False


def test_the_drift_alarm_actually_fires():
    """A monitor nobody has seen alarm is not a monitor."""
    from app.monitoring import build_monitoring_report

    report = build_monitoring_report(generate_dataset(200, seed=42))
    alarm = report["alarm_scenario"]
    assert alarm["retrain_recommended"] is True
    assert alarm["flagged_count"] >= 3
    assert alarm["max_psi"] > 0.25


# --------------------------------------------------------------------------- #
# Data quality and degradation
# --------------------------------------------------------------------------- #
def test_no_field_group_can_crash_the_scorer():
    from app.data_quality import build_data_quality_report

    data = generate_dataset(200, seed=42)
    baseline = [score_customer_rules(c) for c in data]
    report = build_data_quality_report(data, baseline)
    assert report["total_crashes"] == 0
    assert report["survives_every_group_loss"] is True


def test_losing_a_data_source_never_inflates_the_queue():
    """Missing data must shrink the confident queue, never grow it."""
    from app.data_quality import build_data_quality_report

    data = generate_dataset(200, seed=42)
    baseline = [score_customer_rules(c) for c in data]
    for row in build_data_quality_report(data, baseline)["degradation"]:
        assert row["rm_queue_after"] <= row["rm_queue_before"], (
            f"removing {row['label']} grew the RM queue "
            f"{row['rm_queue_before']} → {row['rm_queue_after']}"
        )


def test_a_record_without_name_or_city_still_scores():
    customer = generate_dataset(1, seed=42)[0]
    for field in ("name", "city", "employment_type", "age", "segment"):
        customer.pop(field, None)
    profile = score_customer_rules(customer)
    assert profile["lead_tier"] in LEAD_TIERS
    assert profile["name"] and profile["city"]


def test_missing_obligations_are_not_read_as_no_debt():
    base = generate_dataset(1, seed=42)[0]
    base["debt_to_income_ratio"] = 0.05
    low_debt = score_customer_rules(base)["repayment_capacity"]["score"]

    unknown = dict(base)
    unknown.pop("debt_to_income_ratio")
    unknown_score = score_customer_rules(unknown)["repayment_capacity"]["score"]

    assert unknown_score < low_debt, "an absent DTI must not score like a debt-free customer"


def test_missing_digital_footprint_caps_the_tier_at_serious():
    data = generate_dataset(200, seed=42)
    promoted = 0
    for customer in data:
        stripped = dict(customer)
        for field in (
            "loan_page_visits_30d", "loan_calculator_uses", "avg_session_minutes",
            "application_started", "window_shopping_flag",
        ):
            stripped.pop(field, None)
        profile = score_customer_rules(stripped)
        assert profile["lead_tier"] != "Quality Lead", (
            "unverified intent must never produce a 24h-SLA Quality Lead"
        )
        assert profile["purchase_intent"]["details"]["data_basis"] == "transaction_only"
        if profile["rm_call_eligible"]:
            promoted += 1
    assert promoted > 0, "branch-acquired customers must not be excluded from the queue entirely"


# --------------------------------------------------------------------------- #
# Vernacular briefs
# --------------------------------------------------------------------------- #
def test_every_language_produces_a_brief_with_no_placeholders(quality_customer):
    from app.vernacular import build_vernacular_briefs

    briefs = build_vernacular_briefs(score_customer_rules(quality_customer))
    assert {b["code"] for b in briefs} == {"hi", "mr", "ta"}
    for brief in briefs:
        assert brief["lines"]
        joined = " ".join(brief["lines"])
        assert "{" not in joined and "}" not in joined, "unrendered template placeholder"
        assert "None" not in joined
        assert "₹—" not in joined, "an unresolved currency value reached the script"
        assert brief["disclaimer"]
        assert brief["review_status"] == "pending native-speaker review"


def test_vernacular_brief_is_tier_aware():
    """A window shopper must get a deprioritisation script, not a pitch."""
    from app.vernacular import build_vernacular_briefs

    data = generate_dataset(200, seed=42)
    shopper = next(
        score_customer_rules(c) for c in data
        if score_customer_rules(c)["lead_tier"] == "Window-shop Risk"
    )
    quality = next(
        score_customer_rules(c) for c in data
        if score_customer_rules(c)["lead_tier"] == "Quality Lead"
    )
    shopper_hi = " ".join(next(b for b in build_vernacular_briefs(shopper) if b["code"] == "hi")["lines"])
    quality_hi = " ".join(next(b for b in build_vernacular_briefs(quality) if b["code"] == "hi")["lines"])

    assert "न करें" in shopper_hi, "the suppression instruction is missing"
    assert "कॉल करें" in quality_hi, "the call instruction is missing"
    assert shopper_hi != quality_hi


# --------------------------------------------------------------------------- #
# Ingest coercion and validation — the sandbox boundary
# --------------------------------------------------------------------------- #
ADVERSARIAL_RECORDS = {
    "empty": {},
    "id only": {"customer_id": "X1"},
    "zero income": {"customer_id": "X2", "monthly_income": 0},
    "negative income": {"customer_id": "X3", "monthly_income": -5000},
    "string income": {"customer_id": "X4", "monthly_income": "85000"},
    "lakh-formatted income": {"customer_id": "X5", "monthly_income": "1,25,000"},
    "null ratios": {"customer_id": "X6", "monthly_income": 60000,
                    "debt_to_income_ratio": None, "salary_day_spend_ratio": None},
    "string booleans": {"customer_id": "X7", "monthly_income": 60000,
                        "application_started": "true", "pays_rent": "yes"},
    "out-of-range ratios": {"customer_id": "X8", "monthly_income": 50000,
                            "need_spend_ratio": 3.0, "debt_to_income_ratio": 9.9},
    "junk numerics": {"customer_id": "X9", "monthly_income": 50000,
                      "avg_monthly_balance": "N/A", "luxury_spend_ratio": "unknown"},
}


@pytest.mark.parametrize("label", list(ADVERSARIAL_RECORDS))
def test_no_malformed_record_can_crash_the_pipeline(label):
    """A sandbox feed sends strings, nulls and out-of-range values. None may 500."""
    from app.next_best_action import build_next_best_actions
    from app.uplift import simulate_uplift
    from app.vernacular import build_vernacular_briefs

    record = dict(ADVERSARIAL_RECORDS[label])
    profile = score_customer_rules(record)
    assert profile["lead_tier"] in LEAD_TIERS
    uplift = simulate_uplift(dict(record), profile)
    nba = build_next_best_actions(profile, dict(record), uplift)
    assert nba["next_best_action"] is not None
    assert len(build_vernacular_briefs(profile)) == 3


def test_numbers_sent_as_strings_are_coerced():
    from app.ingest import coerce_customer

    clean, notes = coerce_customer({"customer_id": "X", "monthly_income": "1,25,000",
                                    "debt_to_income_ratio": "0.35"})
    assert clean["monthly_income"] == 125000
    assert clean["debt_to_income_ratio"] == pytest.approx(0.35, abs=1e-9)
    assert notes


def test_unparseable_values_are_dropped_not_zeroed():
    """A zero would read as good news; absent reads as unknown."""
    from app.ingest import coerce_customer

    clean, notes = coerce_customer({"customer_id": "X", "monthly_income": 50000,
                                    "debt_to_income_ratio": "N/A"})
    assert "debt_to_income_ratio" not in clean
    assert any("dropped" in n for n in notes)


def test_nulls_are_treated_as_absent():
    from app.ingest import coerce_customer

    clean, _ = coerce_customer({"customer_id": "X", "monthly_income": 50000,
                                "salary_day_spend_ratio": None, "city": None})
    assert "salary_day_spend_ratio" not in clean
    assert "city" not in clean


def test_out_of_range_ratios_are_clamped_and_flagged():
    from app.ingest import coerce_customer

    clean, notes = coerce_customer({"customer_id": "X", "monthly_income": 50000,
                                    "need_spend_ratio": 3.0, "credit_utilization_pct": -2})
    assert clean["need_spend_ratio"] == 1.0
    assert clean["credit_utilization_pct"] == 0.0
    assert sum("clamped" in n for n in notes) == 2


def test_a_negative_income_never_outscores_a_zero_income():
    negative = score_customer_rules({"customer_id": "N", "monthly_income": -5000})
    zero = score_customer_rules({"customer_id": "Z", "monthly_income": 0})
    assert negative["composite_lead_score"] <= zero["composite_lead_score"]


def test_the_hard_ingest_gate_rejects_unscoreable_records():
    from app.ingest import validate_customer

    for record in ({}, {"monthly_income": 50000}, {"customer_id": "  ", "monthly_income": 1},
                   {"customer_id": "X"}, {"customer_id": "X", "monthly_income": None},
                   {"customer_id": "X", "monthly_income": "N/A"},
                   {"customer_id": "X", "monthly_income": -100}):
        assert validate_customer(record)["accepted"] is False, record

    ok = validate_customer({"customer_id": "IDBI-L10010", "monthly_income": "85,000"})
    assert ok["accepted"] is True
    assert ok["record"]["monthly_income"] == 85000


def test_boolean_flags_alone_are_not_a_digital_footprint():
    """
    A sandbox returns `{application_started: false, window_shopping_flag: false}`
    for a customer with no digital activity. Treating that as an observed footprint
    collapsed intent and silently excluded branch-acquired customers.
    """
    from app.scoring import has_digital_footprint

    record = {"customer_id": "B1", "monthly_income": 60000,
              "application_started": False, "window_shopping_flag": False}
    assert has_digital_footprint(record) is False
    assert score_customer_rules(record)["purchase_intent"]["details"]["data_basis"] == "transaction_only"


def test_the_live_population_passes_the_ingest_gate():
    from app.ingest import ingest_report

    report = ingest_report(generate_dataset(200, seed=42))
    assert report["accepted"] == 200
    assert report["rejected"] == 0
    assert report["records_needing_coercion"] == 0


# --------------------------------------------------------------------------- #
# The UI must not expose implementation detail
# --------------------------------------------------------------------------- #
CODE_PATTERNS = [
    (r"\b[A-Za-z_][A-Za-z0-9_]*\.py\b", "a source filename"),
    (r"\b[a-z_][a-z0-9_]{3,}\(\)", "a function name"),
    (r"\b[A-Z][A-Z0-9]{3,}_[A-Z0-9_]+\b", "a constant name"),
    (r"\.jsonl\b|\.joblib\b", "a storage file"),
]

# Raw contract field names are allowed only where they are the integration
# contract itself; everywhere else a business label must be used.
def _assert_no_code(text: str, where: str) -> None:
    for pattern, what in CODE_PATTERNS:
        found = re.findall(pattern, text)
        assert not found, f"{where} exposes {what}: {sorted(set(found))[:5]}"


def test_next_best_action_evidence_is_business_language():
    from app.next_best_action import build_next_best_actions

    data = generate_dataset(60, seed=42)
    for raw in data:
        profile = score_customer_rules(raw)
        for action in build_next_best_actions(profile, raw)["actions"]:
            _assert_no_code(action["evidence"], "an action's evidence label")
            _assert_no_code(action["rationale"], "an action's rationale")
            _assert_no_code(action["script"], "an RM call script")


def test_usp_catalogue_is_business_language():
    from app.usp import build_usp_catalogue

    for usp in build_usp_catalogue()["entries"]:
        for field in ("title", "claim", "why_idbi", "evidence_label", "typical_entry"):
            _assert_no_code(usp[field], f"USP '{usp['id']}' field {field}")


def test_glossary_never_points_at_source_files():
    from app.glossary import build_glossary

    for entry in build_glossary()["entries"]:
        _assert_no_code(entry["where"], f"glossary term '{entry['term']}'")
        _assert_no_code(entry["definition"], f"glossary definition '{entry['term']}'")


def test_governance_surfaces_are_business_language():
    from app.fairness import PROXY_REGISTER, DATA_INVENTORY, governance_controls

    for control in governance_controls():
        _assert_no_code(control["evidence"], "a governance control")
        _assert_no_code(control["detail"], "a governance control detail")
    for proxy in PROXY_REGISTER:
        _assert_no_code(proxy["feature"], "the proxy register")
        _assert_no_code(proxy["mitigation"], "a proxy mitigation")
    for row in DATA_INVENTORY:
        _assert_no_code(row["minimisation"], "the data inventory")


def test_data_quality_fields_carry_business_labels():
    from app.data_quality import build_data_quality_report

    data = generate_dataset(60, seed=42)
    report = build_data_quality_report(data, [score_customer_rules(c) for c in data])
    for group in report["groups"]:
        for row in group["required_fields"] + group["optional_fields"]:
            assert row["label"] and row["label"] != row["field"], (
                f"{row['field']} has no business label"
            )
    for rule in report["ingest_rules"]:
        _assert_no_code(rule[0], "an ingest rule")
        _assert_no_code(rule[1], "an ingest rule description")


def test_uplift_copy_is_business_language(quality_customer):
    from app.uplift import simulate_uplift

    report = simulate_uplift(quality_customer)
    _assert_no_code(report["method"], "the uplift method note")
    _assert_no_code(report["disclaimer"], "the uplift disclaimer")
    for lever in report["levers"]:
        _assert_no_code(lever["label"], "an uplift lever label")
        _assert_no_code(lever["note"], "an uplift lever note")
