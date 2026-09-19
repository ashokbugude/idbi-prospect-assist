# Track 02 Requirements — Coverage & Gap Analysis

**Version:** 0.9.0 · **Reviewed:** 19 Sep 2026 · **Status:** shortlisted, preparing refinement round

Assessed against the Track 02 problem statement, the IDBI orientation (AMA) notes captured in
`AMA_ALIGNMENT.md`, and the sandbox field submission in `SANDBOX_DATA_FIELD_SUBMISSION.md`.

---

## 1. Stated requirements — all met

| # | Requirement | Status | Evidence |
|---|---|---|---|
| 1 | Lift ~1% liability-lead conversion | Met | `/impact` — RM queue 25%, quality segment 41.3% vs 1% baseline, Monte Carlo backtest with 90% CI |
| 2 | Repayment capacity beyond stated salary | Met | `income_inference.py` — credit-inflow reconciliation with an explicit confidence score |
| 3 | Transaction-inferred income | Met | Inferred income + variance + method note on every customer page |
| 4 | Purchase intent from digital journeys | Met | `score_intent()` — visits, calculator, session depth, application started |
| 5 | Window-shopper filtering | Met | Hard tier override, not just a ranking penalty |
| 6 | Behavioural discipline | Met | Day-1 salary spend, need/want/luxury, savings transfers, UPI merchant mix |
| 7 | Need vs want vs luxury segmentation | Met | Spend chart + tagged 30-day transaction timeline |
| 8 | Future delinquency from spending | Met | 12-month stress score carrying 17% of the composite, can cap a tier |
| 9 | Multi-bank / Account Aggregator | Met | Consent → fetch → re-score, with tier movement shown before/after |
| 10 | Self-employed & gig income | Met | Industry net-margin model in `config.SELF_EMPLOYED_MARGINS` |
| 11 | Bureau cross-check | Met | `bureau.py` — band, enquiries, utilisation, vintage, underwriting hint |
| 12 | Geo / UPI merchant patterns | Met | `geo_stability`, `upi_signals.py` |
| 13 | Lead tiers for RM prioritisation | Met | Four tiers with SLAs and explicit no-contact tier |
| 14 | Five products with EMI gates | Met | `scoring.py` → `SCORERS` + `PRODUCT_MIN_EMI` |
| 15 | ≥32% quality-segment conversion | Met | 41.3% base case; conservative scenario still clears 32% |
| 16 | Human-in-loop, no auto credit decision | Met | ±8 pt ML nudge ceiling, Quality Leads never demoted, underwriter packet |
| 17 | AWS sandbox integration path | Met | Typed three-endpoint field contract + live stub at `/api/sandbox/{id}` |
| 18 | GenAI RM assistance | Met | Tier-aware brief that writes a deprioritisation rationale, not a pitch, for window shoppers |
| 19 | Explainability | Met | Reasons on every dimension; coverage now measured, not asserted (`/fairness`) |

**Conclusion:** no stated Track 02 requirement is unmet at v0.7.0.

---

## 2. Gaps closed in v0.8.0

These were not stated requirements. They are the places where a shortlisted entry gets beaten by
another shortlisted entry.

| Gap at v0.7.0 | Why it mattered | Closed by |
|---|---|---|
| The engine scored leads but said nothing about the 77% of the book that is not callable | An RM cannot act on "Interested" | **Lead Uplift Simulator** — 11 executable levers, each a real re-score through the production rule engine, plus the shortest path to the next tier (`/customer/{id}`, `/api/customer/{id}/uplift`) |
| A tier was a point-in-time verdict with no notion of durability | An underwriter needs to know whether quality is structural or a good month | **Per-lead stress test** — adverse six-month re-score, Resilient/Fragile verdict with a sizing instruction |
| `recommended_action` was one static string with no cost, channel or value | Branch capacity is budgeted in minutes; an uncosted recommendation cannot be prioritised | **Next Best Action engine** — channel, SLA, script, RM-minute cost, conversion delta, expected rupees, ranked by ₹ per RM minute (`/actions`) |
| No operating rhythm — a ranked list is not a work plan | The buyer is a branch manager running a morning huddle | **Branch day plan** — every top action packed into 6 RMs × 360 productive minutes, SLA commitments first, with utilisation and captured pipeline value |
| Suppression value was invisible | The business case is as much in calls not made | **RM hours recovered** — 11.8 h/day across 59 suppressed leads, reported as a headline metric |
| Compliance was slide-level assertion | A bank's model risk committee asks in the first ten minutes | **Fairness & Governance page** — four-fifths audit on every load, proxy register, DPDP data inventory, explainability coverage, governance controls (`/fairness`) |
| No answer to "prove the bias mitigation works" | "We will monitor it" is not evidence | **Mitigation simulation** — the AA lever re-run across the population with before/after disparate-impact ratios, reported honestly including where it fails to close the gap |
| Mixed-audience vocabulary | The panel spans risk, compliance and engineering | **Glossary** — 136 terms, abbreviations harvested by scanning the source, with a test that fails the build when a term used in code is undefined (`/glossary`) |
| Differentiation was implicit | Judges compare entries, they do not reverse-engineer them | **USP catalogue** — 34 capabilities, each linked to a verifiable page, each contrasted with the common alternative approach (`/usps`) |

---

## 2b. Added in v0.9.0 — beyond differentiation, into deployability

