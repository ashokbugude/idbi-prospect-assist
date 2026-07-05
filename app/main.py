from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from urllib.parse import urlencode

from fastapi import FastAPI, Request, Form, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.auth import auth_token, is_authenticated, require_auth, verify_pin
from app.config import APP_TITLE, APP_VERSION, AUTH_COOKIE, HERO_CUSTOMERS
from app.scoring import (
    LEAD_TIERS,
    PRODUCT_LABELS,
    TIER_CSS,
    compute_impact_metrics,
    rank_customers,
    score_customer,
)

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "customers.json"
DASHBOARD_PAGE_SIZE = 20

app = FastAPI(
    title=APP_TITLE,
    description="Track 02 — behavioral repayment capacity + intent scoring for liability customers",
    version=APP_VERSION,
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@app.middleware("http")
async def rm_auth_middleware(request: Request, call_next):
    redirect = require_auth(request)
    if redirect:
        return redirect
    return await call_next(request)


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


def _paginate(items: list[dict], page: int, per_page: int = DASHBOARD_PAGE_SIZE) -> tuple[list[dict], dict]:
    total = len(items)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    page_items = items[start : start + per_page]
    return page_items, {
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages,
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "range_start": start + 1 if total else 0,
        "range_end": start + len(page_items),
    }


def _dashboard_query(
    page: int,
    product: str | None = None,
    tier: str | None = None,
    min_score: float = 0,
    multi_bank: bool = False,
) -> str:
    params: dict[str, str | int | float] = {"page": page}
    if product:
        params["product"] = product
    if tier:
        params["tier"] = tier
    if min_score > 0:
        params["min_score"] = min_score
    if multi_bank:
        params["multi_bank"] = "true"
    return "?" + urlencode(params)


def _dashboard_table_context(
    product: str | None,
    tier: str | None,
    min_score: float,
    multi_bank: bool,
    page: int,
) -> dict:
    all_ranked = rank_customers(load_customers())
    ranked = _apply_filters(all_ranked, product, tier, min_score, multi_bank_only=multi_bank)
    customers, pagination = _paginate(ranked, page)
    return {
        "customers": customers,
        "pagination": pagination,
        "page_query": lambda p: _dashboard_query(
            p, product=product, tier=tier, min_score=min_score, multi_bank=multi_bank
        ),
    }


def _multibank_customers() -> list[dict]:
    ranked = rank_customers(load_customers())
    return [c for c in ranked if c.get("has_other_bank_accounts")]


def _multibank_query(page: int) -> str:
    return "?" + urlencode({"page": page})


def _multibank_table_context(page: int) -> dict:
    customers, pagination = _paginate(_multibank_customers(), page)
    return {
        "customers": customers,
        "pagination": pagination,
        "page_query": lambda p: _multibank_query(p),
    }


def _rescored_profile(raw: dict, enriched: dict) -> dict:
    before = score_customer(raw)
    after = score_customer(enriched)
    return {
        "lead_tier": after["lead_tier"],
        "lead_tier_css": TIER_CSS.get(after["lead_tier"], ""),
        "composite_lead_score": after["composite_lead_score"],
        "affordable_emi_estimate": after.get("affordable_emi_estimate"),
        "holistic_monthly_income": after.get("holistic_monthly_income"),
        "previous_tier": before["lead_tier"],
        "previous_tier_css": TIER_CSS.get(before["lead_tier"], ""),
        "previous_composite_lead_score": before["composite_lead_score"],
        "tier_changed": before["lead_tier"] != after["lead_tier"],
    }


def _tier_explanation(profile: dict) -> list[str]:
    items: list[str] = []
    for key in ("repayment_capacity", "purchase_intent", "behavioral_discipline"):
        dim = profile.get(key) or {}
        reasons = dim.get("reasons") or []
        if reasons:
            items.append(f"{dim.get('name', key)}: {reasons[0]}")
    ml = profile.get("ml_enhancement") or {}
    if ml.get("applied") and ml.get("nudge_applied"):
        items.append(f"ML nudge: {ml['nudge_applied']} (confidence {ml.get('ml_confidence', '—')})")
    return items[:4]


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
        "digital_avg_session": round(
            sum(
                c.get("purchase_intent", {}).get("details", {}).get("avg_session_minutes", 0)
                for c in all_ranked
            ) / len(all_ranked),
            1,
        ) if all_ranked else 0,
        "digital_calc_pct": round(
            sum(
                1
                for c in all_ranked
                if c.get("purchase_intent", {}).get("details", {}).get("loan_calculator_uses", 0) > 0
            )
            / len(all_ranked) * 100,
            1,
        ) if all_ranked else 0,
        "digital_app_started_pct": round(
            sum(
                1
                for c in all_ranked
                if c.get("purchase_intent", {}).get("details", {}).get("application_started")
            )
            / len(all_ranked) * 100,
            1,
        ) if all_ranked else 0,
    }


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str | None = None):
    if is_authenticated(request):
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": error, "active": ""},
    )


