"""In-memory cache for static demo dataset — avoids re-scoring 200 leads per request."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "customers.json"

_customers: list[dict] | None = None
_ranked: list[dict] | None = None
_ranked_by_id: dict[str, dict] | None = None
_impact: dict[str, Any] | None = None
_ml_report: dict[str, Any] | None = None
_backtest: dict[str, Any] | None = None
_portfolio: dict[str, Any] | None = None
_fairness: dict[str, Any] | None = None
_uplift_cache: dict[str, dict] = {}
_monitoring: dict[str, Any] | None = None
_data_quality: dict[str, Any] | None = None


def get_customers() -> list[dict]:
    global _customers
    if _customers is None:
        if not DATA_PATH.exists():
            from app.data_generator import save_dataset

            save_dataset(DATA_PATH)
        _customers = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    return _customers


def get_ranked_customers() -> list[dict]:
    global _ranked, _ranked_by_id
    if _ranked is None:
        from app.scoring import rank_customers

        _ranked = rank_customers(get_customers())
        _ranked_by_id = {c["customer_id"]: c for c in _ranked}
    return _ranked


def get_customer_raw(customer_id: str) -> dict | None:
    return next((c for c in get_customers() if c["customer_id"] == customer_id), None)


def get_scored_profile(customer_id: str) -> dict | None:
    get_ranked_customers()
    assert _ranked_by_id is not None
    return _ranked_by_id.get(customer_id)


def get_impact_metrics() -> dict[str, Any]:
    global _impact
    if _impact is None:
        from app.scoring import compute_impact_metrics

        _impact = compute_impact_metrics(get_customers())
    return _impact


def get_ml_report() -> dict[str, Any]:
    global _ml_report
    if _ml_report is None:
        from app.ml_evaluation import get_ml_credibility_report

        _ml_report = get_ml_credibility_report(get_customers())
    return _ml_report


def get_backtest_result() -> dict[str, Any]:
    global _backtest
    if _backtest is None:
        from app.impact import run_conversion_backtest

        _backtest = run_conversion_backtest(get_customers(), trials=500)
    return _backtest


def get_portfolio_actions() -> dict[str, Any]:
    """Branch-wide Next Best Action plan (cached — one pass over the whole book)."""
    global _portfolio
    if _portfolio is None:
        from app.next_best_action import build_portfolio_actions

        raw_by_id = {c["customer_id"]: c for c in get_customers()}
        _portfolio = build_portfolio_actions(get_ranked_customers(), raw_by_id)
    return _portfolio


def get_fairness_report() -> dict[str, Any]:
    """Fair-lending audit over the scored population (cached)."""
    global _fairness
    if _fairness is None:
        from app.fairness import build_fairness_report

        _fairness = build_fairness_report(get_customers(), get_ranked_customers())
    return _fairness


def get_uplift(customer_id: str) -> dict | None:
    """Per-customer counterfactual report (cached per customer)."""
    if customer_id in _uplift_cache:
        return _uplift_cache[customer_id]
    raw = get_customer_raw(customer_id)
    if not raw:
        return None
    from app.uplift import simulate_uplift

    from app.scoring import score_customer_rules

    report = simulate_uplift(raw, score_customer_rules(raw))
    _uplift_cache[customer_id] = report
    return report


def get_monitoring_report() -> dict[str, Any]:
    """Population drift (PSI) against the training distribution (cached)."""
    global _monitoring
    if _monitoring is None:
        from app.monitoring import build_monitoring_report

        _monitoring = build_monitoring_report(get_customers())
    return _monitoring


def get_data_quality_report() -> dict[str, Any]:
    """Field completeness plus computed degradation under missing data (cached)."""
    global _data_quality
    if _data_quality is None:
        from app.data_quality import build_data_quality_report
        from app.scoring import score_customer_rules

        baseline = [score_customer_rules(c) for c in get_customers()]
        _data_quality = build_data_quality_report(get_customers(), baseline)
    return _data_quality


def get_outcome_report() -> dict[str, Any]:
    """Outcome feedback loop — never cached; it changes as RMs log dispositions."""
    from app.outcomes import build_outcome_report

    return build_outcome_report()


def warmup() -> None:
    """Pre-load dataset, scores, ML model, and heavy report pages at startup."""
    from app.ml_model import get_model

    get_ranked_customers()
    get_impact_metrics()
    get_ml_report()
    get_portfolio_actions()
    get_fairness_report()
    get_monitoring_report()
    get_data_quality_report()
    get_model()

    # Seed the governance and feedback artefacts so a cold start still
    # demonstrates the mechanism rather than an empty table.
    try:
        from app import audit, outcomes

        outcomes.seed_simulated_outcomes(get_ranked_customers())
        audit.record_lead_decisions(get_ranked_customers())
    except Exception as exc:  # never let an instrumentation failure block boot
        print(f"Governance seed skipped: {type(exc).__name__}", flush=True)
    print(
        "Dataset cache warmed (leads + impact + ML + NBA + fairness + drift + data quality)",
        flush=True,
    )


def clear_cache_for_tests() -> None:
    """Reset module cache — for tests only."""
    global _customers, _ranked, _ranked_by_id, _impact, _ml_report, _backtest
    global _portfolio, _fairness, _monitoring, _data_quality
    _customers = _ranked = _ranked_by_id = _impact = _ml_report = _backtest = None
    _portfolio = _fairness = _monitoring = _data_quality = None
    _uplift_cache.clear()
