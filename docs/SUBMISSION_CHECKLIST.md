# IDBI Innovate 2026 — Track 02 Submission Checklist

**Team:** Srishti GenAI · **Deadline:** Jul 9, 2026 (round 1, submitted) · **Version:** 0.9.0

## Code & deployment

- [ ] Push repo to GitHub: `https://github.com/ashokbugude/idbi-prospect-assist`
- [ ] Deploy live demo on **Render (free)** — see `docs/RENDER_DEPLOY.md`
- [ ] Verify public URL loads dashboard (login PIN: `idbi2026`)
- [ ] Verify `/api/health` returns `version: 0.9.0` and `ml_ready: true`
- [ ] Test RM CSV export: `/api/rm-queue/export`
- [ ] Test sandbox stub: `/api/sandbox/IDBI-L10010`
- [ ] Test AA flow on `/multi-bank` (hero: `IDBI-L10055` — tier uplift after consent)
- [ ] Test PDF export from customer detail page

## Hack2skill platform (manual)

- [ ] Submit POC form with deployment URL + GitHub link
- [ ] Upload mandatory PPT PDF (`input/IDBI_Prospect_Assist_Submission_FILLED.pptx` → export to PDF in PowerPoint)
- [ ] Complete Startup Information form (5 fields)
- [ ] Add teammates on Hack2skill (max 4) if available

## Local validation before submit

```powershell
cd C:\Users\ashok\Projects\idbi-prospect-assist
.\.venv\Scripts\activate
pip install -r requirements.txt
python -m app.data_generator
python scripts/train_model.py
python scripts/validate.py
python -m pytest tests/ -v
uvicorn app.main:app --reload --port 8080
```

Login at `http://localhost:8080/login` with PIN `idbi2026`.

**Judge / API access:** Read-only APIs (`/api/health`, `/api/impact`, `/api/sandbox/{id}`, `/api/demo-comparison`, `/api/ml/model-card`) work without login. UI pages and CSV export require RM PIN.

## Live deployment (Render — free)

**URL:** https://idbi-prospect-assist.onrender.com  
**Login PIN:** `idbi2026`  
**Platform:** Render free tier (Docker)

### Deploy steps

1. Push repo to GitHub
2. [render.com](https://render.com) → **New +** → **Blueprint** → connect `ashokbugude/idbi-prospect-assist`
3. Apply — first build ~8–15 min (ML trains on build)
4. Set `PUBLIC_DEMO_URL` in Render env to your `*.onrender.com` URL

Full guide: `docs/RENDER_DEPLOY.md`

> HF Docker Spaces are **paid** — not needed for this POC.

**Paste into Hack2skill notes + PPT Slide 8:**
```
Demo URL: https://idbi-prospect-assist.onrender.com
Login PIN: idbi2026
Public APIs (no login): /api/health · /api/impact · /api/sandbox/IDBI-L10010
```

## Render deploy steps (reference)

1. Create repo on GitHub and push `main`
2. [render.com](https://render.com) → New → Blueprint → connect repo
3. Render reads `render.yaml` and builds Docker image (trains ML on build)
4. Set `RM_DEMO_PIN` in Render env if changing default
5. Copy the `*.onrender.com` URL for Hack2skill submission (Slide 8)

## 2-minute demo script (rehearse)

1. **Problem (15s):** ~1% conversion; RMs chase window shoppers
2. **Dashboard (20s):** Tier distribution, Before/After toggle, RM queue ~23%
3. **Quality Lead detail (45s):** GenAI brief → income inference → txn timeline → need/want/luxury → PDF
4. **Multi-bank (20s):** AA consent on `IDBI-L10055` → fetch → tier moves Interested → Serious; highlight holistic income + affordable EMI
5. **Impact (20s):** Baseline 1% → RM queue 25% → quality 41% (simulation + pilot plan)
6. **Architecture (15s):** AWS diagram + compliance + sandbox stub
7. **Ask (10s):** Ready for IDBI sandbox pilot with RM teams

## Refinement-round demo additions (v0.8.0)

8. **Actions (30s):** `/actions` — "here is the branch's morning, costed in RM minutes";
   11.8 RM hours recovered by suppression, 95.8% of pipeline value captured within capacity
9. **Uplift (30s):** `/customer/IDBI-L10055` — Serious, 7.6 points short of Quality; one lever closes it;
   stress test says Fragile, so size conservatively
10. **Governance (40s):** `/governance` — four-fifths audit with both findings shown openly and the AA
    mitigation simulated; then Model risk (append-only audit log, PSI drift with the alarm firing) and
    Data quality (zero failures when any sandbox source is removed)
11. **Outcomes (30s):** `/outcomes` — "the system finds out whether it was right". Calibration shows
    Serious running 7.9 pp above its assumption; retrain readiness at 49%. Say plainly that today's ML
    moves zero tiers because it learns from rules, and that this loop is what changes that
12. **Vernacular + what-if (20s):** `/customer/IDBI-L10055` — switch the brief to हिन्दी, then move the
    DTI slider and watch Serious become a Quality Lead live

## What judges see

| Capability | Endpoint / page |
|------------|-----------------|
| RM priority queue (~23% of leads) | `/` |
| Before/After demo | `/` toggle |
| GenAI RM brief | `/customer/{id}` |
| Transaction timeline | `/customer/{id}` |
| Underwriter PDF | `/api/customer/{id}/underwriter-pdf` |
| Account Aggregator flow | `/multi-bank` |
| Explainability | `/customer/{id}` |
| Architecture + AWS + compliance | `/architecture` |
| AMA alignment matrix | `docs/AMA_ALIGNMENT.md` |
| Pilot validation plan | `/impact` |
| 30%+ quality conversion (simulation) | `/api/impact` |
| Multi-bank holistic view | `/api/multi-bank` |
| CSV for RMs | `/api/rm-queue/export` |
| Sandbox integration stub | `/api/sandbox/{id}` |
| RM auth gate | `/login` |
| Lead Uplift Simulator (counterfactual) | `/customer/{id}` · `/api/customer/{id}/uplift` |
| Next Best Action + branch capacity plan | `/actions` · `/api/next-best-action` |
| Fair-lending audit + DPDP evidence | `/fairness` · `/api/fairness` |
| USP catalogue | `/usps` · `/api/usps` |
| Glossary | `/glossary` · `/api/glossary` |
| Requirement coverage review | `docs/TRACK02_GAP_ANALYSIS.md` |
| Outcome feedback loop + calibration | `/outcomes` · `/api/outcomes` |
| Decision audit log | `/governance?tab=model-risk` · `/api/audit/export` |
| Drift monitoring (PSI) | `/governance?tab=model-risk` · `/api/monitoring` |
| Data-quality + degradation gates | `/governance?tab=data-quality` · `/api/data-quality` |
| Vernacular call scripts | `/customer/{id}` -> language switcher |
| Live what-if simulator | `POST /api/customer/{id}/simulate` |

## Aligned metrics (seed=42, n=200)

| Metric | Value |
|--------|-------|
| RM queue (Quality + Serious) | ~23% |
| Window-shop Risk | ~30% |
| Quality segment conversion (sim) | ~41% |
| RM queue conversion (sim) | ~25% |
