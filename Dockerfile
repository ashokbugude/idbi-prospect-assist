FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts

RUN python -m app.data_generator && python scripts/train_model.py

ENV PORT=8000
ENV PYTHONUNBUFFERED=1
ENV DEPLOY_PLATFORM=render

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
