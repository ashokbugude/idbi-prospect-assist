#!/usr/bin/env python3
"""Pre-submission validation for IDBI Prospect Assist AI."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.data_generator import generate_dataset  # noqa: E402
from app.scoring import compute_impact_metrics, rank_customers, score_customer  # noqa: E402


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    data_path = ROOT / "app" / "data" / "customers.json"
    if not data_path.exists():
        errors.append("Missing app/data/customers.json — run: python -m app.data_generator")
    else:
        customers = json.loads(data_path.read_text(encoding="utf-8"))
        if len(customers) < 100:
            warnings.append(f"Only {len(customers)} customers — recommend 200+ for demo")

    customers = generate_dataset(200, seed=42)
    ranked = rank_customers(customers)
    impact = compute_impact_metrics(customers)
    hybrid_modes: dict[str, int] = {}
    ml_applied = 0
    for c in customers[:50]:
        h = score_customer(c)
        mode = h.get("scoring_mode", "unknown")
        hybrid_modes[mode] = hybrid_modes.get(mode, 0) + 1
        if h.get("ml_enhancement", {}).get("applied"):
            ml_applied += 1

    from app.ml_model import get_model

    ml_ready = get_model().is_ready
    from app.ml_evaluation import get_ml_credibility_report

    ml_report = get_ml_credibility_report(customers[:200])
    ml_ready = ml_report.get("model_ready", False)
    if not ml_ready:
        errors.append("ML model not loaded — run: python scripts/train_model.py")
    elif not all(ml_report.get("credibility_checks", {}).values()):
        errors.append("ML credibility checks failed — see /ml")
    if not impact.get("meets_track02_conversion_target"):
        errors.append("Quality lead conversion below Track 02 target (32%)")
    if not impact.get("proof_summary", {}).get("backtest_quality_meets_target"):
        errors.append("Monte Carlo backtest: quality segment below 32% target")
    if not impact.get("proof_summary", {}).get("conservative_quality_still_above_target"):
        errors.append("Conservative scenario: quality segment below 32% target")
    if impact.get("rm_queue_conversion_pct", 0) <= impact.get("baseline_conversion_pct", 1):
        errors.append("RM queue conversion must exceed baseline")
    if ml_ready and hybrid_modes.get("hybrid", 0) == 0 and hybrid_modes.get("rules_fallback", 0) > 0:
        errors.append("ML model loaded but scoring fell back — check predict() errors")

    for c in ranked:
        if not c["repayment_capacity"]["reasons"]:
            errors.append(f"{c['customer_id']}: missing repayment reasons")
        if not c["all_scores"][0]["reasons"]:
            errors.append(f"{c['customer_id']}: missing product reasons")
        if c["composite_lead_score"] < 0 or c["composite_lead_score"] > 100:
            errors.append(f"{c['customer_id']}: composite out of range")

    rm_queue = sum(1 for c in ranked if c.get("rm_call_eligible"))
    rm_pct = rm_queue / len(ranked) * 100 if ranked else 0
    if rm_pct < 20 or rm_pct > 35:
        warnings.append(f"RM queue {rm_pct:.1f}% — target 20-35% for pitch consistency")
    window_pct = impact.get("window_shop_filtered_pct", 0)
    if window_pct < 20:
        warnings.append(f"Window-shop only {window_pct}% — target 25-35% for realism")

    print("=== IDBI Prospect Assist AI — Validation ===")
    print(f"Customers scored: {len(ranked)}")
    print(f"Tier distribution: {impact['tier_distribution']}")
    print(f"Baseline conversion: {impact['baseline_conversion_pct']}%")
    print(f"RM queue conversion: {impact.get('rm_queue_conversion_pct', impact.get('projected_conversion_pct'))}%")
    print(f"Quality segment conversion: {impact.get('quality_lead_conversion_pct')}%")
    print(f"Track 02 target met: {impact.get('meets_track02_conversion_target')}")
    print(f"RM actionable leads: {impact['rm_actionable_leads']} ({impact['rm_queue_pct']}%)")
    print(f"Window-shop filtered: {impact['window_shop_filtered_pct']}%")
    print(f"ML model ready: {ml_ready}")
    print(f"Hybrid modes (sample): {hybrid_modes}")
    print(f"ML nudges applied (sample): {ml_applied}")

    if warnings:
        print("\nWarnings:")
        for w in warnings:
            print(f"  - {w}")

    if errors:
        print("\nERRORS:")
        for e in errors:
            print(f"  - {e}")
        return 1

    print("\nAll validation checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
