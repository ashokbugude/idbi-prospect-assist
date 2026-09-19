"""
Outcome feedback loop — what actually happened after the RM acted.

Why this exists
---------------
Round 1 scored leads and never found out whether it was right. That is the gap
between a model and a system: the XGBoost layer is trained on the rule engine's
own labels, so it agrees with its teacher by construction and can never learn
that the teacher was wrong.

This module captures the one fact that breaks that circle — the RM's call
disposition — and turns it into three things a bank can act on:

1. **Calibration.** Every conversion rate on /impact is currently a documented
   assumption. Each captured outcome moves one of them from "assumed" to
   "measured", and the gap is published.
2. **A retrain label.** Dispositions map to a binary converted/not-converted
   target, so the next model learns from RMs rather than from rules.
3. **A pilot instrument.** The 4-week A/B needs an outcome table. This is it,
   ready on day one rather than built during week one.

Storage is an append-only JSONL file: outcomes are evidence, so nothing is ever
updated or deleted in place. A correction is a new record that supersedes the
previous one.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.impact import TIER_CONVERSION_RATES
from app.scoring import LEAD_TIERS

DATA_DIR = Path(__file__).resolve().parent / "data"
OUTCOME_LOG = DATA_DIR / "outcomes.jsonl"

_lock = threading.Lock()
_cache: list[dict] | None = None

# Minimum contacted leads in a tier before its measured rate is trustworthy.
MIN_SAMPLE_FOR_CALIBRATION = 30
# Captured outcomes needed before a supervised retrain is worth running.
RETRAIN_THRESHOLD = 150


# (code, label, contacted?, converted?, description)
DISPOSITIONS: list[tuple[str, str, bool, bool, str]] = [
    ("not_reachable", "Not reachable", False, False,
     "No contact established — excluded from conversion denominators."),
    ("call_declined", "Declined the call", True, False,
     "Contact made, customer would not engage."),
    ("not_interested", "Not interested", True, False,
     "Engaged but no appetite for the product offered."),
    ("interested_nurture", "Interested — needs nurture", True, False,
     "Genuine interest, no commitment yet. Re-queue rather than close."),
    ("application_started", "Application started", True, False,
     "Converted on intent; not yet a booked asset."),
    ("application_declined", "Declined by underwriting", True, False,
     "Applied and was refused — the signal the scorer most needs to see."),
    ("loan_booked", "Loan booked", True, True,
     "Full conversion. The label the next model trains on."),
]

DISPOSITION_INDEX = {d[0]: d for d in DISPOSITIONS}
CONVERTING = {d[0] for d in DISPOSITIONS if d[3]}
CONTACTED = {d[0] for d in DISPOSITIONS if d[2]}


def _display_path(path: Path) -> str:
    """Repo-relative when it sits inside the project, absolute otherwise."""
    try:
        return str(path.relative_to(Path(__file__).resolve().parent.parent))
    except ValueError:
        return str(path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read_all() -> list[dict]:
    global _cache
    if _cache is not None:
        return _cache
    records: list[dict] = []
    if OUTCOME_LOG.exists():
        for line in OUTCOME_LOG.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # a torn final write must not take the page down
    _cache = records
    return _cache


def record_outcome(
    customer_id: str,
    disposition: str,
    lead_tier: str,
    action_code: str = "",
    composite_lead_score: float | None = None,
    rm_id: str = "demo-rm",
    notes: str = "",
    recorded_at: str | None = None,
    simulated: bool = False,
    sync: bool = True,
) -> dict:
    """Append one disposition. Never updates or deletes an existing record."""
    if disposition not in DISPOSITION_INDEX:
        raise ValueError(f"unknown disposition: {disposition}")

    record = {
        "outcome_id": uuid.uuid4().hex[:12],
        "customer_id": customer_id,
        "lead_tier": lead_tier,
        "action_code": action_code,
        "composite_lead_score": composite_lead_score,
        "disposition": disposition,
        "contacted": disposition in CONTACTED,
        "converted": disposition in CONVERTING,
        "rm_id": rm_id,
        "notes": notes[:500],
        "recorded_at": recorded_at or _now(),
        "simulated": simulated,
    }

    with _lock:
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            with OUTCOME_LOG.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record) + "\n")
                fh.flush()
                if sync:
                    os.fsync(fh.fileno())
        except OSError as exc:
            # A read-only filesystem must not lose the RM's work silently.
            record["persisted"] = False
            record["persist_error"] = type(exc).__name__
        else:
            record["persisted"] = True
        if _cache is not None:
            _cache.append(record)
    return record


def latest_per_customer() -> dict[str, dict]:
    """A correction is a later record, so the last one wins."""
    latest: dict[str, dict] = {}
    for r in _read_all():
        latest[r["customer_id"]] = r
    return latest


# --------------------------------------------------------------------------- #
# Calibration — assumption vs measurement
# --------------------------------------------------------------------------- #
def calibration_by_tier() -> list[dict]:
    """
    Compare each tier's assumed conversion rate against what RMs actually saw.

    This is the scoreboard that turns /impact from a projection into a claim
    that can be checked.
    """
    latest = latest_per_customer().values()
    rows: list[dict] = []
    for tier in LEAD_TIERS:
        tier_rows = [r for r in latest if r["lead_tier"] == tier]
        contacted = [r for r in tier_rows if r["contacted"]]
        converted = [r for r in contacted if r["converted"]]
        assumed_pct = round(TIER_CONVERSION_RATES.get(tier, 0.02) * 100, 1)

        if not contacted:
            rows.append({
                "tier": tier,
                "assumed_conversion_pct": assumed_pct,
                "observed_conversion_pct": None,
                "outcomes_logged": len(tier_rows),
                "contacted": 0,
                "converted": 0,
                "delta_pp": None,
                "status": "unvalidated",
                "note": "No outcomes captured yet for this tier.",
            })
            continue

        observed_pct = round(len(converted) / len(contacted) * 100, 1)
        delta = round(observed_pct - assumed_pct, 1)
        if len(contacted) < MIN_SAMPLE_FOR_CALIBRATION:
            status = "emerging"
            note = f"n={len(contacted)} — below the {MIN_SAMPLE_FOR_CALIBRATION} needed to trust this rate."
        elif abs(delta) <= 5:
            status = "validated"
            note = "Observed rate is within 5 pp of the assumption."
        else:
            status = "diverging"
            note = (
                f"Observed rate is {abs(delta):.1f} pp "
                f"{'above' if delta > 0 else 'below'} the assumption — recalibrate the model."
            )

        rows.append({
            "tier": tier,
            "assumed_conversion_pct": assumed_pct,
            "observed_conversion_pct": observed_pct,
            "outcomes_logged": len(tier_rows),
            "contacted": len(contacted),
            "converted": len(converted),
            "delta_pp": delta,
            "status": status,
            "note": note,
        })
    return rows


def disposition_breakdown() -> list[dict]:
    latest = list(latest_per_customer().values())
    total = len(latest) or 1
    rows = []
    for code, label, contacted, converted, description in DISPOSITIONS:
        n = sum(1 for r in latest if r["disposition"] == code)
        rows.append({
            "code": code,
            "label": label,
            "description": description,
            "count": n,
            "share_pct": round(n / total * 100, 1),
            "counts_as_contact": contacted,
            "counts_as_conversion": converted,
        })
    return rows


def training_readiness() -> dict:
    """Can the next model learn from RMs rather than from the rule engine?"""
    latest = list(latest_per_customer().values())
    labelled = [r for r in latest if r["contacted"]]
    positives = [r for r in labelled if r["converted"]]
    real = [r for r in latest if not r.get("simulated")]
    ready = len(labelled) >= RETRAIN_THRESHOLD and len(positives) >= 20

    return {
        "outcomes_captured": len(latest),
        "usable_labels": len(labelled),
        "positive_labels": len(positives),
        "real_outcomes": len(real),
        "simulated_outcomes": len(latest) - len(real),
        "retrain_threshold": RETRAIN_THRESHOLD,
        "progress_pct": round(min(100.0, len(labelled) / RETRAIN_THRESHOLD * 100), 1),
        "ready_to_retrain": ready,
        "blocker": (
            None if ready
            else f"Need {max(0, RETRAIN_THRESHOLD - len(labelled))} more contacted outcomes"
            if len(labelled) < RETRAIN_THRESHOLD
            else "Need at least 20 booked loans before a supervised retrain is meaningful"
        ),
        "current_label_source": "rule engine (self-supervised)",
        "next_label_source": "RM dispositions (supervised on real outcomes)",
        "why_it_matters": (
            "Today the classifier is trained on labels the rule engine produced, so it agrees with "
            "the rules by construction and moves no tiers. Once these outcomes cross the threshold "
            "the target becomes what actually happened, and the model can disagree with the rules "
            "for a reason a human can audit."
        ),
    }


def rm_activity() -> list[dict]:
    by_rm: dict[str, dict] = {}
    for r in latest_per_customer().values():
        row = by_rm.setdefault(r["rm_id"], {"rm_id": r["rm_id"], "logged": 0, "contacted": 0, "booked": 0})
        row["logged"] += 1
        row["contacted"] += 1 if r["contacted"] else 0
        row["booked"] += 1 if r["converted"] else 0
    for row in by_rm.values():
        row["contact_rate_pct"] = round(row["contacted"] / row["logged"] * 100, 1) if row["logged"] else 0
        row["book_rate_pct"] = round(row["booked"] / row["contacted"] * 100, 1) if row["contacted"] else 0
    return sorted(by_rm.values(), key=lambda r: -r["logged"])


def build_outcome_report() -> dict[str, Any]:
    latest = list(latest_per_customer().values())
    calibration = calibration_by_tier()
    validated = [c for c in calibration if c["status"] == "validated"]
    diverging = [c for c in calibration if c["status"] == "diverging"]

    return {
        "total_records": len(_read_all()),
        "leads_with_outcome": len(latest),
        "calibration": calibration,
        "validated_tiers": len(validated),
        "diverging_tiers": [c["tier"] for c in diverging],
        "dispositions": disposition_breakdown(),
        "training": training_readiness(),
        "rm_activity": rm_activity(),
        "disposition_options": [
            {"code": c, "label": l, "contacted": ct, "converted": cv, "description": d}
            for c, l, ct, cv, d in DISPOSITIONS
        ],
        "method": (
            "Append-only JSONL. A correction is a new record that supersedes the previous one for "
            "that customer, so the audit trail is never rewritten. Conversion denominators count "
            "contacted leads only — an unreachable lead is not a failed pitch."
        ),
        "storage_path": _display_path(OUTCOME_LOG),
    }


# --------------------------------------------------------------------------- #
# Demo backfill — clearly labelled, never mistaken for real evidence
# --------------------------------------------------------------------------- #
def seed_simulated_outcomes(ranked_profiles: list[dict], seed: int = 42) -> int:
    """
    Populate the loop with plausible dispositions so the page demonstrates the
    mechanism on a cold start. Every record is flagged `simulated: true` and the
    UI says so — the point is to show the instrument working, not to claim results.
    """
    if any(not r.get("simulated") for r in _read_all()):
        return 0  # real outcomes exist; never mix in synthetic ones
    if _read_all():
        return 0  # already seeded

    import random

    rng = random.Random(seed)
    # Deliberately offset from TIER_CONVERSION_RATES so calibration has something
    # to say rather than trivially confirming the assumptions.
    observed_rates = {
        "Quality Lead": 0.34,
        "Serious": 0.21,
        "Interested": 0.05,
        "Window-shop Risk": 0.01,
    }
    written = 0
    for profile in ranked_profiles:
        tier = profile["lead_tier"]
        # Only leads the engine actually told an RM to work get an outcome.
        if tier == "Window-shop Risk" and rng.random() > 0.08:
            continue
        if tier == "Interested" and rng.random() > 0.35:
            continue
        if rng.random() < 0.18:
            disposition = "not_reachable"
        elif rng.random() < observed_rates.get(tier, 0.05):
            disposition = "loan_booked"
        else:
            disposition = rng.choices(
                ["not_interested", "interested_nurture", "application_started",
                 "application_declined", "call_declined"],
                weights=[30, 28, 18, 10, 14],
            )[0]
        record_outcome(
            customer_id=profile["customer_id"],
            disposition=disposition,
            lead_tier=tier,
            action_code=profile.get("top_product", ""),
            composite_lead_score=profile.get("composite_lead_score"),
            rm_id=f"RM-{rng.randint(1, 6):02d}",
            notes="",
            simulated=True,
            sync=False,  # one fsync at the end rather than one per record
        )
        written += 1

    if written:
        try:
            with OUTCOME_LOG.open("a", encoding="utf-8") as fh:
                os.fsync(fh.fileno())
        except OSError:
            pass
    return written


def clear_cache_for_tests() -> None:
    global _cache
    _cache = None
