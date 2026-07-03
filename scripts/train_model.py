#!/usr/bin/env python3
"""Train hybrid XGBoost models on rule-labeled synthetic data."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.data_generator import generate_dataset  # noqa: E402
from app.features import features_to_vector  # noqa: E402
from app.ml_model import LeadMLModel, TIER_INDEX  # noqa: E402
from app.scoring import score_customer_rules  # noqa: E402


def main() -> None:
    print("Generating training data...")
    customers = generate_dataset(4000, seed=2026)
    profiles = [score_customer_rules(c) for c in customers]

    x = np.array(features_to_vector(customers), dtype=np.float32)
    y_score = np.array([p["composite_lead_score"] for p in profiles], dtype=np.float32)
    y_tier = np.array([TIER_INDEX[p["lead_tier"]] for p in profiles], dtype=np.int32)

    x_train, x_val, ys_train, ys_val, yt_train, yt_val = train_test_split(
        x, y_score, y_tier, test_size=0.2, random_state=42, stratify=y_tier
    )

    model = LeadMLModel()
    metrics = model.train(x_train, ys_train, yt_train, x_val, ys_val, yt_val)
    print("Training complete:")
    for k, v in metrics.items():
        print(f"  {k}: {v}")

    if metrics["validation_score_mae"] > 12:
        raise SystemExit("Model quality too low — aborting")
    if metrics["validation_tier_accuracy"] < 0.55:
        raise SystemExit("Tier accuracy too low — aborting")


if __name__ == "__main__":
    main()
