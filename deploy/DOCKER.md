# Docker Deploy Guide

## Prereqs

- Docker Desktop (Windows) with WSL2 enabled.

## Environment

Create `.env` from `.env.example` and adjust as needed:

- `PORT` (default 8000)
- `PUBLIC_PORT` (default 8080)
- `WEB_CONCURRENCY` (default 2)
- `MODEL_PATH`, `TOKENIZER_PATH`, `SCRAPER_JS_PATH`

## Dev

```bash
docker compose -f deploy/docker-compose.yml up --build
```

## Prod

```bash
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml up --build -d
```

## Health check

```bash
curl http://localhost:${PUBLIC_PORT:-8080}/health
```

## Predict

```bash
curl -X POST http://localhost:${PUBLIC_PORT:-8080}/predict \
  -H "Content-Type: application/json" \
  -d "{\"url\":\"https://example.com\"}"
```
