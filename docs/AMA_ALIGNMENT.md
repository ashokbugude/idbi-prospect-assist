# AMA Alignment Matrix — IDBI Prospect Assist AI (Track 02)

Maps IDBI orientation / AMA quotes to product features and demo paths.

| AMA / problem statement theme | Our implementation | Demo |
|---|---|---|
| ~1% liability lead conversion; RMs chase window shoppers | RM queue (23% of leads), window-shop tier (30%), Before/After toggle | `/` → toggle → RM queue |
| Repayment capacity beyond stated salary | `income_inference.py`, disposable income, DTI | `/customer/IDBI-L10010` |
| Transaction-based income (not salary slip only) | Credit inflow reconciliation, 30-day txn timeline | Customer detail → Transaction Timeline |
| Window shopping vs serious buyers | `window_shopping_flag`, session depth, calculator gates | `/customer/IDBI-L10121` |
| Day-1 salary spend / discipline | `salary_day_spend_ratio`, behavioral discipline score | Customer detail dimensions |
| Need vs want vs luxury | Spend breakdown chart + timeline tags | Customer detail |
| Future delinquency from spending | `score_delinquency_risk`, RAG bands | Customer detail → Delinquency |
| Multi-bank / Account Aggregator | `account_aggregator.py`, AA consent flow | `/multi-bank` → AA button |
| Bureau cross-check | `bureau.py`, underwriting hints | Customer detail → Bureau |
| Geo / UPI merchant patterns | `geo_stability`, `upi_signals.py` | Customer detail sections |
| Self-employed / gig irregular income | `SELF_EMPLOYED_MARGINS` in `config.py` | Income inference method note |
| Lead tiers for RM prioritization | Quality → Serious → Interested → Window-shop | Dashboard tier stats |
| 5 loan products + EMI gates | `scoring.py` product match | Customer detail → Product Match |
| ≥30% quality lead conversion | Impact simulation 41.3% + pilot plan | `/impact` |
| Human-in-loop; no auto credit decision | Disclaimers, PDF, RM workflow, ML guardrails | `/architecture` Compliance |
| AWS sandbox integration path | `/api/sandbox/{id}` + transaction array contract | `/api/sandbox/IDBI-L10010` |
| Digital clickstream (browsing) | Session minutes, calculator, app_started on dashboard | `/` Digital Clickstream section |
| GenAI for RM assistance | GenAI-ready brief + optional OpenAI | Customer detail RM brief |

**Pilot ask (post-shortlist):** IDBI AWS sandbox + 4-week RM A/B on Quality vs control cohort.
