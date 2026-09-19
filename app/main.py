from __future__ import annotations

import csv
import hashlib
import io
from contextlib import asynccontextmanager
from pathlib import Path

from urllib.parse import urlencode

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.auth import auth_token, is_authenticated, require_auth, rm_session_active, verify_pin
from app.config import APP_TITLE, APP_VERSION, AUTH_COOKIE, DEPLOY_PLATFORM, HERO_CUSTOMERS, PUBLIC_DEMO_URL
from app.dataset_store import (
    get_customer_raw,
    get_customers,
    get_data_quality_report,
    get_fairness_report,
    get_monitoring_report,
    get_outcome_report,
    get_impact_metrics,
    get_ml_report,
    get_portfolio_actions,
    get_ranked_customers,
    get_scored_profile,
    get_backtest_result,
    get_uplift,
    warmup,
)
from app.scoring import (
    LEAD_TIERS,
    PRODUCT_LABELS,
    TIER_CSS,
    score_customer,
)

BASE_DIR = Path(__file__).resolve().parent
DASHBOARD_PAGE_SIZE = 20


@asynccontextmanager
async def lifespan(_app: FastAPI):
    warmup()
    yield


app = FastAPI(
    title=APP_TITLE,
    description="Track 02 — behavioral repayment capacity + intent scoring for liability customers",
    version=APP_VERSION,
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")
templates.env.globals["deploy_platform"] = DEPLOY_PLATFORM
templates.env.globals["public_demo_url"] = PUBLIC_DEMO_URL
templates.env.globals["rm_session_active"] = rm_session_active


def asset_version() -> str:
    """
    Fingerprint the static assets so a stale — or partially transferred —
    stylesheet can never survive a reload or a redeploy.

    A dev-server restart mid-transfer leaves the browser holding a truncated
    style.css: early rules apply, later ones silently do not, and the page looks
    half-styled until a hard refresh. Versioning the URL makes any change a new
    URL, so the browser refetches instead of reusing what it has.
    """
    stamp = []
    for name in ("style.css", "nav.js"):
        asset = BASE_DIR / "static" / name
        try:
            stat = asset.stat()
            stamp.append(f"{name}:{stat.st_mtime_ns}:{stat.st_size}")
        except OSError:
            stamp.append(f"{name}:missing")
    return hashlib.sha1("|".join(stamp).encode()).hexdigest()[:10]


templates.env.globals["asset_version"] = asset_version


@app.middleware("http")
async def rm_auth_middleware(request: Request, call_next):
    redirect = require_auth(request)
    if redirect:
        return redirect
    return await call_next(request)


def _find_customer(customer_id: str) -> dict | None:
    return get_customer_raw(customer_id)


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
    all_ranked: list[dict] | None = None,
) -> dict:
    ranked_source = all_ranked if all_ranked is not None else get_ranked_customers()
    ranked = _apply_filters(ranked_source, product, tier, min_score, multi_bank_only=multi_bank)
    customers, pagination = _paginate(ranked, page)
    return {
        "customers": customers,
        "pagination": pagination,
        "page_query": lambda p: _dashboard_query(
            p, product=product, tier=tier, min_score=min_score, multi_bank=multi_bank
        ),
    }


def _multibank_customers() -> list[dict]:
    return [c for c in get_ranked_customers() if c.get("has_other_bank_accounts")]


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
    from app.enrichment import idbi_only_baseline

    before = score_customer(idbi_only_baseline(raw))
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


DIMENSION_LABELS = {
    "repayment_capacity": "Repayment capacity",
    "purchase_intent": "Purchase intent",
    "behavioral_discipline": "Behavioural discipline",
}


def _tier_explanation(profile: dict) -> list[str]:
    items: list[str] = []
    for key, label in DIMENSION_LABELS.items():
        dim = profile.get(key) or {}
        reasons = dim.get("reasons") or []
        if reasons:
            items.append(f"{dim.get('name') or label}: {reasons[0]}")
    ml = profile.get("ml_enhancement") or {}
    if ml.get("applied") and ml.get("nudge_applied"):
        items.append(f"ML nudge: {ml['nudge_applied']} (confidence {ml.get('ml_confidence', '—')})")
    return items[:4]


def _dashboard_stats(ranked: list[dict], all_ranked: list[dict]) -> dict:
    total = len(ranked)
    impact = get_impact_metrics()
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
    all_ranked = get_ranked_customers()
    ranked = _apply_filters(all_ranked, product, tier, min_score, multi_bank_only=multi_bank)
    table_ctx = _dashboard_table_context(product, tier, min_score, multi_bank, page, all_ranked)

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
    return templates.TemplateResponse(
        "ml.html",
        {"request": request, "report": get_ml_report(), "active": "ml"},
    )


