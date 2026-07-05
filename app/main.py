from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.scoring import (
    LEAD_TIERS,
    PRODUCT_LABELS,
    compute_impact_metrics,
    rank_customers,
    score_customer,
)

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "customers.json"

app = FastAPI(
    title="IDBI Prospect Assist AI",
    description="Track 02 — behavioral repayment capacity + intent scoring for liability customers",
    version="0.6.1",
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


def load_customers() -> list[dict]:
    if not DATA_PATH.exists():
        from app.data_generator import save_dataset

        save_dataset(DATA_PATH)
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def _find_customer(customer_id: str) -> dict | None:
    return next((c for c in load_customers() if c["customer_id"] == customer_id), None)


def _apply_filters(
    ranked: list[dict],
    product: str | None,
    tier: str | None,
    min_score: float,
    multi_bank_only: bool = False,
) -> list[dict]:
    if multi_bank_only:
        ranked = [c for c in ranked if c.get("has_other_bank_accounts")]

    if product and product in PRODUCT_LABELS:
        filtered: list[dict] = []
        for c in ranked:
            match = next((s for s in c["all_scores"] if s["product"] == product), None)
            if not match:
                continue
            filtered.append({
                **c,
                "filter_score": match["score"],
                "display_reasons": match["reasons"],
                "display_product_label": match["label"],
            })
        ranked = sorted(
            filtered,
            key=lambda c: (
                LEAD_TIERS.index(c["lead_tier"]) if c["lead_tier"] in LEAD_TIERS else 99,
                -c["filter_score"],
            ),
        )

    if tier and tier in LEAD_TIERS:
        ranked = [c for c in ranked if c["lead_tier"] == tier]

    if min_score > 0:
        ranked = [c for c in ranked if c["composite_lead_score"] >= min_score]

    return ranked


def _dashboard_stats(ranked: list[dict], all_ranked: list[dict]) -> dict:
    total = len(ranked)
    impact = compute_impact_metrics(load_customers())
    return {
        "total": total,
        "quality_leads": sum(1 for c in ranked if c["lead_tier"] == "Quality Lead"),
        "serious": sum(1 for c in ranked if c["lead_tier"] == "Serious"),
        "window_shop": sum(1 for c in ranked if c["lead_tier"] == "Window-shop Risk"),
        "rm_queue": sum(1 for c in all_ranked if c.get("rm_call_eligible")),
        "multi_bank": sum(1 for c in all_ranked if c.get("has_other_bank_accounts")),
        "avg_composite": round(
            sum(c["composite_lead_score"] for c in ranked) / total, 1
        ) if total else 0,
        "baseline_conversion_pct": impact.get("baseline_conversion_pct", 1.0),
        "rm_queue_conversion_pct": impact.get("rm_queue_conversion_pct", 0),
        "projected_conversion_pct": impact.get("rm_queue_conversion_pct", 0),
        "quality_lead_conversion_pct": impact.get("quality_lead_conversion_pct", 0),
        "quality_conversion_target_pct": impact.get("quality_conversion_target_pct", 32),
        "meets_track02_target": impact.get("meets_track02_conversion_target", False),
        "rm_queue_pct": impact.get("rm_queue_pct", 0),
        "rm_time_saved_pct": impact.get("estimated_rm_time_saved_pct", 0),
        "incremental_portfolio_value_cr": impact.get("incremental_portfolio_value_cr", 0),
        "conversion_story": (
            f"Baseline ~{impact.get('baseline_conversion_pct', 1)}% → "
            f"RM queue ~{impact.get('rm_queue_conversion_pct', 0)}% · "
            f"Quality segment ~{impact.get('quality_lead_conversion_pct', 0)}% "
            f"(target {impact.get('quality_conversion_target_pct', 32)}%)"
        ),
    }


@app.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    product: str | None = None,
    tier: str | None = None,
    min_score: float = 0,
    multi_bank: bool = False,
):
    all_ranked = rank_customers(load_customers())
    ranked = _apply_filters(all_ranked, product, tier, min_score, multi_bank_only=multi_bank)

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "customers": ranked[:50],
            "rm_queue": [c for c in all_ranked if c.get("rm_call_eligible")][:10],
            "stats": _dashboard_stats(ranked, all_ranked),
            "products": PRODUCT_LABELS,
            "lead_tiers": LEAD_TIERS,
            "selected_product": product,
            "selected_tier": tier,
            "min_score": min_score,
            "multi_bank": multi_bank,
        },
    )


