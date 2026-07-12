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


def warmup() -> None:
    """Pre-load dataset, scores, ML model, and heavy report pages at startup."""
    from app.ml_model import get_model

    get_ranked_customers()
    get_impact_metrics()
    get_ml_report()
    get_model()
    print("Dataset cache warmed (ranked leads + impact + ML report)", flush=True)


def clear_cache_for_tests() -> None:
    """Reset module cache — for tests only."""
    global _customers, _ranked, _ranked_by_id, _impact, _ml_report, _backtest
    _customers = _ranked = _ranked_by_id = _impact = _ml_report = _backtest = None