@app.get("/api/ml/evaluation")
async def api_ml_evaluation():
    return get_ml_report()


@app.get("/api/impact/backtest")
async def api_impact_backtest():
    return get_backtest_result()


@app.get("/impact", response_class=HTMLResponse)
async def impact_page(request: Request):
    impact = get_impact_metrics()
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
            "all_customers": get_customers(),
            "hero_aa_customer": HERO_CUSTOMERS["multibank_uplift"],
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
    impact = get_impact_metrics()
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


@app.get("/actions", response_class=HTMLResponse)
async def actions_page(request: Request):
    """Branch-wide Next Best Action plan — today's work, costed in RM minutes."""
    return templates.TemplateResponse(
        "actions.html",
        {"request": request, "portfolio": get_portfolio_actions(), "active": "actions"},
    )


@app.get("/governance", response_class=HTMLResponse)
async def governance_page(request: Request, tab: str = "fairness"):
    """Fair-lending audit, model risk (audit log + drift), and data quality."""
    from app.audit import build_audit_report

    return templates.TemplateResponse(
        "governance.html",
        {
            "request": request,
            "report": get_fairness_report(),
            "audit": build_audit_report(),
            "drift": get_monitoring_report(),
            "quality": get_data_quality_report(),
            "tab": tab if tab in ("fairness", "model-risk", "data-quality") else "fairness",
            "active": "governance",
        },
    )


@app.get("/fairness")
async def fairness_redirect():
    """Kept so existing links and the USP evidence trail do not break."""
    return RedirectResponse(url="/governance?tab=fairness", status_code=302)


@app.get("/outcomes", response_class=HTMLResponse)
async def outcomes_page(request: Request):
    """Outcome feedback loop — what happened after the RM acted."""
    return templates.TemplateResponse(
        "outcomes.html",
        {"request": request, "report": get_outcome_report(), "active": "outcomes"},
    )


@app.post("/api/outcomes")
async def api_record_outcome(
    customer_id: str = Form(...),
    disposition: str = Form(...),
    notes: str = Form(""),
    rm_id: str = Form("demo-rm"),
):
    """Capture an RM call disposition — the label the next model trains on."""
    from app import audit
    from app.outcomes import record_outcome

    raw = _find_customer(customer_id)
    if not raw:
        return JSONResponse({"error": "Customer not found"}, status_code=404)
    profile = get_scored_profile(customer_id) or score_customer(raw)

    try:
        record = record_outcome(
            customer_id=customer_id,
            disposition=disposition,
            lead_tier=profile["lead_tier"],
            action_code=profile.get("top_product", ""),
            composite_lead_score=profile.get("composite_lead_score"),
            rm_id=rm_id,
            notes=notes,
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)

    audit.record(
        "outcome_recorded",
        actor=rm_id,
        customer_id=customer_id,
        summary=f"{profile['lead_tier']} → {disposition}",
        outputs={"disposition": disposition, "converted": record["converted"]},
    )
    return {"recorded": record, "report": get_outcome_report()}


@app.get("/api/outcomes")
async def api_outcomes():
    return get_outcome_report()


@app.post("/api/ingest/check")
async def api_ingest_check(record: dict):
    """
    Run one raw record through the ingest gate.

    Lets IDBI test a real sandbox payload against the coercion and validation
    rules before any integration work starts.
    """
    from app.ingest import validate_customer

    if not isinstance(record, dict):
        return JSONResponse({"error": "Send a JSON object representing one customer record"}, status_code=400)
    result = validate_customer(record)
    if result["accepted"]:
        from app.scoring import score_customer_rules

        scored = score_customer_rules(result["record"])
        result["scoring_preview"] = {
            "lead_tier": scored["lead_tier"],
            "composite_lead_score": scored["composite_lead_score"],
            "intent_basis": scored["purchase_intent"]["details"].get("data_basis"),
        }
    return result


@app.get("/api/monitoring")
async def api_monitoring():
    return get_monitoring_report()


@app.get("/api/data-quality")
async def api_data_quality():
    return get_data_quality_report()


@app.get("/api/audit")
async def api_audit(event_type: str | None = None, customer_id: str | None = None, limit: int = 100):
    from app.audit import build_audit_report, query

    if event_type or customer_id:
        return {"entries": query(event_type=event_type, customer_id=customer_id, limit=limit)}
    return build_audit_report(limit=limit)