@app.get("/ml", response_class=HTMLResponse)
async def ml_credibility_page(request: Request):
    from app.ml_evaluation import get_ml_credibility_report

    return templates.TemplateResponse(
        "ml.html",
        {"request": request, "report": get_ml_credibility_report(load_customers())},
    )


@app.get("/api/ml/evaluation")
async def api_ml_evaluation():
    from app.ml_evaluation import get_ml_credibility_report

    return get_ml_credibility_report(load_customers())


@app.get("/api/impact/backtest")
async def api_impact_backtest():
    from app.impact import run_conversion_backtest

    return run_conversion_backtest(load_customers(), trials=500)


@app.get("/impact", response_class=HTMLResponse)
async def impact_page(request: Request):
    impact = compute_impact_metrics(load_customers())
    return templates.TemplateResponse(
        "impact.html",
        {"request": request, "impact": impact},
    )


@app.get("/multi-bank", response_class=HTMLResponse)
async def multi_bank_page(request: Request):
    ranked = rank_customers(load_customers())
    multi = [c for c in ranked if c.get("has_other_bank_accounts")][:40]
    return templates.TemplateResponse(
        "multi_bank.html",
        {"request": request, "customers": multi, "all_customers": load_customers()},
    )


@app.post("/api/multi-bank/analyze")
async def analyze_multibank_upload(
    customer_id: str = Form(...),
    other_bank_monthly_inflow: int = Form(0),
):
    """Simulate other-bank statement upload and re-score."""
    from app.multibank import analyze_multibank

    raw = _find_customer(customer_id)
    if not raw:
        return JSONResponse({"error": "Customer not found"}, status_code=404)

    analysis = analyze_multibank(raw, other_bank_monthly_inflow or None)
    enriched = dict(raw)
    enriched["has_other_bank_accounts"] = True
    if other_bank_monthly_inflow > 0:
        enriched["multi_bank_income_share"] = round(
            other_bank_monthly_inflow / max(analysis["holistic_monthly_income"], 1), 2
        )
    profile = score_customer(enriched)
    return {
        "customer_id": customer_id,
        "multibank_analysis": analysis,
        "rescored_profile": {
            "lead_tier": profile["lead_tier"],
            "composite_lead_score": profile["composite_lead_score"],
            "affordable_emi_estimate": profile.get("affordable_emi_estimate"),
            "holistic_monthly_income": profile.get("holistic_monthly_income"),
        },
    }


@app.get("/api/ml/model-card")
async def api_model_card():
    from app.ml_model import get_model

    model = get_model()
    if not model.is_ready:
        return {"ready": False, "message": "Run scripts/train_model.py"}
    return {"ready": True, **model.model_card()}


@app.get("/api/impact/methodology")
async def api_impact_methodology():
    impact = compute_impact_metrics(load_customers())
    return {
        "impact_summary": impact,
        "methodology": impact.get("methodology", {}),
    }


@app.get("/architecture", response_class=HTMLResponse)
async def architecture(request: Request):
    from app.features import FEATURE_NAMES
    from app.ml_model import get_model

    model = get_model()
    model_card = model.model_card() if model.is_ready else {}
    return templates.TemplateResponse(
        "architecture.html",
        {
            "request": request,
            "ml_ready": model.is_ready,
            "feature_count": len(FEATURE_NAMES),
            "model_card": model_card,
        },
    )


@app.get("/customer/{customer_id}", response_class=HTMLResponse)
async def customer_detail(request: Request, customer_id: str):
    raw = _find_customer(customer_id)
    if not raw:
        return RedirectResponse(url="/", status_code=302)

    profile = score_customer(raw)
    return templates.TemplateResponse(
        "detail.html",
        {"request": request, "customer": profile, "raw": raw},
    )


