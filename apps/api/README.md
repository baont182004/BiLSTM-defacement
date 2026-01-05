# Deface Watcher API

## Chạy ứng dụng
Dev (từ root):
```powershell
$env:PYTHONPATH="apps/api/src"
flask --app deface_watcher.web run --host 0.0.0.0 --port 5000 --no-reload
```

Dev (từ `apps/api`):
```powershell
$env:PYTHONPATH="src"
flask --app deface_watcher.web run --host 0.0.0.0 --port 5000 --no-reload
```

Prod:
```powershell
$env:PYTHONPATH="apps/api/src"
$env:PORT=5000
gunicorn -w 2 -b 0.0.0.0:$env:PORT deface_watcher.wsgi:app
```

## Endpoints
- `GET /` UI dashboard
- `GET /health` health check
- `POST /predict` JSON `{ "url": "..." }`

Response trả về thường bao gồm:
`status`, `probability`, `checked_url`, `source`, `scrape_time_ms`, `predict_time_ms`.

## Biến môi trường
- `MODEL_PATH`, `TOKENIZER_PATH`, `SCRAPER_JS_PATH`
- `MAX_CHARS` (mặc định `20000`)
- `PROCESS_TIMEOUT`, `REQUEST_TIMEOUT`
- `STRICT_EMPTY_TEXT=1` để trả về "Không có dữ liệu" khi text rỗng
- `RETURN_TOKENS=1` để trả về `tokenized_sequence`
- `LOG_LEVEL` (mặc định `INFO`)
- `REQUEST_UA` (ghi đè User-Agent cho requests)

Ghi chú:
- Flask debug reloader có thể chạy hai process. Dùng `--no-reload` để tránh load 2 lần.

## Smoke test
```powershell
$env:PYTHONPATH="apps/api/src"
python apps/api/smoke_test.py
```
