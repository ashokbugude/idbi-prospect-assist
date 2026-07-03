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
    if not ml_ready:
        errors.append("ML model not loaded — run: python scripts/train_model.py")
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
    if rm_queue < 5:
        warnings.append(f"RM queue only {rm_queue} leads — may look thin in demo")

    print("=== IDBI Prospect Assist AI — Validation ===")
    print(f"Customers scored: {len(ranked)}")
    print(f"Tier distribution: {impact['tier_distribution']}")
    print(f"Baseline conversion: {impact['baseline_conversion_pct']}%")
    print(f"Projected (RM queue): {impact['projected_conversion_pct']}%")
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
