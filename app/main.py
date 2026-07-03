from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
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
    version="0.4.0",
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
) -> list[dict]:
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
        "avg_composite": round(
            sum(c["composite_lead_score"] for c in ranked) / total, 1
        ) if total else 0,
        "baseline_conversion_pct": impact.get("baseline_conversion_pct", 1.0),
        "projected_conversion_pct": impact.get("projected_conversion_pct", 0),
        "rm_queue_pct": impact.get("rm_queue_pct", 0),
        "rm_time_saved_pct": impact.get("estimated_rm_time_saved_pct", 0),
        "conversion_story": (
            f"Baseline ~{impact.get('baseline_conversion_pct', 1)}% conversion → "
            f"~{impact.get('projected_conversion_pct', 0)}% on RM-prioritized queue "
            f"({impact.get('rm_actionable_leads', 0)} actionable leads)"
        ),
    }


@app.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    product: str | None = None,
    tier: str | None = None,
    min_score: float = 0,
):
    all_ranked = rank_customers(load_customers())
    ranked = _apply_filters(all_ranked, product, tier, min_score)

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


@app.get("/api/stats")
async def api_stats():
    return compute_impact_metrics(load_customers())


@app.get("/api/health")
async def health():
    from app.ml_model import get_model

    return {
        "status": "ok",
        "track": "02-prospect-assist-ai",
        "version": "0.4.0",
        "ml_ready": get_model().is_ready,
    }
