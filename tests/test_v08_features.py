"""Tests for v0.8.0 — uplift simulator, next best action, fairness audit, glossary, USPs."""

from __future__ import annotations

import pathlib
import re

import pytest

from app.data_generator import generate_dataset
from app.scoring import LEAD_TIERS, rank_customers, score_customer_rules


# --------------------------------------------------------------------------- #
# Lead Uplift Simulator
# --------------------------------------------------------------------------- #
def test_uplift_report_shape(quality_customer):
    from app.uplift import simulate_uplift

    report = simulate_uplift(quality_customer)
    assert report["current_tier"] in LEAD_TIERS
    assert report["levers"], "at least one lever should apply to a realistic profile"
    for lever in report["levers"]:
        assert lever["tier_after"] in LEAD_TIERS
        assert -100 <= lever["delta_points"] <= 100
        assert lever["owner"] in ("RM", "Customer", "RM + Customer")


def test_uplift_deltas_are_real_rescores():
    """A lever's reported delta must equal an independent re-score of the mutated record."""
    from app.uplift import LEVERS_BY_CODE, simulate_uplift

    customer = next(
        c for c in generate_dataset(200, seed=42) if c["customer_id"] == "IDBI-L10055"
    )
    base = score_customer_rules(customer)
    report = simulate_uplift(customer, base)

    for lever_result in report["levers"][:4]:
        mutated = dict(customer)
        LEVERS_BY_CODE[lever_result["code"]].apply(mutated)
        expected = score_customer_rules(mutated)["composite_lead_score"]
        assert lever_result["score_after"] == expected
        assert lever_result["delta_points"] == pytest.approx(
            expected - base["composite_lead_score"], abs=0.05
        )


def test_uplift_is_deterministic(quality_customer):
    from app.uplift import simulate_uplift

    a = simulate_uplift(quality_customer)
    b = simulate_uplift(quality_customer)
    assert [l["code"] for l in a["levers"]] == [l["code"] for l in b["levers"]]
    assert a["recommended_path"]["score_after"] == b["recommended_path"]["score_after"]


def test_uplift_never_mutates_the_source_record(quality_customer):
    from app.uplift import simulate_uplift

    before = dict(quality_customer)
    simulate_uplift(quality_customer)
    assert quality_customer == before


def test_uplift_top_tier_has_no_next_tier(quality_customer):
    from app.uplift import simulate_uplift

    quality_customer["application_started"] = True
    report = simulate_uplift(quality_customer)
    if report["current_tier"] == "Quality Lead":
        assert report["next_tier"] is None
        assert report["at_top_tier"] is True


def test_stress_test_present_and_bounded(window_shopper):
    from app.uplift import simulate_uplift

    stress = simulate_uplift(window_shopper)["stress_test"]
    assert stress["resilience"] in ("Resilient", "Fragile")
    assert 0 <= stress["score_after"] <= 100
    assert stress["tier_after"] in LEAD_TIERS


# --------------------------------------------------------------------------- #
# Next Best Action
# --------------------------------------------------------------------------- #
def test_nba_ranks_and_costs_actions(quality_customer):
    from app.next_best_action import build_next_best_actions

    profile = score_customer_rules(quality_customer)
    nba = build_next_best_actions(profile, quality_customer)
    assert nba["next_best_action"] is not None
    priorities = [a["priority"] for a in nba["actions"]]
    assert priorities == sorted(priorities, reverse=True)
    for a in nba["actions"]:
        assert a["effort_minutes"] >= 0
        assert a["expected_value_inr"] >= 0
        assert a["script"]
        assert a["compliance_note"]


def test_window_shopper_is_never_told_to_call():
    """The core promise: a window shopper must not produce an outbound sales action."""
    from app.next_best_action import build_next_best_actions

    data = generate_dataset(200, seed=42)
    checked = 0
    for raw in data:
        profile = score_customer_rules(raw)
        if profile["lead_tier"] != "Window-shop Risk":
            continue
        checked += 1
        nba = build_next_best_actions(profile, raw)
        assert nba["next_best_action"]["code"] == "suppress_outbound"
        assert nba["next_best_action"]["rm_minutes_saved"] > 0
        assert not any(a["channel"] == "RM call" for a in nba["actions"])
    assert checked > 0, "dataset should contain window shoppers"


