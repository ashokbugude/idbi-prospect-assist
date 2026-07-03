# IDBI Prospect Assist AI

Track **02** prototype for **IDBI Innovate 2026** — behavioral lead intelligence for existing IDBI liability customers.

## What it does (v0.2)

Addresses IDBI's stated pain: **~1% lead conversion** with too many window-shoppers wasting RM time.

| Dimension | Purpose |
|-----------|---------|
| **Repayment Capacity** | Disposable income + affordable EMI from transaction behavior |
| **Purchase Intent** | Separates serious buyers from window shoppers (app visits, calculator, application) |
| **Behavioral Discipline** | Salary spend timing, needs vs luxury, savings transfers |
| **Lead Tiers** | Quality Lead → Serious → Interested → Window-shop Risk |
| **Product Match** | Next-best loan offer (home, auto, personal, consumer durable) |

## Quick start

```bash
cd C:\Users\ashok\Projects\idbi-prospect-assist
.\.venv\Scripts\activate
pip install -r requirements.txt
python -m app.data_generator
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Dashboard: http://localhost:8000
- Customer detail: http://localhost:8000/customer/IDBI-L10001

## ML layer (XGBoost hybrid)

Rules provide explainability; XGBoost learns non-linear patterns from 4,000 synthetic profiles.

```bash
python scripts/train_model.py   # trains regressor + classifier
python scripts/compare_scoring.py  # rule vs hybrid comparison
```

| Model | Validation metric |
|-------|-------------------|
| Score regressor | MAE ~2.2 on composite (0–100) |
| Tier classifier | ~88% accuracy |

**Safety:** ML can nudge composite ±8 pts max; never demotes Quality Leads; low-confidence ML ignored.

## Validation (pre-submission)

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -v
python scripts/validate.py
```

**v0.4 checks:** 13/13 unit tests · XGBoost hybrid · affordability gates · RM queue · impact metrics

## API

| Endpoint | Description |
|----------|-------------|
| `GET /api/health` | Health check |
| `GET /api/impact` | Conversion lift vs 1% baseline |
| `GET /api/rm-queue` | Quality + Serious leads for RM outreach |
| `GET /api/customers?tier=Quality+Lead` | Ranked leads |
| `GET /api/customers/{id}` | Full explainability profile |
| `GET /docs` | OpenAPI (auto-generated) |

## Hackathon submission (Jul 9)

- Deployment URL + GitHub + official PPT template
- Round 1: synthetic data (no sandbox yet)
- Round 2: integrate IDBI sandbox APIs on AWS

## Structure

```
app/
  main.py              # FastAPI routes + dashboard
  scoring.py           # 3-dimension scoring + lead tiers + product match
  data_generator.py    # Synthetic behavioral customer data
  data/customers.json
  templates/           # Dashboard + detail explainability
  static/style.css
```