| Gap | Why it mattered | Closed by |
|---|---|---|
| The engine never learned whether it was right | The ML trains on the rule engine's own labels, agrees by construction, and moves **zero tiers** across 200 leads | **Outcome feedback loop** (`/outcomes`) — append-only disposition capture, calibration of every conversion assumption, retrain-readiness gauge |
| Every impact number was an assumption with no way to check it | A panel discounts unverifiable figures | **Calibration scoreboard** — assumed vs observed per tier in percentage points, status unvalidated / emerging / validated / diverging |
| Auditability was asserted, not demonstrated | Model risk committees gate on this | **Decision audit log** — append-only, versioned, reason-coded, CSV export |
| No answer to "will it still be right in six months" | The second question governance asks after fairness | **PSI drift monitoring** on the 0.10/0.25 bands, plus a shifted-intake scenario so thresholds are seen breaching |
| Sandbox data will be incomplete; behaviour unknown | Round 2 is an integration exercise | **Data-quality gates** — per-field completeness against the sandbox contract, measured tier churn per missing source |
| English-only briefs for a branch network | RMs in Pune and Coimbatore do not open in English | **Vernacular briefs** — Hindi, Marathi, Tamil, template-driven and tier-aware |
| Explainability was read-only | An RM on a call cannot explore it | **Live what-if** — sliders re-scored through the production engine, each simulation audit-logged |

---

## 3. Defects found and fixed

**a. ML import crashed the request path.** `score_customer()` imported `app.ml_model` **outside** its `try` block. A missing or broken ML
dependency therefore raised `ModuleNotFoundError` on the request path and returned HTTP 500 instead of
degrading to the rule engine — reproduced on a machine without `joblib` installed. The import now sits
inside the guarded block and the fallback records the exception type.

**b. Missing data was scored as good news.** An absent `debt_to_income_ratio` defaulted to `0` and earned
"Low existing debt burden supports new EMI" (+25); an absent `salary_day_spend_ratio` defaulted to `0` and
earned "disciplined pattern" (+15). A thin-file record therefore looked like an ideal borrower. Both now
score neutrally and say so in the reasons. Found by the degradation harness: removing the transactions API
used to *grow* the RM queue from 46 to 57; it now correctly shrinks it to 18.

**c. Records without `name` or `city` crashed the scorer.** `score_customer_rules()` indexed those keys
directly, so a sandbox record missing them returned HTTP 500. Now defaulted.

**d. No digital footprint excluded a whole acquisition channel.** With the digital endpoint absent, intent
collapsed to ~10 and the RM queue fell to **zero** — branch-acquired customers were structurally unable to
be called, which is both an integration failure and a fairness problem. Intent now falls back to a
transaction-only basis and the tier is capped at Serious, because unverified intent must not carry a
24-hour SLA.

**e. Non-deterministic timelines and AA fetches.** Both seeded from `hash()` or a fresh consent id, so the
transaction timeline changed on every restart and the AA hero demo showed a different score on every click.
Both now seed from the customer id.

**f. The scorer assumed clean types and 500'd on a realistic feed.** `monthly_income: "85000"` (a string,
which any CSV or JSON export produces), `"1,25,000"`, and `null` in place of an absent key each raised a
`TypeError` on the request path. A new ingest layer (`app/ingest.py`) coerces at a single chokepoint —
`enrich_customer()` — and drops what it cannot parse rather than zeroing it, so an unreadable field is
scored as unknown instead of as good news.

**g. A negative income scored *better* than a zero income** (47.1 vs 43.1), because the negative value
flowed into ratio arithmetic unchecked. Negatives are now floored to zero and flagged.

**h. Boolean flags alone counted as a digital footprint.** A sandbox returning
`{application_started: false, window_shopping_flag: false}` — exactly what it sends for a customer with no
digital activity — satisfied the presence check, so the transaction-only fallback never ran and the lead
collapsed to intent 10. Presence now requires a *measurable* signal (page visits, calculator uses or
session minutes); booleans do not qualify. This was the same structural-exclusion bug as (d), still
reachable through a realistic payload.

**i. The documented ingest rules were prose, not code.** `/governance` stated that a record missing
`customer_id` or `monthly_income` is rejected at ingest — but an empty `{}` scored as "Interested" at 40.9.
`ingest.validate_customer()` now enforces the gate, `POST /api/ingest/check` exercises it against any
payload, and the data-quality page reports acceptance across the live population.

**j. Warmup spent ~1 second on fsync.** Seeding the outcome and audit stores issued one fsync per record
(287 of them), and the audit writer re-imported the ML module for every entry to resolve a version string.
Batched to one fsync per run and memoised the version: 917 ms → 19 ms for 200 audit entries, 146 ms → 7 ms
for 87 outcomes.

Graceful degradation is now a stated governance control on `/governance` and a USP.

---

## 4. Open items for the refinement round

1. **Gig and low-income disparate impact.** The audit reports DI 0.43 (gig) and 0.40 (< ₹40k) against the
   four-fifths threshold. Both have a business-necessity justification and product-eligibility evidence
   showing the segments are not excluded from credit. The AA mitigation narrows the self-employed gap
   (+0.10) but does not close it. **Ask of IDBI:** realised-delinquency data by employment type from the
   sandbox, so the risk premium can be justified or removed with evidence rather than assumption.
2. **Conversion assumptions remain assumptions.** Tier close rates and action relative-lifts are
   POC figures, labelled as such throughout. The 4-week RM A/B is the calibration mechanism.
3. **Deck inconsistency.** Slides 2 and 7 of the round-1 deck say *Google Cloud Run*; slides 10 and 13,
   `render.yaml` and `config.py` say *Render*. Reconcile before any resubmission.
4. **AA is simulated.** Live FIP connectors require an AA aggregator relationship — a Round-2 ask.
5. **Synthetic data.** n=200, seed=42. The fairness audit, uplift simulator and NBA engine all run
   unchanged against sandbox data; the numbers will move, the method will not.