def test_nba_uses_real_rescore_when_uplift_supplied():
    from app.next_best_action import build_next_best_actions
    from app.uplift import simulate_uplift

    data = generate_dataset(200, seed=42)
    for raw in data:
        profile = score_customer_rules(raw)
        if profile["lead_tier"] == "Window-shop Risk" or raw.get("has_other_bank_accounts"):
            continue
        uplift = simulate_uplift(raw, profile)
        aa = next((l for l in uplift["levers"] if l["code"] == "aa_consent"), None)
        if not (aa and aa["tier_moves"]):
            continue
        nba = build_next_best_actions(profile, raw, uplift)
        action = next(a for a in nba["actions"] if a["code"] == "aa_consent_request")
        # A grounded delta is labelled as measured; an assumed one is not.
        assert "measured re-score" in action["evidence"], action["evidence"]
        assert action["expected_conversion_delta_pp"] > 0
        return
    pytest.skip("no AA-moving lead in this dataset slice")


def test_portfolio_plan_respects_capacity():
    from app.next_best_action import build_portfolio_actions

    data = generate_dataset(200, seed=42)
    ranked = rank_customers(data)
    plan = build_portfolio_actions(ranked, {c["customer_id"]: c for c in data}, rm_count=6)
    cp = plan["capacity_plan"]
    assert cp["minutes_scheduled"] <= cp["total_minutes_available"]
    assert cp["actions_scheduled"] == len(plan["today_queue"]) or cp["actions_scheduled"] >= len(plan["today_queue"])
    assert plan["rm_minutes_saved_by_suppression"] > 0
    assert plan["playbook"]


def test_sla_commitments_are_scheduled_first():
    from app.next_best_action import build_portfolio_actions

    data = generate_dataset(200, seed=42)
    ranked = rank_customers(data)
    plan = build_portfolio_actions(ranked, {c["customer_id"]: c for c in data})
    queue = plan["today_queue"]
    committed = [i for i, item in enumerate(queue) if (item["action"]["sla_hours"] or 999) <= 24]
    discretionary = [i for i, item in enumerate(queue) if (item["action"]["sla_hours"] or 999) > 24]
    if committed and discretionary:
        assert max(committed) < min(discretionary)


# --------------------------------------------------------------------------- #
# Fairness audit
# --------------------------------------------------------------------------- #
def test_no_prohibited_attribute_reaches_the_model():
    from app.fairness import audit_prohibited_attributes

    audit = audit_prohibited_attributes(generate_dataset(50, seed=42))
    assert audit["passed"] is True
    assert audit["prohibited_features_found"] == []


def test_customer_name_is_not_a_model_feature():
    """Surname is a caste/community proxy in the Indian context — it must stay out."""
    from app.features import FEATURE_NAMES

    assert not any("name" in f.lower() for f in FEATURE_NAMES)


def test_fairness_report_scores_every_dimension():
    from app.fairness import build_fairness_report

    data = generate_dataset(200, seed=42)
    report = build_fairness_report(data, rank_customers(data))
    assert report["population"] == 200
    assert len(report["segments"]) == 4
    for seg in report["segments"]:
        assert seg["status"] in ("pass", "watch", "review")
        assert seg["groups"]
        for g in seg["groups"]:
            if g["disparate_impact_ratio"] is not None:
                assert 0 <= g["disparate_impact_ratio"] <= 1.0
            else:
                assert g["n"] < 15
    assert report["explainability"]["all_three_dimensions_explained_pct"] == 100.0
    assert report["explainability"]["deprioritised_with_reason_pct"] == 100.0


def test_flagged_dimensions_carry_a_mitigation_simulation():
    from app.fairness import build_fairness_report

    data = generate_dataset(200, seed=42)
    report = build_fairness_report(data, rank_customers(data))
    flagged = {s["dimension"] for s in report["segments"] if s["status"] != "pass"}
    simulated = {m["dimension"] for m in report["mitigation_simulations"]}
    assert flagged == simulated
    for seg in report["segments"]:
        if seg["status"] != "pass":
            assert seg["business_necessity"], f"{seg['dimension']} needs a stated justification"
            assert seg["mitigation_actions"]


# --------------------------------------------------------------------------- #
# Glossary — kept honest against the codebase
# --------------------------------------------------------------------------- #
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SKIP_DIRS = {".venv", ".git", "__pycache__", ".pytest_cache", "node_modules", "models"}
SOURCE_SUFFIXES = {".py", ".md", ".html", ".css", ".js", ".yaml", ".yml"}

