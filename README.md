# IDBI Prospect Assist AI

Track **02** prototype for **IDBI Innovate 2026** — behavioral lead intelligence for existing IDBI liability customers.

## What it does (v0.7.0)

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

## Judge quick start

| Item | Value |
|------|--------|
| **Live demo** | https://idbi-prospect-assist.onrender.com *(Render free tier)* |
| **Login** | `/login` → PIN `idbi2026` |
| **Public API** | `/api/health` · `/api/impact` · `/api/sandbox/IDBI-L10010` |
| **Hero Quality Lead** | `/customer/IDBI-L10010` (Vikram Singh) |
| **Hero window shopper** | `/customer/IDBI-L10121` (Rahul Sharma) |
| **Hero multi-bank (AA demo)** | `/multi-bank` → `IDBI-L10055` (Aarav Singh) — Interested → Serious after AA fetch |

See `docs/AMA_ALIGNMENT.md` for full Track 02 traceability.

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
