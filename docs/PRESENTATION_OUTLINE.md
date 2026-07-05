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
- RMs waste time on **window shoppers** with no repayment capacity
- Stated salary ≠ actual cashflow; single-bank view misses holistic income

---

## Slide 3 — Solution

**Behavioral lead intelligence** for existing CASA customers:

1. **Repayment capacity** — disposable income, DTI, txn-inferred income
2. **Purchase intent** — digital journeys, session depth, calculator usage
3. **Behavioral discipline** — spend patterns, bureau signals
4. **Lead tiers** — Quality → Serious → Interested → Window-shop Risk

---

## Slide 4 — Architecture

```
Customer data → Enrichment (income, delinquency, geo)
             → Rule engine (5 products, EMI gates)
             → XGBoost hybrid (safe ±8 pt nudge)
             → RM dashboard + CSV export
```

Post-shortlist: IDBI AWS sandbox APIs replace synthetic data.

---

## Slide 5 — Key innovations

| Signal | How we use it |
|--------|----------------|
| Income inference | Credit inflow + savings vs stated salary |
| Multi-bank view | Holistic income uplift for cross-bank customers |
| Session depth | Distinguish deep intent from shallow browsing |
| Delinquency risk | 12-month stress from day-1 spend + DTI |
| Geo stability | UPI spend location vs declared city |
| Mortgage product | Refinance/top-up for housing exposure |

---

## Slide 6 — ML approach

- **28 → 32 features** including session minutes, geo, multi-bank share
- XGBoost regressor + tier classifier trained on rule labels
- **Safe hybrid:** ML nudges score ±8 pts; never demotes Quality Leads
- Full explainability: rule reasons + ML contribution panel

---

## Slide 7 — Business impact

| Metric | Before | After (POC) |
|--------|--------|-------------|
| Baseline conversion | ~1% | — |
| RM-prioritized queue | — | ~15–25% of leads |
| Projected conversion | — | ~12–18% on queue |
| **Quality lead conversion** | — | **≥32%** (Track 02 target) |
| RM time saved | — | ~70% of window-shop filtered |

---

## Slide 8 — Demo walkthrough

1. Dashboard — tier distribution + RM priority queue
2. Customer detail — income inference, delinquency, geo, product match
3. Multi-bank filter — holistic income view
4. Export CSV — RM outreach list
5. `/architecture` — system design for judges

**Live URL:** _(paste Render deployment URL)_

---

## Slide 9 — Roadmap (post-shortlist)

- Integrate IDBI sandbox APIs (transactions, bureau, digital footprint)
- A/B test RM callback SLA on Quality vs control
- Fine-tune on real conversion outcomes
- Embed in mobile RM app / CRM

---

## Slide 10 — Team & ask

**Srishti GenAI** — GenAI + banking analytics  
GitHub: `github.com/ashokbugude/idbi-prospect-assist`  
Thank you — ready for sandbox access and pilot with IDBI RM teams.
