#!/usr/bin/env python3
"""Compare rule-only vs hybrid scoring quality."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.data_generator import generate_dataset  # noqa: E402
from app.scoring import LEAD_TIERS, score_customer, score_customer_rules  # noqa: E402


def main() -> None:
    customers = generate_dataset(500, seed=42)
    rule_tiers = {t: 0 for t in LEAD_TIERS}
    hybrid_tiers = {t: 0 for t in LEAD_TIERS}
    upgrades = downgrades = 0

    for c in customers:
        r = score_customer_rules(c)
        h = score_customer(c, use_ml=True)
        rule_tiers[r["lead_tier"]] += 1
        hybrid_tiers[h["lead_tier"]] += 1
        ri = LEAD_TIERS.index(r["lead_tier"])
        hi = LEAD_TIERS.index(h["lead_tier"])
        if hi < ri:
            upgrades += 1
        if hi > ri:
            downgrades += 1

    print("Rule tiers:  ", rule_tiers)
    print("Hybrid tiers:", hybrid_tiers)
    print(f"Upgrades: {upgrades}, Downgrades: {downgrades}")
    print(f"Quality Lead delta: {hybrid_tiers['Quality Lead'] - rule_tiers['Quality Lead']}")
    print(f"Window-shop delta: {hybrid_tiers['Window-shop Risk'] - rule_tiers['Window-shop Risk']}")


if __name__ == "__main__":
    main()