@app.get("/api/audit/export")
async def api_audit_export():
    """Full decision log as CSV for the bank's own retention and review."""
    from app.audit import query

    rows = query(limit=5000)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "audit_id", "at", "event_type", "actor", "customer_id",
        "summary", "lead_tier", "composite_score", "reason_codes",
        "engine_version", "model_version",
    ])
    for r in rows:
        writer.writerow([
            r.get("audit_id"), r.get("at"), r.get("event_type"), r.get("actor"),
            r.get("customer_id", ""), r.get("summary", ""),
            (r.get("outputs") or {}).get("lead_tier", ""),
            (r.get("outputs") or {}).get("composite_lead_score", ""),
            " | ".join(r.get("reason_codes") or []),
            r.get("engine_version"), r.get("model_version"),
        ])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=decision_audit_log.csv"},
    )


@app.post("/api/customer/{customer_id}/simulate")
async def api_customer_simulate(
    customer_id: str,
    debt_to_income_ratio: float = Form(None),
    savings_transfer_ratio: float = Form(None),
    salary_day_spend_ratio: float = Form(None),
    luxury_spend_ratio: float = Form(None),
    application_started: bool = Form(False),
    aa_consent: bool = Form(False),
):
    """
    Live what-if for an RM on a call: change a lever, see the tier move.

    Runs the production rule engine on a copy of the record — the number shown
    is what the scorer would actually output, not an interpolation.
    """
    from app.audit import record as audit_record
    from app.scoring import score_customer_rules

    raw = _find_customer(customer_id)
    if not raw:
        return JSONResponse({"error": "Customer not found"}, status_code=404)

    base = score_customer_rules(raw)
    candidate = dict(raw)
    overrides: dict[str, float | bool] = {}
    for field, value in (
        ("debt_to_income_ratio", debt_to_income_ratio),
        ("savings_transfer_ratio", savings_transfer_ratio),
        ("salary_day_spend_ratio", salary_day_spend_ratio),
        ("luxury_spend_ratio", luxury_spend_ratio),
    ):
        if value is not None:
            clamped = max(0.0, min(1.5 if field == "debt_to_income_ratio" else 1.0, float(value)))
            candidate[field] = clamped
            overrides[field] = clamped
    if application_started:
        candidate["application_started"] = True
        candidate["window_shopping_flag"] = False
        overrides["application_started"] = True
    if aa_consent:
        candidate["has_other_bank_accounts"] = True
        candidate["multi_bank_income_share"] = max(
            float(candidate.get("multi_bank_income_share") or 0), 0.25
        )
        overrides["aa_consent"] = True

    after = score_customer_rules(candidate)
    audit_record(
        "whatif_simulation",
        customer_id=customer_id,
        summary=f"{base['lead_tier']} → {after['lead_tier']}",
        inputs=overrides,
        outputs={"lead_tier": after["lead_tier"], "composite_lead_score": after["composite_lead_score"]},
    )
    return {
        "customer_id": customer_id,
        "overrides": overrides,
        "before": {
            "lead_tier": base["lead_tier"],
            "lead_tier_css": base["lead_tier_css"],
            "composite_lead_score": base["composite_lead_score"],
            "affordable_emi_estimate": base.get("affordable_emi_estimate"),
        },
        "after": {
            "lead_tier": after["lead_tier"],
            "lead_tier_css": after["lead_tier_css"],
            "composite_lead_score": after["composite_lead_score"],
            "affordable_emi_estimate": after.get("affordable_emi_estimate"),
            "repayment": after["repayment_capacity"]["score"],
            "intent": after["purchase_intent"]["score"],
            "discipline": after["behavioral_discipline"]["score"],
        },
        "tier_changed": base["lead_tier"] != after["lead_tier"],
        "score_delta": round(after["composite_lead_score"] - base["composite_lead_score"], 1),
        "disclaimer": "Indicative simulation through the production rule engine. Not an offer.",
    }


@app.get("/usps", response_class=HTMLResponse)
async def usps_page(request: Request):
    from app.usp import build_usp_catalogue

    return templates.TemplateResponse(
        "usps.html",
        {"request": request, "catalogue": build_usp_catalogue(), "active": "usps"},
    )


@app.get("/glossary", response_class=HTMLResponse)
async def glossary_page(request: Request):
    from app.glossary import build_glossary

    return templates.TemplateResponse(
        "glossary.html",
        {"request": request, "glossary": build_glossary(), "active": "glossary"},
    )


@app.get("/api/next-best-action")
async def api_portfolio_actions():
    return get_portfolio_actions()


@app.get("/api/customer/{customer_id}/uplift")
async def api_customer_uplift(customer_id: str):
    report = get_uplift(customer_id)
    if not report:
        return JSONResponse({"error": "Customer not found"}, status_code=404)
    return report


