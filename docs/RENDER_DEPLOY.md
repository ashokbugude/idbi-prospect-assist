# Deploy to Render (free tier)

**Use this instead of Hugging Face** — HF Docker Spaces require a paid plan. Render free tier works with our existing `Dockerfile` and `render.yaml`.

## 1. Push code to GitHub

```powershell
cd C:\Users\ashok\Projects\idbi-prospect-assist
git add .
git commit -m "Configure Render free deployment"
git push origin main
```

## 2. Create Render service

1. Go to [render.com](https://render.com) and sign up / log in (GitHub login is easiest)
2. **New +** → **Blueprint**
3. Connect repository `ashokbugude/idbi-prospect-assist`
4. Render reads `render.yaml` and creates the web service
5. Click **Apply** — first Docker build takes **~8–15 minutes** (trains ML model on build)

## 3. Live URL

After deploy succeeds:

```
https://idbi-prospect-assist.onrender.com
```

(Your URL may differ slightly — copy it from the Render dashboard.)

## 4. Update demo URL in app (optional)

In Render dashboard → your service → **Environment**:

| Key | Value |
|-----|-------|
| `PUBLIC_DEMO_URL` | `https://idbi-prospect-assist.onrender.com` |
| `RM_DEMO_PIN` | `idbi2026` |

Save — Render redeploys automatically.

## 5. Verify

```powershell
curl https://idbi-prospect-assist.onrender.com/api/health
```

Expected:

```json
{"status":"ok","version":"0.7.0","ml_ready":true,"deploy_platform":"render",...}
```

Open in browser → `/login` → PIN `idbi2026`

## 6. Regenerate submission PPT

```powershell
$env:PUBLIC_DEMO_URL="https://idbi-prospect-assist.onrender.com"
python scripts/update_submission_ppt.py
```

## Free tier notes

- Service **spins down after ~15 min idle** — first visit after sleep takes **30–90 seconds** (cold start)
- **750 free instance hours/month** — enough for hackathon demo + judging
- No credit card required for free tier (as of 2026)

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Build fails on ML train | Check Render build logs; ensure `scripts/train_model.py` completes |
| 502 on first load | Wait 60s — cold start waking up |
| Health check fails | Confirm `/api/health` returns 200 after warm-up |

## Hugging Face alternative?

HF **Docker Spaces are paid**. HF Gradio/Streamlit would require rewriting the app — not recommended. **Render is the best free fit** for this FastAPI + Jinja2 POC.