@app.get("/api/customers")
async def api_customers(limit: int = 100, tier: str | None = None):
    ranked = rank_customers(load_customers())
    if tier:
        ranked = [c for c in ranked if c["lead_tier"] == tier]
    return {"count": len(ranked), "customers": ranked[:limit]}


@app.get("/api/customers/{customer_id}")
async def api_customer_detail(customer_id: str):
    raw = _find_customer(customer_id)
    if not raw:
        return {"error": "Customer not found"}
    return score_customer(raw)


@app.get("/api/impact")
async def api_impact():
    return compute_impact_metrics(load_customers())


@app.get("/api/rm-queue")
async def api_rm_queue(limit: int = 20):
    ranked = rank_customers(load_customers())
    queue = [c for c in ranked if c.get("rm_call_eligible")]
    return {"count": len(queue), "customers": queue[:limit]}


@app.get("/api/rm-queue/export")
async def api_rm_queue_export():
    """CSV export for RM outreach lists."""
    ranked = rank_customers(load_customers())
    queue = [c for c in ranked if c.get("rm_call_eligible")]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "customer_id", "name", "city", "lead_tier", "composite_score",
        "top_product", "recommended_action", "monthly_income",
        "inferred_income", "holistic_income", "rm_call_eligible",
    ])
    for c in queue:
        writer.writerow([
            c["customer_id"],
            c["name"],
            c["city"],
            c["lead_tier"],
            c["composite_lead_score"],
            c["top_product_label"],
            c["recommended_action"],
            c.get("monthly_income", ""),
            c.get("inferred_monthly_income", ""),
            c.get("holistic_monthly_income", ""),
            c.get("rm_call_eligible", False),
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=rm_priority_queue.csv"},
    )


@app.get("/api/multi-bank")
async def api_multi_bank(limit: int = 50):
    """Customers with multi-bank footprint — holistic income view."""
    ranked = rank_customers(load_customers())
    multi = [c for c in ranked if c.get("has_other_bank_accounts")]
    return {
        "count": len(multi),
        "customers": [
            {
                "customer_id": c["customer_id"],
                "name": c["name"],
                "lead_tier": c["lead_tier"],
                "composite_lead_score": c["composite_lead_score"],
                "stated_income": c.get("monthly_income"),
                "inferred_income": c.get("inferred_monthly_income"),
                "holistic_income": c.get("holistic_monthly_income"),
                "income_confidence": c.get("income_confidence"),
                "top_product": c["top_product_label"],
            }
            for c in multi[:limit]
        ],
    }


@app.get("/api/sandbox/{customer_id}")
async def sandbox_stub(customer_id: str):
    """
    Post-shortlist IDBI sandbox API stub.
    Returns synthetic transaction + bureau payload shape for integration testing.
    """
    raw = _find_customer(customer_id)
    if not raw:
        return {"error": "Customer not found", "sandbox": True}

    profile = score_customer(raw)
    return {
        "sandbox": True,
        "status": "stub",
        "message": "Replace with IDBI AWS sandbox endpoints after shortlist",
        "customer_id": customer_id,
        "endpoints": {
            "transactions": f"/sandbox/v1/customers/{customer_id}/transactions",
            "bureau": f"/sandbox/v1/customers/{customer_id}/bureau",
            "digital_footprint": f"/sandbox/v1/customers/{customer_id}/digital",
        },
        "sample_payload": {
            "monthly_credit_inflow": raw.get("monthly_credit_inflow"),
            "geo_transaction_consistency": raw.get("geo_transaction_consistency"),
            "bureau_enquiries_90d": raw.get("bureau_enquiries_90d"),
            "credit_score_band": raw.get("credit_score_band"),
        },
        "scoring_preview": {
            "lead_tier": profile["lead_tier"],
            "composite_lead_score": profile["composite_lead_score"],
            "delinquency_risk": profile.get("delinquency_risk", {}),
            "geo_stability": profile.get("geo_stability", {}),
        },
    }


@app.get("/api/stats")
async def api_stats():
    return compute_impact_metrics(load_customers())


@app.get("/api/health")
async def health():
    from app.ml_model import get_model

    return {
        "status": "ok",
        "track": "02-prospect-assist-ai",
        "version": "0.6.0",
        "ml_ready": get_model().is_ready,
    }