@app.post("/login")
async def login_submit(pin: str = Form(...)):
    if not verify_pin(pin):
        return RedirectResponse(url="/login?error=1", status_code=302)
    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie(AUTH_COOKIE, auth_token(), httponly=True, samesite="lax", max_age=86400 * 7)
    return response


@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie(AUTH_COOKIE)
    return response


@app.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    product: str | None = None,
    tier: str | None = None,
    min_score: float = 0,
    multi_bank: bool = False,
    page: int = 1,
):
    all_ranked = rank_customers(load_customers())
    ranked = _apply_filters(all_ranked, product, tier, min_score, multi_bank_only=multi_bank)
    table_ctx = _dashboard_table_context(product, tier, min_score, multi_bank, page)

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            **table_ctx,
            "rm_queue": [c for c in all_ranked if c.get("rm_call_eligible")][:10],
            "stats": _dashboard_stats(ranked, all_ranked),
            "products": PRODUCT_LABELS,
            "lead_tiers": LEAD_TIERS,
            "selected_product": product,
            "selected_tier": tier,
            "min_score": min_score,
            "multi_bank": multi_bank,
            "active": "dashboard",
            "hero_customers": HERO_CUSTOMERS,
        },
    )


@app.get("/partials/dashboard-table", response_class=HTMLResponse)
async def dashboard_table_partial(
    request: Request,
    product: str | None = None,
    tier: str | None = None,
    min_score: float = 0,
    multi_bank: bool = False,
    page: int = 1,
):
    return templates.TemplateResponse(
        "index_table_partial.html",
        {"request": request, **_dashboard_table_context(product, tier, min_score, multi_bank, page)},
    )


@app.get("/ml", response_class=HTMLResponse)
async def ml_credibility_page(request: Request):
    from app.ml_evaluation import get_ml_credibility_report

    return templates.TemplateResponse(
        "ml.html",
        {"request": request, "report": get_ml_credibility_report(load_customers()), "active": "ml"},
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
        {"request": request, "impact": impact, "active": "impact"},
    )


@app.get("/multi-bank", response_class=HTMLResponse)
async def multi_bank_page(request: Request, page: int = 1):
    return templates.TemplateResponse(
        "multi_bank.html",
        {
            "request": request,
            "all_customers": load_customers(),
            "active": "multi-bank",
            **_multibank_table_context(page),
        },
    )


@app.get("/partials/multi-bank-table", response_class=HTMLResponse)
async def multi_bank_table_partial(request: Request, page: int = 1):
    return templates.TemplateResponse(
        "multi_bank_table_partial.html",
        {"request": request, **_multibank_table_context(page)},
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
    return {
        "customer_id": customer_id,
        "multibank_analysis": analysis,
        "rescored_profile": _rescored_profile(raw, enriched),
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
            "active": "architecture",
        },
    )


