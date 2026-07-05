# IDBI Prospect Assist AI

Track **02** prototype for **IDBI Innovate 2026** — behavioral lead intelligence for existing IDBI liability customers.

## What it does (v0.6.1)

Addresses IDBI's stated pain: **~1% lead conversion** with too many window-shoppers wasting RM time.

| Dimension | Purpose |
|-----------|---------|
| **Repayment Capacity** | Disposable income, bureau profile, txn-inferred + multi-bank holistic income |
| **Purchase Intent** | Session depth, calculator usage, application started, window-shopping filter |
| **Behavioral Discipline** | Day-1 salary spend, UPI merchant mix, need vs luxury |
| **Delinquency Safety** | 12-month stress signal wired into composite score and tiering |
| **Lead Tiers** | Quality Lead → Serious → Interested → Window-shop Risk |
| **Product Match** | Home, Mortgage, Auto, Personal, Consumer Durable |

## Pages

| URL | Purpose |
|-----|---------|
| `/` | RM dashboard + priority queue |
| `/customer/{id}` | Full explainability (bureau, UPI, delinquency, ML contributions) |
| `/impact` | Business impact + Monte Carlo backtest + scenarios |
| `/ml` | ML credibility report (R², confusion matrix, rules vs hybrid) |
| `/multi-bank` | Cross-bank income comparison + statement upload simulation |
| `/architecture` | System design + ML model card |

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

- **34 features** including bureau score, UPI discipline, geo, multi-bank
- Safe hybrid: ±8 pt nudge max; never demotes Quality Leads
- Model card: `GET /api/ml/model-card`

## Validation

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -v
python scripts/validate.py
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
| `POST /api/multi-bank/analyze` | Simulate other-bank statement upload |
| `GET /api/sandbox/{id}` | Post-shortlist IDBI API stub |

## Hackathon submission (Jul 9)

- Deployment URL + GitHub + official PPT PDF
- See `docs/SUBMISSION_CHECKLIST.md`
