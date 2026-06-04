# syntax=docker/dockerfile:1.7

FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
ARG VITE_BACKEND_URL=
ENV VITE_BACKEND_URL=$VITE_BACKEND_URL
RUN npm run build

FROM python:3.11-slim AS app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --index-url https://download.pytorch.org/whl/cpu "torch>=2.2" \
    && pip install -r backend/requirements.txt

COPY backend backend
COPY scripts scripts
COPY sample_data sample_data
COPY --from=frontend-builder /app/frontend/dist backend/static_dist

RUN mkdir -p backend/data backend/storage backend/data/feedback certs

EXPOSE 8000 8443

CMD ["python", "scripts/run_backend_single.py", "--host", "0.0.0.0", "--port", "8000"]
