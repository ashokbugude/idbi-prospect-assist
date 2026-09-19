# IDBI Prospect Assist AI

Track **02** prototype for **IDBI Innovate 2026** — behavioral lead intelligence for existing IDBI liability customers.

## What it does (v0.9.0)

Addresses IDBI's stated pain: **~1% lead conversion** with too many window-shoppers wasting RM time.

**RM login:** `/login` — demo PIN `idbi2026` (override via `RM_DEMO_PIN` env)

| Dimension | Purpose |
|-----------|---------|
| **Repayment Capacity** | Disposable income, bureau profile, txn-inferred + multi-bank holistic income |
| **Purchase Intent** | Session depth, calculator usage, application started, window-shopping filter |
| **Behavioral Discipline** | Day-1 salary spend, UPI merchant mix, need vs want vs luxury |
| **Delinquency Safety** | 12-month stress signal wired into composite score and tiering |
| **Lead Tiers** | Quality Lead → Serious → Interested → Window-shop Risk |
| **Product Match** | Home, Mortgage, Auto, Personal, Consumer Durable |
| **GenAI RM Brief** | AI-assisted call script per customer (Srishti GenAI) |
| **Account Aggregator** | Simulated AA consent → fetch other-bank statements → rescore |
| **Lead Uplift Simulator** | Counterfactual "what would move this lead" — 11 levers, each a real re-score |
| **Lead stress test** | Adverse-scenario re-score → Resilient / Fragile tier verdict |
| **Next Best Action** | Channel, SLA, script, RM-minute cost and expected ₹ per action |
| **Branch day plan** | Every action packed into real RM capacity, SLA commitments first |
| **Fairness audit** | Four-fifths rule across age, employment, geography, income — live, every load |
| **DPDP governance** | Proxy register, data inventory, explainability coverage, control evidence |
| **Outcome feedback loop** | RM call dispositions -> calibration of every conversion assumption -> retrain labels |
| **Decision audit log** | Append-only, versioned, reason-coded, CSV-exportable |
| **Drift monitoring** | PSI per feature with the alarm demonstrated firing |
| **Data-quality gates** | Completeness per field + measured degradation when a sandbox source is missing |
| **Vernacular briefs** | Hindi, Marathi and Tamil call scripts, template-driven |
| **Live what-if** | Sliders that re-score the lead through the production engine during a call |
| **Ingest gate** | Type coercion + hard validation at the sandbox boundary — strings, nulls and out-of-range values |

## Pages

| URL | Purpose |
|-----|---------|
| `/` | RM dashboard + priority queue + Before/After demo toggle |
| `/login` | RM PIN gate (demo: `idbi2026`) |
| `/customer/{id}` | Explainability + GenAI brief + txn timeline + PDF export |
| `/impact` | Business impact + pilot plan + Monte Carlo backtest |
| `/ml` | ML credibility report (R², confusion matrix, rules vs hybrid) |
| `/multi-bank` | AA flow + cross-bank income + statement upload |
| `/architecture` | AWS diagram + compliance + pilot KPIs |
| `/actions` | Next Best Action — branch playbook, today's queue, capacity plan |
| `/fairness` | Fair-lending audit, proxy register, DPDP data inventory |
| `/differentiators` | 34 differentiators, each linked to verifiable evidence in the app |
| `/glossary` | 153 terms and abbreviations used across the repo, searchable |
| `/outcomes` | Feedback loop — dispositions, calibration, retrain readiness |
| `/governance` | Fairness &amp; bias · Model risk (audit + drift) · Data quality |

## Judge quick start

| Item | Value |
|------|--------|
| **Live demo** | https://idbi-prospect-assist.onrender.com *(Render free tier)* |
| **Login** | `/login` → PIN `idbi2026` |
| **Public API** | `/api/health` · `/api/impact` · `/api/sandbox/IDBI-L10010` |
| **Hero Quality Lead** | `/customer/IDBI-L10010` (Vikram Singh) |
| **Hero window shopper** | `/customer/IDBI-L10121` (Rahul Sharma) |
| **Hero multi-bank (AA demo)** | `/multi-bank` → `IDBI-L10055` (Aarav Singh) — Interested → Serious after AA fetch |

See `docs/AMA_ALIGNMENT.md` for full Track 02 traceability and
`docs/TRACK02_GAP_ANALYSIS.md` for the requirement-by-requirement coverage review.

## Quick start

```bash
cd C:\Users\ashok\Projects\idbi-prospect-assist
.\.venv\Scripts\activate
pip install -r requirements.txt
python -m app.data_generator
python scripts/train_model.py
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## ML layer (XGBoost hybrid)

```bash
python scripts/train_model.py
python scripts/compare_scoring.py
```

- **35 features** including bureau score, UPI discipline, geo, multi-bank
- Customer name is deliberately **excluded** from every feature — surname is a caste/community proxy
- Safe hybrid: ±8 pt nudge max; never demotes Quality Leads
- Model card: `GET /api/ml/model-card`

## Validation

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -v
python scripts/validate.py
python scripts/benchmark.py
```

## Key APIs

| Endpoint | Description |
|----------|-------------|
| `GET /api/impact` | Conversion lift vs 1% baseline |
| `GET /api/impact/methodology` | Documented business proof |
| `GET /api/ml/model-card` | ML metrics + feature importance |
| `GET /api/ml/evaluation` | Full ML credibility package |
| `GET /api/impact/backtest` | Monte Carlo conversion backtest |
| `GET /api/rm-queue/export` | CSV for RM outreach |
| `POST /api/aa/consent` | Account Aggregator consent simulation |
| `POST /api/aa/fetch` | AA fetch statements + auto-rescore |
| `GET /api/customer/{id}/rm-brief` | GenAI RM call brief |
| `GET /api/customer/{id}/underwriter-pdf` | Underwriter packet PDF |
| `GET /api/demo-comparison` | Before/After conversion comparison |
| `GET /api/customer/{id}/uplift` | Counterfactual lever simulation + stress test |
| `GET /api/customer/{id}/next-best-action` | Costed, ranked action list for one lead |
| `GET /api/next-best-action` | Branch-wide action plan and capacity utilisation |
| `GET /api/fairness` | Fair-lending audit (public — no login) |
| `GET /api/differentiators` | USP catalogue (public — no login) |
| `GET /api/glossary` | Glossary (public — no login) |
| `GET/POST /api/outcomes` | Read the feedback loop, or record an RM disposition |
| `GET /api/monitoring` | Population drift (PSI) per feature (public) |
| `GET /api/data-quality` | Completeness + degradation report (public) |
| `GET /api/audit` · `/api/audit/export` | Decision audit log, JSON or CSV |
| `POST /api/customer/{id}/simulate` | Live what-if re-score through the rule engine |
| `POST /api/ingest/check` | Run a raw sandbox record through coercion + the hard ingest gate |

## Deploy (Render — free)

See **`docs/RENDER_DEPLOY.md`** for step-by-step setup.

```powershell
# After deploy, set your URL and regenerate submission deck
$env:PUBLIC_DEMO_URL="https://idbi-prospect-assist.onrender.com"
python scripts/update_submission_ppt.py
```

> Hugging Face Docker Spaces are **paid** — use Render instead (`docs/RENDER_DEPLOY.md`).

## Hackathon submission

- Deployment URL + GitHub + official PPT PDF
- See `docs/SUBMISSION_CHECKLIST.md`
