# IDBI Innovate 2026 — Track 02 Submission Checklist

**Team:** Srishti GenAI · **Deadline:** Jul 9, 2026

## Code & deployment

- [ ] Push repo to GitHub: `https://github.com/ashokbugude/idbi-prospect-assist`
- [ ] Deploy to Render (or Railway) using `render.yaml` / `Dockerfile`
- [ ] Verify public URL loads dashboard and `/api/health` returns `ml_ready: true`
- [ ] Test RM CSV export: `/api/rm-queue/export`
- [ ] Test sandbox stub: `/api/sandbox/IDBI-L00001`

## Hack2skill platform (manual)

- [ ] Submit POC form with deployment URL + GitHub link
- [ ] Upload mandatory PPT PDF (use `docs/PRESENTATION_OUTLINE.md` → export to PDF)
- [ ] Complete Startup Information form (5 fields)

## Local validation before submit

```powershell
cd C:\Users\ashok\Projects\idbi-prospect-assist
.\.venv\Scripts\activate
python -m app.data_generator
python scripts/train_model.py
python scripts/validate.py
python -m pytest tests/ -v
uvicorn app.main:app --reload --port 8000
```

## Render deploy steps

1. Create repo on GitHub and push `main`
2. [render.com](https://render.com) → New → Blueprint → connect repo
3. Render reads `render.yaml` and builds Docker image (trains ML on build)
4. Copy the `*.onrender.com` URL for Hack2skill submission

## What judges see

| Capability | Endpoint / page |
|------------|-----------------|
| RM priority queue | `/` |
| Explainability | `/customer/{id}` |
| Architecture | `/architecture` |
| 30%+ quality conversion story | `/api/impact` |
| Multi-bank holistic view | `/api/multi-bank` |
| CSV for RMs | `/api/rm-queue/export` |
| Sandbox integration stub | `/api/sandbox/{id}` |
