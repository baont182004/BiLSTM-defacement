# Deface Watcher API

API nà̀y phục vụ trang web và endpoint dự đoán defacement. Mục tiêu là chạy được nhanh, dễ kiểm tra.

## Chạy nhanh
Dev (từ root repo, không cần PYTHONPATH):
```powershell
python -m apps.api.dev
```

Prod (Gunicorn, từ root repo):
```powershell
$env:PORT=8000
gunicorn -w 2 -b 0.0.0.0:$env:PORT apps.api.wsgi:app
```

## Endpoint
- `GET /` giao diện UI
- `GET /health` healthcheck
- `POST /predict` nhận JSON: `{ "url": "https://example.com" }`

Response thường bao gồm:
`status`, `probability`, `checked_url`, `source`, `scrape_time_ms`, `predict_time_ms`.

## Biến môi trường
- `MODEL_PATH` đường dẫn model Keras
- `TOKENIZER_PATH` đường dẫn tokenizer
- `SCRAPER_JS_PATH` đường dẫn script Puppeteer
- `MAX_CHARS` (mặc định 20000)
- `PROCESS_TIMEOUT`, `REQUEST_TIMEOUT`
- `STRICT_EMPTY_TEXT=1` trả về “Không có dữ liệu” khi text rỗng
- `RETURN_TOKENS=1` trả về `tokenized_sequence`
- `LOG_LEVEL` (mặc định WARNING)
- `PORT` cổng chạy (mặc định 8000)

## Smoke test
```powershell
python apps/api/smoke_test.py
```

## Gợi ý kiểm tra nhanh
```bash
curl http://127.0.0.1:8000/health
```
