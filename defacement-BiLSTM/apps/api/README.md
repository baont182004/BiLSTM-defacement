# Deface Watcher API

## Run

Dev (from repo root):
```powershell
$env:PYTHONPATH="apps/api/src"
flask --app deface_watcher.web run --port 5000 --no-reload
```

Dev (from apps/api):
```powershell
$env:PYTHONPATH="src"
flask --app deface_watcher.web run --port 5000 --no-reload
```

Prod:
```powershell
$env:PYTHONPATH="apps/api/src"
gunicorn -w 2 -b 0.0.0.0:$env:PORT deface_watcher.wsgi:app
```

## Endpoints

- `GET /` UI dashboard
- `GET /health` health check
- `POST /predict` JSON `{ "url": "..." }`

Response fields include:
`status`, `probability`, `checked_url`, `source`, `scrape_time_ms`, `predict_time_ms`.

## Environment

- `MODEL_PATH`, `TOKENIZER_PATH`, `SCRAPER_JS_PATH`
- `MAX_CHARS` (default `20000`)
- `PROCESS_TIMEOUT`, `REQUEST_TIMEOUT`
- `STRICT_EMPTY_TEXT=1` to return "Không đủ dữ liệu" on empty text
- `RETURN_TOKENS=1` to include `tokenized_sequence`
- `LOG_LEVEL` (default `INFO`)

Notes:
- Flask debug reloader can spawn two processes. Use `--no-reload` to avoid double loads in development.

## Smoke test

```powershell
$env:PYTHONPATH="apps/api/src"
python apps/api/smoke_test.py
```
