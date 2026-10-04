#!/usr/bin/env python3
"""Fill the official Hack2skill IDBI Innovate PPT template with Prospect Assist AI content.

Content reflects v0.9.0 (refinement round). Capabilities added since the round-1
submission are marked, because the judges are re-reading a deck they have seen.
"""

from __future__ import annotations

import os
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Pt

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "docs" / "Hack2skill_Template.pptx"
OUTPUT = ROOT / "input" / "IDBI_Prospect_Assist_Submission_FILLED.pptx"

DEMO_URL = os.environ.get(
    "PUBLIC_DEMO_URL",
    "https://idbi-prospect-assist.onrender.com",
)
GITHUB_URL = "https://github.com/ashokbugude/idbi-prospect-assist"
# Set DEMO_VIDEO_URL before running to add the video line; left unset, the line is
# omitted rather than shipping a bracketed "[Add if recorded]" to-do to the judges.
VIDEO_URL = os.environ.get("DEMO_VIDEO_URL", "").strip()

# Content area below slide titles (EMU from template inspection)
BODY_LEFT = 265350
BODY_TOP = 1450000
BODY_WIDTH = 8943000
BODY_HEIGHT = 3500000

# A shape within this many EMU of BODY_TOP is treated as the body box.
BODY_TOP_TOLERANCE = 120000


def _style_paragraphs(tf, lines: list[str], *, font_size: int, bold_first: bool = False,
                      space_after: int | None = None) -> None:
    tf.clear()
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = line
        p.level = 1 if line.startswith(("•", "-")) else 0
        if space_after is not None:
            p.space_after = Pt(space_after)
        for run in p.runs:
            run.font.size = Pt(font_size)
            run.font.name = "Calibri"
            run.font.color.rgb = RGBColor(0x33, 0x33, 0x33)
            if bold_first and i == 0:
                run.font.bold = True


def _set_para_text(shape, lines: list[str], *, font_size: int = 16, bold_first: bool = False) -> None:
    _style_paragraphs(shape.text_frame, lines, font_size=font_size, bold_first=bold_first)


def _body_shape(slide, top: int = BODY_TOP):
    """Return the text box the template already carries at `top`, if there is one.

    The template ships pre-filled, so adding a fresh textbox at the same position
    stacks a second set of text directly over the first — unreadable, and invisible
    to anyone who only checks the generated file's text dump. Reuse the box instead.
    """
    for shape in slide.shapes:
        if shape.has_text_frame and abs(shape.top - top) <= BODY_TOP_TOLERANCE:
            return shape
    return None


def _add_body_box(slide, lines: list[str], *, font_size: int = 15) -> None:
    box = _body_shape(slide)
    if box is None:
        box = slide.shapes.add_textbox(BODY_LEFT, BODY_TOP, BODY_WIDTH, BODY_HEIGHT)
    box.text_frame.word_wrap = True
    _style_paragraphs(box.text_frame, lines, font_size=font_size, space_after=4)


def _find_title_shape(slide):
    for shape in slide.shapes:
        if shape.has_text_frame and shape.top > 500000:
            return shape
    return None


