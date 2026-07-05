"""ML credibility artifacts — validation metrics and rules vs hybrid evaluation."""

from __future__ import annotations

from typing import Any

import numpy as np

from app.scoring import LEAD_TIERS, score_customer, score_customer_rules


def evaluate_rules_vs_hybrid(customers: list[dict]) -> dict[str, Any]:
    """Quantify hybrid uplift over rules-only on a customer sample."""
    rule_tiers = {t: 0 for t in LEAD_TIERS}
    hybrid_tiers = {t: 0 for t in LEAD_TIERS}
    upgrades = downgrades = unchanged = 0
    quality_preserved = quality_total = 0
    window_rule = window_hybrid = 0
    ml_applied = 0
    ml_nudges: list[float] = []

    for c in customers:
        rules = score_customer_rules(c)
        hybrid = score_customer(c, use_ml=True)
        rule_tiers[rules["lead_tier"]] += 1
        hybrid_tiers[hybrid["lead_tier"]] += 1

        ri = LEAD_TIERS.index(rules["lead_tier"])
        hi = LEAD_TIERS.index(hybrid["lead_tier"])
        if hi < ri:
            upgrades += 1
        elif hi > ri:
            downgrades += 1
        else:
            unchanged += 1

        if rules["lead_tier"] == "Quality Lead":
            quality_total += 1
            if hybrid["lead_tier"] == "Quality Lead":
                quality_preserved += 1

        if c.get("window_shopping_flag"):
            if rules["lead_tier"] == "Window-shop Risk":
                window_rule += 1
            if hybrid["lead_tier"] == "Window-shop Risk":
                window_hybrid += 1

        enh = hybrid.get("ml_enhancement", {})
        if enh.get("applied"):
            ml_applied += 1
            ml_nudges.append(abs(enh.get("nudge_applied", 0)))

    n = len(customers) or 1
    return {
        "sample_size": len(customers),
        "rule_tier_distribution": rule_tiers,
        "hybrid_tier_distribution": hybrid_tiers,
        "tier_upgrades": upgrades,
        "tier_downgrades": downgrades,
        "tier_unchanged": unchanged,
        "quality_lead_preservation_pct": round(quality_preserved / max(quality_total, 1) * 100, 1),
        "window_shop_detection_rule": window_rule,
        "window_shop_detection_hybrid": window_hybrid,
        "window_shop_detection_lift_pct": round(
            (window_hybrid - window_rule) / max(window_rule, 1) * 100, 1
        ) if window_rule else 0,
        "ml_nudges_applied": ml_applied,
        "ml_nudge_rate_pct": round(ml_applied / n * 100, 1),
        "avg_nudge_magnitude": round(float(np.mean(ml_nudges)), 2) if ml_nudges else 0,
        "quality_lead_delta": hybrid_tiers["Quality Lead"] - rule_tiers["Quality Lead"],
    }


def get_ml_credibility_report(customers: list[dict] | None = None) -> dict[str, Any]:
    """Full ML transparency package for judges."""
    from app.data_generator import generate_dataset
    from app.features import FEATURE_NAMES
    from app.ml_model import get_model

    model = get_model()
    sample = customers or generate_dataset(500, seed=42)
    comparison = evaluate_rules_vs_hybrid(sample)

    report: dict[str, Any] = {
        "model_ready": model.is_ready,
        "feature_count": len(FEATURE_NAMES),
        "rules_vs_hybrid": comparison,
    }

    if model.is_ready:
        card = model.model_card()
        metrics = model.meta.get("metrics", {})
        report["model_card"] = card
        report["training"] = {
            "algorithm": "XGBoost regressor + multi-class classifier",
            "train_rows": metrics.get("train_rows"),
            "validation_split": metrics.get("validation_split", "80/20 stratified by tier"),
            "validation_score_mae": metrics.get("validation_score_mae"),
            "validation_score_r2": metrics.get("validation_score_r2"),
            "validation_tier_accuracy": metrics.get("validation_tier_accuracy"),
            "tier_precision": metrics.get("tier_precision", {}),
            "tier_recall": metrics.get("tier_recall", {}),
            "confusion_matrix": metrics.get("confusion_matrix", {}),
        }
        report["credibility_checks"] = {
            "quality_never_demoted": comparison["quality_lead_preservation_pct"] == 100.0,
            "mae_below_threshold": (metrics.get("validation_score_mae") or 99) <= 5.0,
            "tier_accuracy_above_baseline": (metrics.get("validation_tier_accuracy") or 0) >= 0.75,
            "hybrid_adds_window_shop_detection": comparison["window_shop_detection_hybrid"]
            >= comparison["window_shop_detection_rule"],
        }

    return report
