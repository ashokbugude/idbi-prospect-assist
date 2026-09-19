"""
USP catalogue — what this build does that a typical Track 02 entry does not.

Each entry names the capability, the reason it matters to IDBI specifically, the
place in the running product where a judge can verify it in one click, and —
deliberately — what the common alternative approach looks like. Claims without a
verifiable link do not belong in this file.
"""

from __future__ import annotations

PILLARS = [
    ("Signal depth", "Reading the customer, not the form they filled in"),
    ("Decisioning", "Turning a score into a decision an RM can act on"),
    ("RM productivity", "Protecting the scarcest resource in the branch"),
    ("Trust & governance", "Surviving a compliance review, not just a demo"),
    ("Engineering credibility", "Evidence that this is a system, not a slide"),
]

# (id, pillar, title, claim, why_idbi, evidence_label, evidence_url, typical_entry, is_new)
USPS: list[tuple[str, str, str, str, str, str, str, str, bool]] = [
    # ---------------- Signal depth ----------------
    ("txn-income", "Signal depth",
     "Income inferred from cashflow, not declared on a form",
     "Credit inflows, balance turnover and savings behaviour are reconciled into an inferred income "
     "with an explicit 0–1 confidence. Below 0.55 confidence the engine refuses its own inference and "
     "falls back to stated income.",
     "The AMA asked for repayment capacity beyond the salary slip. A confidence score is what makes "
     "that inference safe to put in front of an underwriter.",
     "Customer detail → Income Inference", "/customer/IDBI-L10010",
     "Uses the declared salary field as-is.", False),

    ("self-employed", "Signal depth",
     "Self-employed and gig income modelled on industry margins",
     "Business inflows are converted to net income using per-industry margin assumptions "
     "(professional 62%, services 48%, retail trade 32%, manufacturing 28%, gig 55%) rather than "
     "treating turnover as income.",
     "A large share of IDBI's liability base is not salaried. Treating a trader's turnover as income "
     "is the fastest route to a bad book.",
     "Customer detail → Income Inference", "/customer/IDBI-L10010",
     "Scores everyone on a single salaried assumption.", False),

    ("multi-bank", "Signal depth",
     "Account Aggregator multi-bank income uplift",
     "Simulated AA consent → FIP fetch → holistic income → live re-score, with the tier movement shown "
     "before and after on screen.",
     "IDBI sees one slice of a customer's money. The income that makes a lead bankable is frequently "
     "sitting at another bank.",
     "Multi-bank AA flow (hero: IDBI-L10055)", "/multi-bank",
     "Mentions Account Aggregator on an architecture slide.", False),

    ("upi-mix", "Signal depth",
     "UPI merchant-category mix as a discipline signal",
     "Food, mobility, retail, entertainment and utilities shares produce a merchant-diversity score and "
     "a discipline hint — without storing a single merchant name.",
     "The AMA explicitly asked what and where the customer spends. Doing it on five neutral aggregates "
     "keeps the signal and drops the privacy exposure.",
     "Customer detail → UPI Merchant Behaviour", "/customer/IDBI-L10010",
     "Counts transactions and stops there.", False),

    ("need-want-luxury", "Signal depth",
     "Need vs want vs luxury segmentation of spend",
     "Every customer's outflow is split three ways and charted, then fed into both the discipline score "
     "and the delinquency model.",
     "Directly requested in the orientation. It is also the most intuitive panel to show an RM who has "
     "never trusted a model before.",
     "Customer detail → spend chart", "/customer/IDBI-L10010",
     "Reports a single 'discretionary spend' percentage.", False),

    ("day1-spend", "Signal depth",
     "Day-1 salary depletion as a leading delinquency indicator",
     "Share of salary spent within 48 hours of credit drives both behavioural discipline and the "
     "forward-looking delinquency score.",
     "It is observable today, on existing CASA data, for every salaried customer — no new data "
     "collection required to start.",
     "Day-1 spend → delinquency model", "/customer/IDBI-L10010",
     "Waits for a bureau delinquency flag, which arrives after the damage.", False),

    ("delinquency-4th", "Signal depth",
     "Delinquency safety as a fourth scoring pillar",
     "A 12-month forward stress score carries 17% of the composite and can cap a tier outright, "
     "independent of how attractive the lead looks on intent.",
     "A high-intent, high-capacity lead with a fragile spending pattern is exactly the loan a bank "
     "regrets. Propensity-only scoring cannot see it.",
     "Customer detail → Delinquency Risk", "/customer/IDBI-L10121",
     "Optimises for conversion probability alone.", False),

    # ---------------- Decisioning ----------------
    ("window-shop", "Decisioning",
     "Window shoppers are actively scored down, not merely ranked lower",
     "High browsing with no calculator use and no application triggers a hard tier override — the lead "
     "cannot rise above Window-shop Risk regardless of income.",
     "This is the stated IDBI pain. A ranked list still leaves a wealthy window shopper near the top; "
     "an override removes them from the call sheet.",
     "Dashboard → Window-shop tier (hero: IDBI-L10121)", "/customer/IDBI-L10121",
     "Sorts by propensity and hopes the ranking handles it.", False),

    ("uplift-sim", "Decisioning",
     "Lead Uplift Simulator — a real counterfactual, not a feature-importance chart",
     "Eleven executable levers are each applied to a copy of the customer record and re-scored through "
     "the identical production rule engine. The page shows the true point movement, the resulting tier, "
     "the EMI headroom unlocked and the smallest combination that clears the next tier gate.",
     "It converts the 77% of the book that is not callable today into a worklist. No other entry will "
     "be able to tell an RM what to *do* about an Interested lead.",
     "Customer detail → Uplift Simulator", "/customer/IDBI-L10055",
     "Shows SHAP values an RM cannot act on.", True),

    ("stress-test", "Decisioning",
     "Per-lead stress test and tier resilience",
     "Every lead is re-scored under an adverse six-month scenario. A tier that survives is marked "
     "Resilient; one that collapses is marked Fragile with a conservative sizing instruction.",
     "It tells an underwriter whether a Quality Lead is quality because of durable behaviour or because "
     "of a good month.",
     "Customer detail → Stress test", "/customer/IDBI-L10010",
     "Reports a single point-in-time score.", True),

    ("nba", "Decisioning",
     "Next Best Action costed in rupees per RM minute",
     "Each lead's actions carry a channel, SLA, script, RM-minute cost, expected conversion delta and "
     "expected rupee value — ranked by expected disbursal per RM minute.",
     "Branch capacity is budgeted in minutes. A recommendation that does not price the minute cannot be "
     "prioritised against the other forty things an RM was asked to do today.",
     "Actions → per-lead queue", "/actions",
     "Outputs 'call this lead' with no cost or expected value.", True),

    ("grounded-delta", "Decisioning",
     "Action value grounded in a re-score, not an assumed lift",
     "Where an action maps to an uplift lever — AA consent, application assist, obligation relief — the "
     "conversion delta comes from the simulated tier movement. Assumption-based deltas are labelled as "
     "assumptions.",
     "It lets IDBI see precisely which numbers are engine output and which are POC assumptions awaiting "
     "pilot calibration.",
     "Actions → method note", "/actions",
     "Applies one flat uplift percentage to everything.", True),

    ("product-emi-gate", "Decisioning",
     "Five products, each gated on affordable EMI",
     "Home, mortgage, auto, personal and consumer durable are scored independently and each is gated on "
     "whether affordable EMI clears that product's floor.",
     "It stops the system recommending a home loan to a customer with ₹4,000 of monthly headroom — the "
     "credibility failure that ends a demo.",
     "Customer detail → Product Match", "/customer/IDBI-L10010",
     "Recommends one generic 'loan'.", False),

    ("outcome-loop", "Decisioning",
     "The system finds out whether it was right",
     "Every RM call disposition is captured against the lead and the action that was recommended, in an "
     "append-only store. Conversion denominators count contacted leads only, so an unreachable customer "
     "is not scored as a failed pitch.",
     "Round 1 scored leads and never learned. This is the difference between a model and a system — and "
     "it is the table the 4-week A/B pilot needs, ready on day one instead of built during week one.",
     "Outcomes → log a disposition", "/outcomes",
     "Ships a scorer and assumes the pilot will build the feedback plumbing later.", True),

    ("calibration", "Engineering credibility",
     "Assumptions promoted to measurements, in public",
     "Each tier's assumed conversion rate is shown beside the rate RMs actually observed, with the gap in "
     "percentage points and a status of unvalidated, emerging, validated or diverging.",
     "Every entrant's impact numbers are assumptions. This one publishes a scoreboard of which ones have "
     "survived contact with reality — and flags the ones that have not.",
     "Outcomes → calibration table", "/outcomes",
     "Presents a conversion figure with no mechanism to ever check it.", True),

    ("breaks-circularity", "Engineering credibility",
     "An honest account of why the ML does nothing today",
     "The classifier is trained on the rule engine's own labels, so it agrees with its teacher by "
     "construction and moves zero tiers across 200 leads. The product says so on screen, and the outcome "
     "loop supplies the labels that fix it.",
     "A panel that finds this themselves will discount everything else on the slide. Naming it first, with "
     "the remedy already built, converts the weakest part of the story into evidence of rigour.",
     "Outcomes → why this changes the model", "/outcomes",
     "Reports 94% tier accuracy without mentioning what the labels were.", True),

    # ---------------- RM productivity ----------------
    ("branch-day-plan", "RM productivity",
     "A whole branch day packed into finite RM capacity",
     "Every lead's top action is packed into a real capacity envelope (6 RMs × 360 productive minutes). "
     "24-hour SLA commitments are scheduled first, the remainder by value density, and the page reports "
     "utilisation, deferred work and the share of pipeline value captured.",
     "This is the artefact a branch manager can run the morning huddle from — the step between a model "
     "and an operating rhythm.",
     "Actions → today's capacity plan", "/actions",
     "Exports a ranked CSV and leaves scheduling to the branch.", True),

    ("suppression-credit", "RM productivity",
     "Suppression measured as recovered RM hours",
     "Every suppressed Window-shop lead returns 12 RM minutes to the queue, and the total is reported in "
     "hours on the actions page.",
     "The value of this product is as much in the calls *not* made as the calls made. Quantifying it "
     "makes the business case without touching the conversion assumptions.",
     "Actions → RM hours recovered", "/actions",
     "Reports conversion lift only.", True),

    ("tiered-sla", "RM productivity",
     "Tier-specific SLAs and RM scripts, not generic advice",
     "24-hour callback for Quality, 48-hour assisted journey for Serious, automated nurture for "
     "Interested, explicit no-contact for Window-shop — each with a written opening line.",
     "An RM needs the first sentence of the call, not a probability.",
     "Customer detail → RM Workflow", "/customer/IDBI-L10010",
     "Provides a score and a tier label.", False),

    ("genai-brief", "RM productivity",
     "GenAI RM brief that knows when to say 'do not call'",
     "The brief is tier-aware: it writes a deprioritisation rationale for a window shopper rather than a "
     "sales pitch, and degrades to a deterministic template when no LLM key is present.",
     "A brief that always produces a pitch will get a window shopper called anyway, which is the exact "
     "behaviour this product exists to stop.",
     "Customer detail → RM Brief", "/customer/IDBI-L10121",
     "Generates an enthusiastic pitch for every lead.", False),

    ("underwriter-pdf", "RM productivity",
     "One-click underwriter packet",
     "A PDF carrying the tier, the reasons, the bureau view and the income inference — generated per "
     "lead, ready to attach.",
     "It shortens sanction cycle time and gives the underwriter the explainability trail in the format "
     "their process already uses.",
     "Underwriter packet (PDF)", "/api/customer/IDBI-L10010/underwriter-pdf",
     "Leaves the RM to re-key the rationale.", False),

    ("csv-export", "RM productivity",
     "RM queue export in the format a branch actually opens",
     "One click produces a CSV of the prioritised queue with tier, score, product, action and income "
     "figures.",
     "Adoption in a branch runs through the tools people already use.",
     "Export CSV", "/api/rm-queue/export",
     "Requires a login to a new dashboard.", False),

    ("vernacular", "RM productivity",
     "Call scripts in the customer's language",
     "Hindi, Marathi and Tamil briefs generated from fixed, reviewable templates with the figures "
     "injected — tier-aware, so a window shopper produces a deprioritisation script rather than a pitch.",
     "A branch RM in Pune or Coimbatore does not open the call in English. Template-driven rather than "
     "machine-translated, because a bank cannot put unreviewed text in front of a customer.",
     "Customer detail → call script", "/customer/IDBI-L10010",
     "Ships an English-only brief for a branch network that does not sell in English.", True),

    ("whatif-live", "RM productivity",
     "A what-if the RM can run during the call",
     "Sliders for DTI, savings, day-1 spend and luxury share, plus AA consent and application toggles — "
     "each change re-scored through the production rule engine and written to the audit log.",
     "It turns an explainability panel into a sales tool: the RM can show a customer exactly what would "
     "make them eligible, while still on the phone.",
     "Customer detail → what-if", "/customer/IDBI-L10055",
     "Shows a static score the RM cannot explore.", True),

    # ---------------- Trust & governance ----------------
    ("fairness-audit", "Trust & governance",
     "A live fair-lending audit, with findings reported as they fall",
     "Selection-rate parity across age, employment, geography and income, scored with the four-fifths "
     "rule on every page load. Bands below 0.80 are shown, named and explained — not hidden.",
     "A bank's model risk committee will ask this question in the first ten minutes. Arriving with the "
     "answer, including the uncomfortable parts, is worth more than arriving with a green tick.",
     "Governance → fairness", "/governance",
     "Asserts 'unbiased' on a compliance slide.", True),

    ("mitigation-sim", "Trust & governance",
     "Bias mitigation simulated, not promised",
     "For every dimension that fails or is on watch, the AA-consent mitigation is re-run across the "
     "whole population and the before/after disparate-impact ratio is published — including where it "
     "fails to close the gap.",
     "It converts a bias finding into a costed Round-2 workplan, and it demonstrates the honesty a "
     "regulated buyer is actually screening for.",
     "Governance → mitigation simulation", "/governance",
     "States that bias will be monitored post-deployment.", True),

    ("proxy-register", "Trust & governance",
     "Proxy-attribute register including the surname problem",
     "Age, employment type, city and income are registered as potential proxies with their mitigations. "
     "The customer's name is deliberately excluded from all 35 features because surname is a caste and "
     "community proxy in the Indian context — and that exclusion is verified in code on every load.",
     "Indian fair-lending risk does not look like the US textbook. Naming the surname vector shows the "
     "problem was thought about in the right jurisdiction.",
     "Governance → proxy register", "/governance",
     "Lists protected attributes as 'not used'.", True),

    ("audit-log", "Trust & governance",
     "A decision audit log a reviewer can actually query",
     "Every scoring decision, consent request, disposition and simulation stored append-only with the "
     "inputs, the engine and model versions live at the time, and the reason codes the RM saw. Exportable "
     "as CSV for the bank's own retention.",
     "Model risk committees block POCs over exactly this. Deterministic, seeded scoring is what makes the "
     "log meaningful — a replay of the same record returns the same tier.",
     "Governance → model risk", "/governance",
     "Asserts auditability on a compliance slide.", True),

    ("drift-monitoring", "Trust & governance",
     "Drift monitoring with the alarm demonstrated firing",
     "Population Stability Index per feature against the training distribution, on the conventional "
     "0.10 / 0.25 bands, plus a deliberately shifted next-quarter intake so the thresholds can be seen "
     "breaching rather than described.",
     "'Is it fair' is the first question governance asks; 'will it still be right in six months' is the "
     "second. A monitor nobody has seen alarm is not a monitor.",
     "Governance → model risk", "/governance",
     "Promises post-deployment monitoring.", True),

    ("missing-data-conservative", "Trust & governance",
     "Missing data is scored as unknown, never as good news",
     "An absent debt-to-income ratio is not read as a debt-free customer, and an absent salary-day spend "
     "pattern is not read as perfect discipline. Both score neutrally and say so in the reasons.",
     "The opposite behaviour is how a thin-file record ends up looking like an ideal borrower. Found by "
     "the degradation harness and fixed: losing a data source now shrinks the confident queue rather "
     "than inflating it.",
     "Governance → data quality", "/governance",
     "Uses zero-defaults, so empty fields quietly improve the score.", True),

    ("degradation-harness", "Engineering credibility",
     "Graceful degradation measured, not claimed",
     "Each sandbox field group is removed from every record and the whole book re-scored: tier churn, "
     "average score movement, RM-queue impact and crash count are published per source.",
     "Round 2 is an integration exercise against real, incomplete bank data. This is the difference "
     "between integrating in week 1 and discovering the edge cases in week 3.",
     "Governance → data quality", "/governance",
     "Assumes the sandbox will look like the synthetic data.", True),

    ("no-auto-decision", "Trust & governance",
     "No automated credit decision, enforced structurally",
     "Rules produce the tier; ML may move a score by at most ±8 points and may never demote a Quality "
     "Lead. Suppression is contact prioritisation and records no adverse credit action.",
     "It keeps the system inside the assistive envelope that IDBI's risk function can approve without a "
     "model-governance programme first.",
     "Architecture → compliance", "/architecture",
     "Lets the model set the outcome directly.", False),

    ("dpdp-inventory", "Trust & governance",
     "DPDP data inventory with lawful basis and retention per category",
     "Five data categories, each with purpose, lawful basis, retention window and the specific "
     "minimisation applied — raw statements are never retained, only derived aggregates.",
     "It is the document a DPO asks for on day one of a pilot, prepared before being asked.",
     "Governance → data inventory", "/governance",
     "Cites the DPDP Act by name on one slide.", True),

    ("explainability-coverage", "Trust & governance",
     "Explainability measured as coverage, not demonstrated on one lead",
     "The share of leads carrying a complete reason set across all three dimensions is computed and "
     "published, along with the share of suppressed leads carrying an adverse-action-ready reason.",
     "One explainable example proves nothing. A coverage percentage across the book is an auditable "
     "control.",
     "Governance → explainability coverage", "/governance",
     "Shows explainability on the hero customer.", True),

    ("graceful-degradation", "Trust & governance",
     "Degrades to rules instead of failing",
     "If the ML artefacts are missing or unloadable, scoring falls back to the deterministic rule engine "
     "and labels the mode on screen, rather than returning an error.",
     "A lead scorer that 500s when a model file is corrupt is not deployable in a branch.",
     "Customer detail → scoring mode badge", "/customer/IDBI-L10010",
     "Hard-fails when the model is unavailable.", False),

    # ---------------- Engineering credibility ----------------
    ("honest-impact", "Engineering credibility",
     "Monte Carlo backtest with a confidence interval, not a single number",
     "500 trials against fixed latent propensities on one population, comparing spray-and-pray, RM queue "
     "and quality-only strategies, reported with a 90% interval.",
     "It isolates the effect of prioritisation rather than asserting a lift, and it shows the downside "
     "case alongside the headline.",
     "Impact → backtest", "/impact",
     "Quotes one conversion number with no interval.", False),

    ("scenarios", "Engineering credibility",
     "Conservative / base / optimistic scenarios with stated assumptions",
     "Every conversion assumption is published with its haircut, and the conservative case still clears "
     "the Track 02 32% target.",
     "It answers 'what if you are wrong' before the panel asks it.",
     "Impact → scenario analysis", "/impact",
     "Presents the optimistic case only.", False),

    ("sandbox-contract", "Engineering credibility",
     "Sandbox integration contract already written",
     "Three endpoints, every field typed, with lengths, mandatory flags, sample values and descriptions, "
     "plus a live stub returning the exact payload shape.",
     "Round 2 is an integration exercise. The contract being ready is the difference between integrating "
     "in week 1 and negotiating the schema in week 3.",
     "Sandbox stub", "/api/sandbox/IDBI-L10010",
     "Plans to define the interface after shortlisting.", False),

    ("public-apis", "Engineering credibility",
     "Judge-accessible APIs with no login",
     "Health, impact, sandbox, demo comparison, model card, fairness, USP and glossary endpoints are "
     "deliberately unauthenticated; customer data stays behind the RM gate.",
     "A judge can verify the claims without a credential, while customer records stay protected.",
     "Health check", "/api/health",
     "Puts everything behind one demo password.", False),

    ("ml-honesty", "Engineering credibility",
     "ML credibility page that publishes the confusion matrix",
     "R², MAE, per-tier precision and recall, the confusion matrix, feature importance and an explicit "
     "rules-versus-hybrid comparison — including where the hybrid does not help.",
     "Publishing the matrix rather than the accuracy headline is the signal that the numbers were not "
     "chosen for the slide.",
     "ML credibility report", "/ml",
     "Reports accuracy only.", False),

    ("determinism", "Engineering credibility",
     "Deterministic, seeded and tested",
     "Fixed seed, pure-function scoring and a test suite that gates tier distribution, ranking "
     "determinism, ML guardrails and the AA uplift path.",
     "Reproducibility is the precondition for auditability — the same record must always produce the "
     "same tier.",
     "Automated regression suite", "/ml",
     "Regenerates data per run, so results move between demos.", False),

    ("glossary", "Engineering credibility",
     "A glossary that is tested against the codebase",
     "136 terms across banking, regulation, scoring, responsible AI, ML and engineering — with the "
     "abbreviation list harvested by scanning the source, and a test that fails the build when a term "
     "used in code is undefined.",
     "A Track 02 panel mixes risk, compliance and engineering readers. Shipping the dictionary keeps the "
     "product language precise instead of diluted.",
     "Glossary", "/glossary",
     "Assumes the reader shares the author's vocabulary.", True),

    ("ama-traceability", "Engineering credibility",
     "Line-by-line traceability to the IDBI orientation",
     "Every stated requirement from the AMA is mapped to the module that implements it and the page that "
     "demonstrates it.",
     "It lets a reviewer check coverage in two minutes instead of hunting through the app.",
     "Requirement traceability matrix", "/usps",
     "Describes features without mapping them to the brief.", False),
]


def build_usp_catalogue() -> dict:
    entries = [
        {
            "id": i,
            "pillar": p,
            "title": t,
            "claim": c,
            "why_idbi": w,
            "evidence_label": el,
            "evidence_url": eu,
            "typical_entry": te,
            "is_new": new,
        }
        for i, p, t, c, w, el, eu, te, new in USPS
    ]
    by_pillar = []
    for name, strapline in PILLARS:
        items = [e for e in entries if e["pillar"] == name]
        if items:
            by_pillar.append(
                {
                    "name": name,
                    "strapline": strapline,
                    "count": len(items),
                    "new_count": sum(1 for e in items if e["is_new"]),
                    "entries": items,
                }
            )
    return {
        "count": len(entries),
        "new_count": sum(1 for e in entries if e["is_new"]),
        "pillars": by_pillar,
        "entries": entries,
        "note": (
            "Every claim links to a page or endpoint in this running build. "
            "'Typical entry' describes the common alternative approach, not any specific competitor."
        ),
    }
