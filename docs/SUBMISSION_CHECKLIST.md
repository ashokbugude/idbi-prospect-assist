# IDBI Innovate 2026 — Track 02 Submission Checklist

**Team:** Srishti GenAI · **Deadline:** Jul 9, 2026 · **Version:** 0.7.0

## Code & deployment

- [ ] Push repo to GitHub: `https://github.com/ashokbugude/idbi-prospect-assist`
- [x] Deploy live demo (Google Cloud Run — `gcloud run deploy`)
- [ ] Optional: mirror on Render using `render.yaml` / `Dockerfile`
- [ ] Verify public URL loads dashboard (login PIN: `idbi2026`)
- [ ] Verify `/api/health` returns `version: 0.7.0` and `ml_ready: true`
- [ ] Test RM CSV export: `/api/rm-queue/export`
- [ ] Test sandbox stub: `/api/sandbox/IDBI-L10010`
- [ ] Test AA flow on `/multi-bank` (hero: `IDBI-L10055` — tier uplift after consent)
- [ ] Test PDF export from customer detail page

## Hack2skill platform (manual)

- [ ] Submit POC form with deployment URL + GitHub link
- [ ] Upload mandatory PPT PDF (`docs/IDBI_Prospect_Assist_Submission.pptx` → export to PDF in PowerPoint)
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

## Live deployment

**URL:** https://idbi-prospect-assist-474562381457.asia-south1.run.app  
**Login PIN:** `idbi2026`  
**Region:** Google Cloud Run (`asia-south1`)

Redeploy after code changes:

```powershell
gcloud run deploy idbi-prospect-assist --source . --region asia-south1 --allow-unauthenticated --set-env-vars "RM_DEMO_PIN=idbi2026,PYTHONUNBUFFERED=1"
```

Optional Render mirror: connect repo at [render.com](https://render.com) → New → Blueprint → `ashokbugude/idbi-prospect-assist`.

## Render deploy steps (optional)

1. Create repo on GitHub and push `main`
2. [render.com](https://render.com) → New → Blueprint → connect repo
3. Render reads `render.yaml` and builds Docker image (trains ML on build)
4. Set `RM_DEMO_PIN` in Render env if changing default
5. Copy the `*.onrender.com` URL for Hack2skill submission (Slide 8)

**Paste into Hack2skill notes + PPT Slide 8:**
```
Demo URL: https://idbi-prospect-assist-474562381457.asia-south1.run.app
Login PIN: idbi2026
Public APIs (no login): /api/health · /api/impact · /api/sandbox/IDBI-L10010
```

## 2-minute demo script (rehearse)

1. **Problem (15s):** ~1% conversion; RMs chase window shoppers
2. **Dashboard (20s):** Tier distribution, Before/After toggle, RM queue ~23%
3. **Quality Lead detail (45s):** GenAI brief → income inference → txn timeline → need/want/luxury → PDF
4. **Multi-bank (20s):** AA consent on `IDBI-L10055` → fetch → tier moves Interested → Serious; highlight holistic income + affordable EMI
5. **Impact (20s):** Baseline 1% → RM queue 25% → quality 41% (simulation + pilot plan)
6. **Architecture (15s):** AWS diagram + compliance + sandbox stub
7. **Ask (10s):** Ready for IDBI sandbox pilot with RM teams

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

## Aligned metrics (seed=42, n=200)

| Metric | Value |
|--------|-------|
| RM queue (Quality + Serious) | ~23% |
| Window-shop Risk | ~30% |
| Quality segment conversion (sim) | ~41% |
| RM queue conversion (sim) | ~25% |
