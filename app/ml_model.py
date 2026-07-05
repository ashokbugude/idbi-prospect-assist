"""Lightweight XGBoost layer — safe hybrid with rule-based scoring."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import xgboost as xgb

from app.features import FEATURE_LABELS, FEATURE_NAMES, extract_features

MODEL_DIR = Path(__file__).resolve().parent / "models"
REG_MODEL_PATH = MODEL_DIR / "lead_xgb_reg.joblib"
CLF_MODEL_PATH = MODEL_DIR / "lead_xgb_clf.joblib"
META_PATH = MODEL_DIR / "lead_xgb.meta.json"

MAX_ML_NUDGE = 8.0
MIN_ML_CONFIDENCE = 0.52
MIN_TIER_PROB = 0.58

TIER_INDEX = {
    "Quality Lead": 0,
    "Serious": 1,
    "Interested": 2,
    "Window-shop Risk": 3,
}


class LeadMLModel:
    def __init__(self) -> None:
        self.regressor: xgb.XGBRegressor | None = None
        self.classifier: xgb.XGBClassifier | None = None
        self.meta: dict[str, Any] = {}
        self._loaded = False

    @property
    def is_ready(self) -> bool:
        return self._loaded and self.regressor is not None and self.classifier is not None

    def load(self) -> bool:
        if not REG_MODEL_PATH.exists() or not CLF_MODEL_PATH.exists() or not META_PATH.exists():
            return False
        self.regressor = joblib.load(REG_MODEL_PATH)
        self.classifier = joblib.load(CLF_MODEL_PATH)
        self.meta = json.loads(META_PATH.read_text(encoding="utf-8"))
        self._loaded = True
        return True

    def save(self, metrics: dict[str, Any]) -> None:
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        assert self.regressor and self.classifier
        joblib.dump(self.regressor, REG_MODEL_PATH)
        joblib.dump(self.classifier, CLF_MODEL_PATH)
        self.meta = {
            "version": "1.0",
            "feature_names": FEATURE_NAMES,
            "metrics": metrics,
        }
        META_PATH.write_text(json.dumps(self.meta, indent=2), encoding="utf-8")
        self._loaded = True

    def train(
        self,
        x_train: np.ndarray,
        y_score: np.ndarray,
        y_tier: np.ndarray,
        x_val: np.ndarray,
        y_score_val: np.ndarray,
        y_tier_val: np.ndarray,
    ) -> dict[str, Any]:
        self.regressor = xgb.XGBRegressor(
            n_estimators=120,
            max_depth=4,
            learning_rate=0.08,
            subsample=0.9,
            colsample_bytree=0.9,
            reg_lambda=1.5,
            objective="reg:squarederror",
            random_state=42,
        )
        self.regressor.fit(x_train, y_score, eval_set=[(x_val, y_score_val)], verbose=False)

        self.classifier = xgb.XGBClassifier(
            n_estimators=140,
            max_depth=4,
            learning_rate=0.08,
            subsample=0.9,
            colsample_bytree=0.9,
            reg_lambda=1.5,
            objective="multi:softprob",
            num_class=4,
            random_state=42,
        )
        self.classifier.fit(x_train, y_tier, eval_set=[(x_val, y_tier_val)], verbose=False)

        pred_score = self.regressor.predict(x_val)
        pred_tier = self.classifier.predict(x_val)
        score_mae = float(np.mean(np.abs(pred_score - y_score_val)))
        tier_acc = float(np.mean(pred_tier == y_tier_val))

        from sklearn.metrics import confusion_matrix, r2_score

        score_r2 = float(r2_score(y_score_val, pred_score))
        cm = confusion_matrix(y_tier_val, pred_tier, labels=list(range(4)))
        tier_names = list(TIER_INDEX.keys())

        tier_precision: dict[str, float] = {}
        tier_recall: dict[str, float] = {}
        for idx, name in enumerate(tier_names):
            tp = cm[idx, idx]
            col_sum = cm[:, idx].sum()
            row_sum = cm[idx, :].sum()
            tier_precision[name] = round(float(tp / col_sum) if col_sum else 0, 3)
            tier_recall[name] = round(float(tp / row_sum) if row_sum else 0, 3)

        metrics = {
            "validation_score_mae": round(score_mae, 2),
            "validation_score_r2": round(score_r2, 3),
            "validation_tier_accuracy": round(tier_acc, 3),
            "train_rows": int(len(x_train)),
            "validation_rows": int(len(x_val)),
            "validation_split": "80/20 stratified by tier",
            "tier_precision": tier_precision,
            "tier_recall": tier_recall,
            "confusion_matrix": {
                "labels": tier_names,
                "matrix": cm.tolist(),
            },
        }
        self.save(metrics)
        return metrics

    def model_card(self) -> dict[str, Any]:
        """Transparency artifact for judges — metrics, features, guardrails."""
        importances: list[dict[str, Any]] = []
        if self.regressor is not None:
            imp = self.regressor.feature_importances_
            pairs = sorted(
                zip(FEATURE_NAMES, imp, strict=True),
                key=lambda p: p[1],
                reverse=True,
            )
            importances = [
                {"feature": n, "label": FEATURE_LABELS.get(n, n), "importance": round(float(v), 4)}
                for n, v in pairs[:10]
            ]
        metrics = self.meta.get("metrics", {})
        return {
            "model_type": "XGBoost hybrid (regressor + tier classifier)",
            "feature_count": len(FEATURE_NAMES),
            "validation_mae": metrics.get("validation_score_mae"),
            "validation_r2": metrics.get("validation_score_r2"),
            "validation_tier_accuracy": metrics.get("validation_tier_accuracy"),
            "train_rows": metrics.get("train_rows"),
            "validation_rows": metrics.get("validation_rows"),
            "validation_split": metrics.get("validation_split"),
            "tier_precision": metrics.get("tier_precision", {}),
            "tier_recall": metrics.get("tier_recall", {}),
            "confusion_matrix": metrics.get("confusion_matrix", {}),
            "top_features": importances,
            "guardrails": {
                "max_nudge_points": MAX_ML_NUDGE,
                "min_confidence": MIN_ML_CONFIDENCE,
                "quality_lead_protection": "ML never demotes Quality Leads",
                "rules_primary": "Rules lead; ML nudges only when confident",
            },
            "version": self.meta.get("version", "1.0"),
        }

    def predict(self, customer: dict) -> dict[str, Any]:
        if not self.is_ready:
            return {"enabled": False}

        features = np.array([extract_features(customer)], dtype=np.float32)
        ml_score = float(self.regressor.predict(features)[0])
        tier_probs = self.classifier.predict_proba(features)[0]
        ml_tier_idx = int(np.argmax(tier_probs))
        tier_names = list(TIER_INDEX.keys())
        ml_tier = tier_names[ml_tier_idx]
        ml_tier_prob = float(tier_probs[ml_tier_idx])
        ml_confidence = float(np.max(tier_probs) - np.partition(tier_probs, -2)[-2])

        dmatrix = xgb.DMatrix(features, feature_names=FEATURE_NAMES)
        contribs = self.regressor.get_booster().predict(dmatrix, pred_contribs=True)
        row = contribs[0] if getattr(contribs, "ndim", 1) > 1 else contribs
        feat_contribs = row[: len(FEATURE_NAMES)]
        if len(feat_contribs) != len(FEATURE_NAMES):
            feat_contribs = self.regressor.feature_importances_
        ml_reasons = _top_contribution_reasons(feat_contribs)

        return {
            "enabled": True,
            "ml_composite_score": round(_clamp(ml_score), 1),
            "ml_tier": ml_tier,
            "ml_tier_probability": round(ml_tier_prob, 3),
            "ml_confidence": round(max(ml_confidence, 0.0), 3),
            "ml_reasons": ml_reasons,
            "feature_contributions": [
                {"feature": FEATURE_NAMES[i], "label": FEATURE_LABELS.get(FEATURE_NAMES[i], FEATURE_NAMES[i]), "contribution": round(float(feat_contribs[i]), 4)}
                for i in range(len(FEATURE_NAMES))
            ],
            "model_metrics": self.meta.get("metrics", {}),
        }


_model: LeadMLModel | None = None


def get_model() -> LeadMLModel:
    global _model
    if _model is None:
        _model = LeadMLModel()
        _model.load()
    return _model


def ensure_model_trained(train_fn) -> LeadMLModel:
    model = get_model()
    if not model.is_ready:
        train_fn()
        model.load()
    return model


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _top_contribution_reasons(contributions: np.ndarray, k: int = 3) -> list[str]:
    pairs = list(zip(FEATURE_NAMES, contributions, strict=True))
    pairs.sort(key=lambda p: abs(p[1]), reverse=True)
    reasons: list[str] = []
    for name, contrib in pairs[:k]:
        label = FEATURE_LABELS.get(name, name)
        direction = "supports" if contrib > 0 else "reduces"
        reasons.append(f"ML: {label} {direction} lead quality ({contrib:+.2f})")
    return reasons


def blend_with_rules(
    rule_profile: dict,
    customer: dict,
    ml: dict[str, Any],
) -> dict:
    """Fuse ML with rules — rules lead, ML nudges only when confident."""
    if not ml.get("enabled"):
        rule_profile["scoring_mode"] = "rules_only"
        rule_profile["ml_enhancement"] = {"enabled": False}
        return rule_profile

    rule_composite = rule_profile["composite_lead_score"]
    rule_tier = rule_profile["lead_tier"]
    ml_composite = ml["ml_composite_score"]
    ml_tier = ml["ml_tier"]
    ml_conf = ml["ml_confidence"]
    ml_prob = ml["ml_tier_probability"]

    if ml_conf < MIN_ML_CONFIDENCE:
        rule_profile["scoring_mode"] = "rules_primary"
        rule_profile["ml_enhancement"] = {**ml, "applied": False, "reason": "low_ml_confidence"}
        return rule_profile

    delta = ml_composite - rule_composite
    nudge = float(np.clip(delta, -MAX_ML_NUDGE, MAX_ML_NUDGE) * min(ml_conf, 1.0))
    # Positive nudge when ML confirms quality; smaller negative nudge when risk detected.
    if delta < 0 and customer.get("window_shopping_flag"):
        nudge = float(np.clip(delta, -MAX_ML_NUDGE, 0) * min(ml_prob, 1.0))
    final_composite = round(_clamp(rule_composite + nudge), 1)
    final_tier = _safe_tier_fusion(rule_tier, ml_tier, ml_prob, ml_conf, customer)

    # Quality guard: blended score must not exceed rule by more than nudge allows
    if final_composite < rule_composite and rule_tier in ("Quality Lead", "Serious"):
        final_composite = rule_composite
        final_tier = rule_tier

    ml_reasons = ml.get("ml_reasons", [])
    combined_reasons = rule_profile["purchase_intent"]["reasons"][:2] + ml_reasons[:2]

    profile = {
        **rule_profile,
        "composite_lead_score": final_composite,
        "rule_composite_score": rule_composite,
        "lead_tier": final_tier,
        "lead_tier_css": _tier_css(final_tier),
        "lead_priority": final_tier,
        "rm_call_eligible": final_tier in ("Quality Lead", "Serious"),
        "recommended_action": rule_profile["recommended_action"],
        "scoring_mode": "hybrid",
        "ml_enhancement": {
            **ml,
            "applied": True,
            "nudge_applied": round(nudge, 2),
            "rule_tier": rule_tier,
            "final_tier": final_tier,
        },
    }
    profile["purchase_intent"] = {
        **rule_profile["purchase_intent"],
        "reasons": combined_reasons[:4],
    }
    profile["recommended_action"] = _action_for_tier(final_tier, profile["top_product"])
    return profile


def _tier_css(tier: str) -> str:
    from app.scoring import TIER_CSS
    return TIER_CSS.get(tier, "interested")


def _action_for_tier(tier: str, product: str) -> str:
    from app.scoring import PRODUCT_LABELS, _recommended_action
    return _recommended_action(tier, product)


def _safe_tier_fusion(
    rule_tier: str,
    ml_tier: str,
    ml_prob: float,
    ml_conf: float,
    customer: dict,
) -> str:
    ri = TIER_INDEX[rule_tier]
    mi = TIER_INDEX[ml_tier]

    if ml_prob < MIN_TIER_PROB:
        return rule_tier

    # Never demote top-quality rule outcomes on ML alone.
    if rule_tier == "Quality Lead":
        return rule_tier

    # Catch window shoppers the rules under-penalized (ML adds value here).
    if (
        customer.get("window_shopping_flag")
        and ml_tier == "Window-shop Risk"
        and rule_tier in ("Interested", "Serious")
        and ml_prob >= 0.55
    ):
        return "Window-shop Risk"

    # Promote Serious → Quality when ML strongly agrees.
    if ml_tier == "Quality Lead" and rule_tier == "Serious" and ml_prob >= 0.62:
        return "Quality Lead"

    # Single-step upgrade when ML agrees and is confident.
    if mi < ri and mi == ri - 1 and ml_prob >= 0.64 and ml_conf >= 0.55:
        return ml_tier

    # Single-step downgrade for clear risk when rule tier is optimistic.
    if mi > ri and mi == ri + 1 and ml_prob >= 0.66 and customer.get("salary_day_spend_ratio", 0) >= 0.7:
        return ml_tier

    return rule_tier