@app.get("/api/customer/{customer_id}/next-best-action")
async def api_customer_nba(customer_id: str):
    from app.next_best_action import build_next_best_actions

    raw = _find_customer(customer_id)
    if not raw:
        return JSONResponse({"error": "Customer not found"}, status_code=404)
    profile = get_scored_profile(customer_id) or score_customer(raw)
    return build_next_best_actions(profile, raw, get_uplift(customer_id))


@app.get("/api/fairness")
async def api_fairness():
    return get_fairness_report()


@app.get("/api/usps")
async def api_usps():
    from app.usp import build_usp_catalogue

    return build_usp_catalogue()


@app.get("/api/glossary")
async def api_glossary():
    from app.glossary import build_glossary

    return build_glossary()


@app.get("/customer/{customer_id}", response_class=HTMLResponse)
async def customer_detail(request: Request, customer_id: str):
    from app.rm_brief import generate_rm_brief
    from app.transaction_timeline import build_transaction_timeline

    raw = _find_customer(customer_id)
    if not raw:
        return RedirectResponse(url="/", status_code=302)

    from app.next_best_action import build_next_best_actions

    profile = get_scored_profile(customer_id) or score_customer(raw)
    timeline = build_transaction_timeline(raw)
    rm_brief = generate_rm_brief(profile)
    uplift = get_uplift(customer_id)
    nba = build_next_best_actions(profile, raw, uplift)

    from app.vernacular import build_vernacular_briefs

    vernacular = build_vernacular_briefs(profile)
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
            "uplift": uplift,
            "nba": nba,
            "vernacular": vernacular,
            "spend_breakdown": spend_breakdown,
            "tier_explanation": _tier_explanation(profile),
            "active": "",
        },
    )


@app.get("/api/customers")
async def api_customers(limit: int = 100, tier: str | None = None):
    ranked = get_ranked_customers()
    if tier:
        ranked = [c for c in ranked if c["lead_tier"] == tier]
    return {"count": len(ranked), "customers": ranked[:limit]}


@app.get("/api/customers/{customer_id}")
async def api_customer_detail(customer_id: str):
    raw = _find_customer(customer_id)
    if not raw:
        return {"error": "Customer not found"}
    return get_scored_profile(customer_id) or score_customer(raw)


@app.get("/api/impact")
async def api_impact():
    return get_impact_metrics()


@app.get("/api/rm-queue")
async def api_rm_queue(limit: int = 20):
    ranked = get_ranked_customers()
    queue = [c for c in ranked if c.get("rm_call_eligible")]
    return {"count": len(queue), "customers": queue[:limit]}


@app.get("/api/rm-queue/export")
async def api_rm_queue_export():
    """CSV export for RM outreach lists."""
    ranked = get_ranked_customers()
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
    ranked = get_ranked_customers()
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
    impact = get_impact_metrics()
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

    from app import audit

    if not _find_customer(customer_id):
        return JSONResponse({"error": "Customer not found"}, status_code=404)
    consent = initiate_aa_consent(customer_id)
    audit.record(
        "aa_consent",
        customer_id=customer_id,
        summary="AA consent requested (DEPOSIT scope, 30 days)",
        outputs={"consent_id": consent.get("consent_id"), "status": consent.get("status")},
    )
    return consent


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
    return generate_rm_brief(get_scored_profile(customer_id) or score_customer(raw))


@app.get("/api/customer/{customer_id}/underwriter-pdf")
async def api_underwriter_pdf(customer_id: str):
    from app.pdf_export import build_underwriter_pdf

    raw = _find_customer(customer_id)
    if not raw:
        return JSONResponse({"error": "Customer not found"}, status_code=404)
    profile = get_scored_profile(customer_id) or score_customer(raw)
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

    profile = get_scored_profile(customer_id) or score_customer(raw)
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
    return get_impact_metrics()


@app.get("/api/health")
async def health():
    from app.ml_model import get_model

    return {
        "status": "ok",
        "track": "02-prospect-assist-ai",
        "version": APP_VERSION,
        "ml_ready": get_model().is_ready,
        "deploy_platform": DEPLOY_PLATFORM,
        "demo_url": PUBLIC_DEMO_URL,
        "cache_warmed": True,
        "capabilities": [
            "lead_uplift_simulator",
            "next_best_action",
            "fairness_audit",
            "outcome_feedback_loop",
            "decision_audit_log",
            "drift_monitoring",
            "data_quality_gates",
            "usp_catalogue",
            "glossary",
        ],
        "public_endpoints": [
            "/api/health",
            "/api/impact",
            "/api/sandbox/{customer_id}",
            "/api/demo-comparison",
            "/api/ml/model-card",
            "/api/fairness",
            "/api/monitoring",
            "/api/data-quality",
            "/api/outcomes",
            "/api/usps",
            "/api/glossary",
        ],
    }
