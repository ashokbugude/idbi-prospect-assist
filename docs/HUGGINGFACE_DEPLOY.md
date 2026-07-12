# Hugging Face Spaces — not available on free tier

Hugging Face **Docker Spaces require a paid plan** on current HF accounts. This FastAPI app cannot run on free Gradio/Static SDKs without a full rewrite.

## Use Render instead (free)

See **`docs/RENDER_DEPLOY.md`** for step-by-step deployment.

```
https://idbi-prospect-assist.onrender.com
```

## If you get HF paid later

Files `README.hf.md` and port `7860` Dockerfile variant are kept for reference — switch `DEPLOY_PLATFORM=huggingface` and use `README.hf.md` as the Space README.