@app.get("/customer/{customer_id}", response_class=HTMLResponse)
async def customer_detail(request: Request, customer_id: str):
    from app.rm_brief import generate_rm_brief
    from app.transaction_timeline import build_transaction_timeline

    raw = _find_customer(customer_id)
    if not raw:
        return RedirectResponse(url="/", status_code=302)

    profile = score_customer(raw)
    timeline = build_transaction_timeline(raw)
    rm_brief = generate_rm_brief(profile)
    need = float(raw.get("need_spend_ratio", 0.5))
    want = float(raw.get("want_spend_ratio", max(0, 1 - need - float(raw.get("luxury_spend_ratio", 0.15)))))
    luxury = float(raw.get("luxury_spend_ratio", 0.15))
    spend_breakdown = {"need": need, "want": want, "luxury": luxury}

    return templates.TemplateResponse(
        "detail.html",
        {
            "request": request,
            "customer": profile,
            "raw": raw,
            "timeline": timeline,
            "rm_brief": rm_brief,
            "spend_breakdown": spend_breakdown,
            "tier_explanation": _tier_explanation(profile),
            "active": "",
        },
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


@app.get("/api/demo-comparison")
async def api_demo_comparison():
    impact = compute_impact_metrics(load_customers())
    return {
        "before": {
            "label": "Spray & pray (all leads)",
            "conversion_pct": impact.get("baseline_conversion_pct", 1.0),
            "rm_calls_pct": 100,
            "leads_contacted": impact.get("total_leads", 0),
        },
        "after": {
            "label": "RM-prioritized queue",
            "conversion_pct": impact.get("rm_queue_conversion_pct", 0),
            "quality_segment_pct": impact.get("quality_lead_conversion_pct", 0),
            "rm_calls_pct": impact.get("rm_queue_pct", 0),
            "rm_time_saved_pct": impact.get("estimated_rm_time_saved_pct", 0),
            "leads_contacted": impact.get("rm_actionable_leads", 0),
        },
        "lift_multiplier": impact.get("proof_summary", {}).get("rm_lift_multiplier", 0),
        "track02_target_met": impact.get("meets_track02_conversion_target", False),
    }


@app.post("/api/aa/consent")
async def api_aa_consent(customer_id: str = Form(...)):
    from app.account_aggregator import initiate_aa_consent

    if not _find_customer(customer_id):
        return JSONResponse({"error": "Customer not found"}, status_code=404)
    return initiate_aa_consent(customer_id)


@app.post("/api/aa/fetch")
async def api_aa_fetch(customer_id: str = Form(...), consent_id: str = Form(...)):
    from app.account_aggregator import fetch_aa_statements

    raw = _find_customer(customer_id)
    if not raw:
        return JSONResponse({"error": "Customer not found"}, status_code=404)
    return fetch_aa_statements(raw, consent_id)


@app.get("/api/customer/{customer_id}/rm-brief")
async def api_rm_brief(customer_id: str):
    from app.rm_brief import generate_rm_brief

    raw = _find_customer(customer_id)
    if not raw:
        return JSONResponse({"error": "Customer not found"}, status_code=404)
    return generate_rm_brief(score_customer(raw))


@app.get("/api/customer/{customer_id}/underwriter-pdf")
async def api_underwriter_pdf(customer_id: str):
    from app.pdf_export import build_underwriter_pdf

    raw = _find_customer(customer_id)
    if not raw:
        return JSONResponse({"error": "Customer not found"}, status_code=404)
    profile = score_customer(raw)
    pdf_bytes = build_underwriter_pdf(profile, raw)
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="underwriter_{customer_id}.pdf"',
        },
    )


@app.get("/api/sandbox/{customer_id}")
async def sandbox_stub(customer_id: str):
    """
    Post-shortlist IDBI sandbox API stub.
    Returns synthetic transaction + bureau payload shape for integration testing.
    """
    from app.transaction_timeline import build_transaction_timeline

    raw = _find_customer(customer_id)
    if not raw:
        return {"error": "Customer not found", "sandbox": True}

    profile = score_customer(raw)
    timeline = build_transaction_timeline(raw)
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
        "sample_transactions": timeline["entries"][:10],
        "digital_footprint": {
            "loan_page_visits_30d": raw.get("loan_page_visits_30d"),
            "loan_calculator_uses": raw.get("loan_calculator_uses"),
            "avg_session_minutes": raw.get("avg_session_minutes"),
            "application_started": raw.get("application_started"),
            "window_shopping_flag": raw.get("window_shopping_flag"),
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
        "version": APP_VERSION,
        "ml_ready": get_model().is_ready,
    }
