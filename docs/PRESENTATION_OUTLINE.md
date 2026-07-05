# Prospect Assist AI — Presentation Outline (Hack2skill PPT)

Copy each slide into the official Hack2skill template and export as PDF.

---

## Slide 1 — Title

**Prospect Assist AI**  
IDBI Innovate 2026 · Track 02: Prospect Assist AI  
Team: **Srishti GenAI** | Leader: Ashok Bugude

---

## Slide 2 — Problem

- IDBI converts only **~1%** of liability-customer leads to loans
- RMs waste time on **window shoppers** (~30% of leads) with weak repayment capacity
- Stated salary ≠ actual cashflow; single-bank view misses holistic income

---

## Slide 3 — Solution

**Behavioral lead intelligence** for existing CASA customers:

1. **Repayment capacity** — disposable income, DTI, txn-inferred income, self-employed margins
2. **Purchase intent** — digital journeys, session depth, calculator usage
3. **Behavioral discipline** — need vs want vs luxury segregation
4. **Lead tiers** — Quality → Serious → Interested → Window-shop Risk

---

## Slide 4 — Architecture

```
Customer data → Enrichment (income, delinquency, geo, AA)
             → Rule engine (5 products, EMI gates)
             → XGBoost hybrid (safe ±8 pt nudge)
             → GenAI RM brief + dashboard + PDF export
```

Post-shortlist: IDBI AWS sandbox APIs (API Gateway → ECS → RDS/S3).

---

## Slide 5 — Key innovations (differentiators)

| Innovation | Demo |
|------------|------|
| **GenAI-ready RM brief** | Template + optional OpenAI (`OPENAI_API_KEY`); human-in-loop |
| **30-day txn timeline** | Tagged salary, rent, luxury, savings |
| **Account Aggregator flow** | Consent → fetch → auto-rescore |
| **Before/After toggle** | 1% spray vs 25% RM queue conversion |
| **Underwriter PDF** | Income, bureau, delinquency, product match |

---

## Slide 6 — ML approach

- **35 features** — feature vector order aligned with `FEATURE_NAMES`
- XGBoost regressor + tier classifier trained on rule labels
- **Safe hybrid:** ML nudges score ±8 pts; never demotes Quality Leads
- Full explainability: rule reasons + ML contribution panel

---

## Slide 7 — Business impact (simulation + pilot plan)

| Metric | Before | After (POC model) |
|--------|--------|-------------------|
| Baseline conversion | ~1% | — |
| RM-prioritized queue | 100% contacted | **~23%** of leads |
| RM queue conversion | — | **~25%** (tier-weighted sim) |
| **Quality segment conversion** | — | **~41%** (simulation¹) |
| Window-shop filtered | — | **~30%** deprioritized |

¹ **Simulation, not observed IDBI pilot data.** Tier-weighted assumptions + Monte Carlo backtest; 4-week RM A/B pilot post-shortlist.

---

## Slide 8 — Demo walkthrough (2 min)

1. Login → Dashboard — tier distribution + **Before/After** toggle
2. Quality Lead — **GenAI brief** → income inference → **txn timeline**
3. Multi-bank — **AA consent** on `IDBI-L10055` → fetch confirms holistic income → tier uplift (or EMI capacity if tier unchanged)
4. Impact page — pilot validation plan
5. Export CSV + **Underwriter PDF**
6. `/architecture` — AWS + compliance

**Live URL:** https://idbi-prospect-assist-474562381457.asia-south1.run.app  
**Login PIN:** `idbi2026` (RM demo gate)  
**Public APIs (no login):** `/api/health`, `/api/impact`, `/api/sandbox/IDBI-L10010`  
**GitHub:** `github.com/ashokbugude/idbi-prospect-assist`

---

## Slide 9 — Compliance & pilot roadmap

- **DPDP:** AA consent; data minimization
- **No auto-credit-decision:** AI assists, underwriter decides
- **Human-in-loop:** ML guardrails + RM workflow SLA
- **Pilot KPIs:** Quality conversion ≥32%, RM hours −40%, 4-week A/B

---

## Slide 10 — Team & ask

**Srishti GenAI** — GenAI + banking analytics  
Ready for **IDBI AWS sandbox** access and RM team pilot.  
Thank you.