# Tokens that are code identifiers, constants or fragments — not domain vocabulary.
NOT_VOCABULARY = {
    "ROOT", "LMARGIN", "NEXT", "OUTPUT", "LEVERS", "SCORERS", "CITIES", "DEPOSIT",
    "SUCCESS", "YYYY", "MM", "DD", "EMU", "DOCTYPE", "UTF", "NOT", "IN", "ID",
    "CENTER", "FPDF", "HF", "PY", "CSS", "HTML", "JS", "GET", "POST", "PILLARS",
    "TERMS", "USPS", "CATEGORIES", "SEGMENTS", "PROXY", "DATA", "BAND", "TIER",
    "PRODUCTS", "PRODUCT", "MAX", "MIN", "TARGET", "BASELINE", "AUTH", "APP", "RM",
    "DISABLE", "TOKEN", "HERO", "SELF", "METRO", "STRESS", "CHANNEL", "ACTION",
    "DEFAULT", "INTEREST", "SUPPRESSED", "PLAYBOOK", "FOUR", "WATCH", "BUSINESS",
    "MITIGATION", "PROHIBITED", "FEATURE", "CREDIT", "EMPLOYMENT", "TIMELINE",
    "FIRST", "LAST", "EMPLOYMENT", "ARCHETYPE", "AVG", "LEAD", "CONVERSION",
    "PASS", "FAIL", "README", "US", "WEIGHTS", "LABELS", "NAMES", "ORDINAL",
    "INDEX", "ORDER", "SKIP", "NOT", "TENOR", "MINUTES", "COUNT", "PRODUCTIVE",
    "RELATIVE", "LIFT", "FIFTHS", "THRESHOLD", "INVENTORY", "REGISTER", "CALL",
    "NECESSITY", "ACTIONS", "SCENARIO", "PATH", "STEPS", "DIRS", "SUFFIXES",
    "SOURCE", "REPO", "REGISTRY", "VOCABULARY", "ATTRIBUTES", "TOKENS", "CITIES",
    "BINS", "STABLE", "MODERATE", "UNKNOWN", "FOR", "NOTE", "REVIEW", "TERMS",
    "RULES", "GROUPS", "CRITICAL", "MONITORED", "LANGUAGES", "PRODUCT", "TIER",
    "DISPOSITIONS", "CONVERTING", "CONTACTED", "RETRAIN", "EVENT", "TYPES",
    "MAX", "MIN", "AUDIT", "LOG", "DIR", "PATH", "DATA", "SAMPLE", "THRESHOLD",
    "DISCLAIMERS", "BUILDERS", "INDEX", "FIELD", "RANGE", "FIELDS",
}