def main() -> int:
    if not TEMPLATE.exists():
        raise SystemExit(f"Template not found: {TEMPLATE}")

    prs = Presentation(str(TEMPLATE))
    slides = prs.slides

    # Slide 1 — Team Details
    _set_para_text(
        slides[0].shapes[1],
        [
            "Team Details",
            "",
            "Team name: Srishti GenAI",
            "Team leader name: Ashok Bugude",
            "Problem Statement: Track 02 — Prospect Assist AI",
            "Stage: shortlisted — refinement round (build v0.9.0)",
            "IDBI converts only ~1% of liability-customer leads; RMs spend their day "
            "on window shoppers.",
        ],
        font_size=14,
        bold_first=True,
    )

    # Slide 2 — Brief about the idea
    _add_body_box(
        slides[1],
        [
            "Prospect Assist AI — behavioral lead intelligence for existing IDBI CASA customers.",
            "",
            "Scores every lead on three AMA dimensions:",
            "• Repayment capacity (transaction-inferred + multi-bank holistic income)",
            "• Purchase intent (digital journeys, window-shopping filter)",
            "• Behavioral discipline (need vs want vs luxury, day-1 salary spend)",
            "",
            "Output: RM-prioritised queue, explainable tiers, costed next best action, "
            "call brief, underwriter PDF.",
            "",
            "New since round 1: the system now measures itself — outcome feedback loop, "
            "live fair-lending audit, drift alarm and data-quality gates.",
            "Production POC v0.9.0 — live demo on Render (free tier).",
        ],
        font_size=14,
    )

    # Slide 3 — Opportunities / USP
    opp = _find_title_shape(slides[2])
    if opp:
        _set_para_text(
            opp,
            [
                "Opportunities",
                "Differentiation: 3-dimension scoring + lead tiers, not spray-and-pray RM calls",
            ],
            font_size=15,
            bold_first=True,
        )
    _add_body_box(
        slides[2],
        [
            "How it solves the problem:",
            "• Filters window shoppers (30% of the book) before the RM dials",
            "• Surfaces Quality and Serious leads with affordable EMI and product match",
            "• RM queue is 23% of leads, converting at 25% simulated against a 1% baseline",
            "• Quality segment conversion simulation: 41.2% against the 32% Track 02 target",
            "• Next best action costed in rupees per RM minute, packed to branch capacity",
            "• Every tier decision explainable and logged — no black-box auto-decision",
            "",
            "43 differentiators catalogued, 21 of them added since round 1, each linked to "
            "live evidence in the running build.",
        ],
        font_size=14,
    )

    # Slide 4 — Features
    _add_body_box(
        slides[3],
        [
            "Round-1 foundation:",
            "• RM dashboard: tier filters, pagination, Before/After conversion toggle",
            "• Lead tiers: Quality → Serious → Interested → Window-shop Risk",
            "• 5 product scorers, income inference, 30-day transaction timeline",
            "• Account Aggregator flow: consent → fetch → holistic income re-score",
            "• Underwriter PDF and RM CSV export, tier-aware call brief",
            "",
            "New since round 1 — 21 capabilities:",
            "• Next Best Action, costed per RM minute and packed to branch capacity",
            "• Lead Uplift Simulator — real counterfactual re-scores, not feature importance",
            "• What-if levers the RM can move while the customer is on the call",
            "• Call scripts in Hindi, Marathi and Tamil",
            "• Outcome feedback loop — logged dispositions calibrate the assumed rates",
            "• Governance pack: fair-lending audit, decision audit log, drift alarm, data-quality gates",
            "• Differentiators catalogue and a glossary tested against the codebase",
        ],
        font_size=12,
    )

    # Slide 5 — Process flow
    _add_body_box(
        slides[4],
        [
            "Lead ingestion → typed ingest gate (coerce, validate, clamp, reject)",
            "       ↓",
            "Enrichment: income inference, bureau, UPI/geo, delinquency, multi-bank AA",
            "       ↓",
            "Rule engine → 3 dimensions + 5 product EMI gates → lead tier",
            "       ↓",
            "XGBoost hybrid — ±8 pt bounded nudge, never demotes a Quality Lead",
            "       ↓",
            "RM queue → next best action → call brief → underwriter PDF",
            "       ↓",
            "Outcome logged → calibration against assumed rates → retrain readiness",
            "       └──────────→ feeds back into the tier assumptions  [new]",
            "",
            "Every decision writes an audit record: engine version, model version, reasons.",
        ],
        font_size=13,
    )

    # Slide 6 — Wireframes / key pages
    _add_body_box(
        slides[5],
        [
            f"Key UI pages — live at {DEMO_URL}, demo PIN idbi2026:",
            "• /  — priority queue, Before/After toggle",
            "• /actions — costed next best actions packed into RM capacity  [new]",
            "• /outcomes — disposition logging, calibration, retrain readiness  [new]",
            "• /governance — fairness, model risk and data quality, three tabs  [new]",
            "• /differentiators — 43 capabilities, each linked to live evidence  [new]",
            "• /glossary — 153 terms, tested against the codebase  [new]",
            "• /multi-bank — AA consent flow (hero: IDBI-L10055 tier uplift)",
            "• /impact — business impact simulation and 4-week pilot plan",
            "• /ml — model card, R², confusion matrix, honest ML disclaimer",
            "• /architecture — AWS target diagram and DPDP compliance",
            "• /customer/IDBI-L10010 — Quality Lead: brief, timeline, uplift, what-if",
            "• /customer/IDBI-L10121 — window shopper: deprioritisation, no RM call",
        ],
        font_size=12,
    )

    # Slide 7 — Architecture
    _add_body_box(
        slides[6],
        [
            "Current POC (refinement round):",
            "  FastAPI + Jinja2 UI → typed ingest gate → rule engine → XGBoost nudge",
            "  Append-only JSONL stores: outcome log and decision audit log  [new]",
            "  Deployed: Render (Docker, free tier), auto-deploy from main",
            "",
            "Target production (post-shortlist):",
            "  API Gateway → ECS/Fargate scoring service",
            "  → RDS (customer profiles) + S3 (transaction batches)",
            "  → SageMaker endpoint (ML nudge) + CloudWatch",
            "  → audit and outcome stores on RDS, PSI drift job on a schedule",
            "  IDBI sandbox banking APIs replace the synthetic customer feed",
        ],
        font_size=13,
    )

    # Slide 8 — Technologies
    _add_body_box(
        slides[7],
        [
            "Backend: Python 3.12, FastAPI, Uvicorn, Pydantic",
            "ML: XGBoost, scikit-learn, 35-feature vector",
            "Governance: four-fifths disparate-impact test, PSI drift bands (0.10 / 0.25)  [new]",
            "UI: Jinja2 templates, vanilla JS, content-fingerprinted static assets",
            "PDF: fpdf2 underwriter packet export",
            "Data: synthetic IDBI liability customers (seed=42, n=200)",
            "Auth: RM PIN session cookie; judge-facing APIs deliberately need no login",
            "Deploy: Docker, Render free tier, render.yaml blueprint",
            "Testing: pytest — 89 tests (7 ML, 21 scoring, 26 round-1, 35 round-2)",
            "GenAI: optional OpenAI API; deterministic template fallback by design, so the "
            "demo never depends on an external key",
        ],
        font_size=13,
    )

    # Slide 9 — Cost (optional)
    _add_body_box(
        slides[8],
        [
            "POC / hackathon phase:",
            "• Render free tier — demo hosting $0 (750 hrs/month)",
            "• No paid third-party APIs required (GenAI template fallback)",
            "",
            "Pilot estimate (4-week RM A/B, post-shortlist):",
            "• AWS sandbox: ECS + RDS micro + API Gateway ≈ $200–400/month",
            "• RM time saved: ~40% of effort currently spent on low-intent leads",
            "• Scale path: serverless scoring handles 10K leads/month at <2s p95",
        ],
        font_size=13,
    )

    # Slide 10 — Snapshots
    # Budget: six lines at 12pt. The body box is 2.11in tall but the template's two
    # screenshots start at 3.25in, so anything past ~1.6in of text renders behind them.
    _add_body_box(
        slides[9],
        [
            "Live prototype — open the demo URL and sign in with PIN idbi2026:",
            f"• Dashboard: {DEMO_URL}/",
            f"• Next best actions: {DEMO_URL}/actions",
            f"• Governance pack: {DEMO_URL}/governance",
            f"• Outcome loop: {DEMO_URL}/outcomes",
            "• No login required: /api/health · /api/impact · /api/fairness · /api/monitoring",
        ],
        font_size=12,
    )

    # Slide 11 — Performance
    _add_body_box(
        slides[10],
        [
            "Benchmark (scripts/benchmark.py, laptop-class CPU):",
            "• Single customer score p95: ~21 ms (n=50)",
            "• Rank 200 customers, mean: ~1,165 ms",
            "• Headroom for 10K leads/month at <2s p95 per score",
            "",
            "Quality gates:",
            "• 89 / 89 pytest tests passing",
            "• Tier mix (n=200): Quality 16 · Serious 30 · Interested 95 · Window-shop 59",
            "• Quality segment conversion (sim): 41.2% vs 32% target | RM queue: 25.0%",
            "• Degradation test: each of 5 source groups removed in turn, 0 scorer crashes  [new]",
            "• /api/health reports version 0.9.0, ml_ready true, 9 capabilities",
        ],
        font_size=12,
    )

    # Slide 12 — Future development
    _add_body_box(
        slides[11],
        [
            "Post-shortlist roadmap:",
            "• Integrate IDBI AWS sandbox APIs, replacing the synthetic feed",
            "• 4-week RM A/B pilot: Quality cohort vs control (KPI ≥32% conversion)",
            "• Retrain on logged outcomes once 150 labelled dispositions accumulate",
            "• Live Account Aggregator consent with real FIP connectors",
            "• Native-speaker sign-off on the Hindi, Marathi and Tamil call scripts",
            "• Bank-approved LLM for brief generation, replacing the template fallback",
            "",
            "Compliance: AI assists — the underwriter decides. No automated credit decision.",
        ],
        font_size=13,
    )

    # Slide 13 — Links
    links = _find_title_shape(slides[12])
    if links:
        link_lines = [
            "Provide links to your:",
            "",
            f"GitHub Public Repository: {GITHUB_URL}",
        ]
        if VIDEO_URL:
            link_lines.append(f"Demo Video Link (3 Minutes): {VIDEO_URL}")
        link_lines += [
            f"Final Product Link: {DEMO_URL}",
            "",
            "Login PIN: idbi2026",
            f"Public API, no login: {DEMO_URL}/api/sandbox/IDBI-L10010",
        ]
        _set_para_text(links, link_lines, font_size=15, bold_first=True)

    # Slide 14 — Thank you
    THANK_TOP = 2200000
    thank = _body_shape(slides[13], top=THANK_TOP)
    if thank is None:
        thank = slides[13].shapes.add_textbox(BODY_LEFT, THANK_TOP, BODY_WIDTH, 1200000)
    _set_para_text(
        thank,
        [
            "Thank you",
            "",
            "Srishti GenAI — ready for the IDBI AWS sandbox pilot",
        ],
        font_size=28,
        bold_first=True,
    )
    for p in thank.text_frame.paragraphs:
        p.alignment = PP_ALIGN.CENTER

    # Slide 15 — Title
    slides[14].placeholders[0].text = "Prospect Assist AI"
    slides[14].placeholders[1].text = (
        "IDBI Innovate 2026 · Track 02: Prospect Assist AI\n"
        "Team: Srishti GenAI | Leader: Ashok Bugude"
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(OUTPUT))
    print(f"Saved: {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
