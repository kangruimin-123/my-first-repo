FROM node:22-bookworm-slim AS frontend

WORKDIR /app/frontend
COPY 主线龙头交易系统/package*.json ./
RUN npm ci
COPY 主线龙头交易系统/ ./
RUN npm run build

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY sample_data ./sample_data
COPY output ./output
COPY config.yaml run.py ./
COPY --from=frontend /app/frontend/dist ./主线龙头交易系统/dist

EXPOSE 8000

CMD ["sh", "-c", "uvicorn backend.api:app --host 0.0.0.0 --port ${PORT:-8000}"]