def _repo_capitalised_tokens() -> set[str]:
    tokens: set[str] = set()
    for path in REPO_ROOT.rglob("*"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if not path.is_file() or path.suffix.lower() not in SOURCE_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for token in re.findall(r"\b[A-Z][A-Z0-9]{1,6}\b", text):
            tokens.add(token)
    return tokens


def test_glossary_defines_every_abbreviation_used_in_the_repo():
    from app.glossary import build_glossary

    glossary = build_glossary()
    defined = set()
    for entry in glossary["entries"]:
        for part in re.split(r"[\s/()·,]+", f"{entry['term']} {entry['expansion']}"):
            if part:
                defined.add(part.upper().strip("."))

    used = _repo_capitalised_tokens()
    missing = {
        t for t in used
        if t not in defined
        and t not in NOT_VOCABULARY
        and not re.match(r"^L\d+$", t)          # customer ids
        and not re.match(r"^[A-Z]\d", t)        # hex/codes like E402, X1, F58220
        and "_" not in t
    }
    assert not missing, (
        "Terms used in the repository but missing from app/glossary.py: "
        + ", ".join(sorted(missing))
    )


def test_glossary_entries_are_complete_and_categorised():
    from app.glossary import CATEGORIES, build_glossary

    glossary = build_glossary()
    assert glossary["count"] >= 120
    seen: set[str] = set()
    for e in glossary["entries"]:
        assert e["category"] in CATEGORIES
        assert len(e["definition"]) > 40, f"{e['term']} needs a real definition"
        assert e["where"], f"{e['term']} must say where it is used"
        assert e["term"] not in seen, f"duplicate glossary term: {e['term']}"
        seen.add(e["term"])


# --------------------------------------------------------------------------- #
# USP catalogue
# --------------------------------------------------------------------------- #
def test_every_usp_links_to_a_real_route():
    from app.main import app
    from app.usp import build_usp_catalogue

    routes = {getattr(r, "path", "") for r in app.routes}
    catalogue = build_usp_catalogue()
    assert catalogue["count"] >= 30
    for usp in catalogue["entries"]:
        url = usp["evidence_url"]
        normalised = re.sub(r"IDBI-L\d+", "{customer_id}", url)
        assert normalised in routes, f"USP '{usp['id']}' points at a non-existent route: {url}"
        assert usp["claim"] and usp["why_idbi"] and usp["typical_entry"]


def test_usp_ids_are_unique():
    from app.usp import build_usp_catalogue

    ids = [u["id"] for u in build_usp_catalogue()["entries"]]
    assert len(ids) == len(set(ids))


# --------------------------------------------------------------------------- #
# Pre-login surface — the RM navigation must not leak before authentication
# --------------------------------------------------------------------------- #
@pytest.fixture
def anon_client():
    """TestClient with RM auth enforced, regardless of the conftest env default."""
    import app.auth as auth_module
    from fastapi.testclient import TestClient

    from app.main import app as fastapi_app

    previous = auth_module.DISABLE_AUTH
    auth_module.DISABLE_AUTH = False
    try:
        with TestClient(fastapi_app) as client:
            yield client
    finally:
        auth_module.DISABLE_AUTH = previous


def test_login_page_exposes_no_rm_navigation(anon_client):
    html = anon_client.get("/login").text
    assert 'class="idbi-nav"' not in html
    assert "idbi-nav-locked" in html
    for label in (
        ">Dashboard<", ">Actions<", ">Outcomes<", ">Multi-bank<", ">Impact<",
        ">Governance<", ">Model<", ">Architecture<", ">USPs<", ">Glossary<",
        "Export CSV", "nav-logout", "rm-role-badge",
    ):
        assert label not in html, f"login page leaks RM navigation item: {label}"


def test_login_page_brand_is_not_a_link_to_the_dashboard(anon_client):
    html = anon_client.get("/login").text
    assert 'class="idbi-brand is-static"' in html
    assert '<a class="idbi-brand"' not in html


def test_failed_login_still_exposes_no_navigation(anon_client):
    html = anon_client.get("/login?error=1").text
    assert "Invalid PIN" in html
    assert 'class="idbi-nav"' not in html


def test_stale_or_forged_cookie_does_not_reveal_navigation(anon_client):
    """Cookie *presence* must not be enough — the token has to match."""
    anon_client.cookies.set("prospect_rm_session", "not-a-real-token")
    response = anon_client.get("/login")
    assert 'class="idbi-nav"' not in response.text
    assert anon_client.get("/actions", follow_redirects=False).status_code == 302


def test_navigation_returns_after_a_valid_login(anon_client):
    from app.config import RM_DEMO_PIN

    anon_client.post("/login", data={"pin": RM_DEMO_PIN}, follow_redirects=False)
    html = anon_client.get("/").text
    assert 'class="idbi-nav"' in html
    assert "idbi-nav-locked" not in html
    for label in (
        ">Dashboard<", ">Actions<", ">Outcomes<", ">Multi-bank<", ">Impact<",
        ">Governance<", ">Model<", ">Architecture<", ">USPs<", ">Glossary<",
        "Export CSV",
    ):
        assert label in html


def test_navigation_is_a_single_flat_row(anon_client):
    """
    Every destination must be visible in one row — no dropdown, no second line.
    A collapsed menu hides half the product from a judge who never hovers.
    """
    from app.config import RM_DEMO_PIN

    anon_client.post("/login", data={"pin": RM_DEMO_PIN}, follow_redirects=False)
    html = anon_client.get("/").text
    nav = html.split('<nav class="idbi-nav">', 1)[1].split("</nav>", 1)[0]

    assert "<button" not in nav, "nav must contain links only — no dropdown toggle"
    assert "nav-group" not in nav, "the collapsible nav group must not come back"

    hrefs = re.findall(r'href="([^"]+)"', nav)
    assert hrefs == [
        # daily work
        "/", "/actions", "/outcomes", "/multi-bank",
        # the evidence
        "/impact", "/governance", "/ml", "/architecture",
        # reference
        "/usps", "/glossary",
        # actions
        "/api/rm-queue/export", "/logout",
    ]


def test_stylesheet_keeps_the_nav_on_one_line():
    css = (REPO_ROOT / "app" / "static" / "style.css").read_text(encoding="utf-8")
    nav_rules = [
        block for block in re.findall(r"\.idbi-nav\s*\{([^}]*)\}", css)
    ]
    assert any("nowrap" in b for b in nav_rules), ".idbi-nav must set flex-wrap: nowrap"
    assert any("overflow-x" in b for b in nav_rules), (
        ".idbi-nav must scroll rather than wrap when the window is narrow"
    )
    inner = re.findall(r"\.idbi-header-inner\s*\{([^}]*)\}", css)
    assert any("nowrap" in b for b in inner), ".idbi-header-inner must not wrap the nav below the brand"
