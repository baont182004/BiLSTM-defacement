# Web Defacement Detection (BiLSTM)

## Mục lục
- Giới thiệu
- Cấu trúc repo
- Yêu cầu hệ thống
- Cài đặt
- Chạy pipeline huấn luyện
- Chạy API Web (Flask)
- Chạy production (Gunicorn)
- Cấu hình biến môi trường
- Troubleshooting
- Quy tắc dữ liệu và git

## Giới thiệu
Dự án phát hiện web defacement bằng BiLSTM dựa trên văn bản trích xuất từ URL. Dữ liệu được thu thập bằng Puppeteer (phù hợp với trang cần JavaScript) và fallback sang requests khi cần. Pipeline huấn luyện gồm 3 bước: extract -> tokenize -> train; API `/predict` dùng để phân loại URL.

## Cấu trúc repo
- API (deploy web): `apps/api/`
  - Flask app, services, templates, static: `apps/api/src/deface_watcher/`
  - WSGI entry: `apps/api/wsgi.py`
  - Dependencies: `apps/api/requirements.txt`
  - Smoke test: `apps/api/smoke_test.py`
- ML (data + training): `ml/`
  - `ml/training/step1_extract_text.py`
  - `ml/training/step2_tokenize_data.py`
  - `ml/training/step3_train_model.py`
  - `ml/data/urls/{normal_url.txt, defacement_url.txt, filter_urls.py}`
  - `ml/data/raw/rawData.json`
  - `ml/data/processed/*.npy`
  - `ml/artifacts/{bilstm_defacement_model.keras, tokenizer.json, training_history.png, ...}`
- Scraper (Puppeteer): `tools/scraper/`
  - `tools/scraper/get_text_puppeteer.js`
  - `tools/scraper/package.json`, `tools/scraper/package-lock.json`

## Yêu cầu hệ thống
- Python 3.10+ (khuyến nghị)
- Node.js 18+ (khuyến nghị) để chạy Puppeteer
- Windows/Linux: Puppeteer sẽ tự tải Chromium khi `npm ci`. Nếu bị chặn tải về hoặc chạy trên server không có GUI, cần cấu hình lại Puppeteer/Chromium cho phù hợp.

## Cài đặt
Tạo môi trường Python và cài dependencies cho API (dùng chung cho training):
```powershell
python -m venv .venv
.venv\Scripts\activate
cd apps/api
pip install -r requirements.txt
```

Cài dependencies cho scraper:
```powershell
cd tools/scraper
npm ci
```

Nếu dùng Linux/macOS:
```bash
python -m venv .venv
source .venv/bin/activate
cd apps/api
pip install -r requirements.txt
```

## Chạy pipeline huấn luyện
Chạy từ root của repo.

### 1) Step 1: Cào dữ liệu
```powershell
python ml/training/step1_extract_text.py
```
Input:
- `ml/data/urls/normal_url.txt`
- `ml/data/urls/defacement_url.txt`

Output:
- `ml/data/raw/rawData.json`

Ghi chú: bước này ưu tiên Puppeteer (`tools/scraper/get_text_puppeteer.js`) và fallback sang requests nếu cần.

### 2) Step 2: Tokenize/tiền xử lý
```powershell
python ml/training/step2_tokenize_data.py
```
Input:
- `ml/data/raw/rawData.json`

Output:
- `ml/data/processed/X_train.npy`, `y_train.npy`
- `ml/data/processed/X_valid.npy`, `y_valid.npy`
- `ml/data/processed/X_test.npy`, `y_test.npy`
- `ml/artifacts/tokenizer.json`

### 3) Step 3: Train BiLSTM
```powershell
python ml/training/step3_train_model.py
```
Input:
- `ml/data/processed/X_train.npy`, `y_train.npy`
- `ml/data/processed/X_valid.npy`, `y_valid.npy`
- `ml/data/processed/X_test.npy`, `y_test.npy`

Output:
- `ml/artifacts/bilstm_defacement_model.keras`
- `ml/artifacts/training_history.png`
- `ml/artifacts/metrics_report.json`
- `ml/artifacts/decision.json`
- `ml/artifacts/calibration.json`
- `ml/artifacts/roc_curve.png`, `ml/artifacts/pr_curve.png`

## Chạy API Web (Flask)
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

Smoke test:
```powershell
$env:PYTHONPATH="apps/api/src"
python apps/api/smoke_test.py
```

Gọi API bằng curl:
```bash
curl -X POST http://127.0.0.1:5000/predict \
  -H "Content-Type: application/json" \
  -d "{\"url\":\"https://example.com\"}"
```

## Chạy production (Gunicorn)
Từ `apps/api`:
```powershell
$env:PYTHONPATH="src"
$env:PORT=5000
gunicorn -w 2 -b 0.0.0.0:$env:PORT deface_watcher.wsgi:app
```

Từ root:
```powershell
$env:PYTHONPATH="apps/api/src"
$env:PORT=5000
gunicorn -w 2 -b 0.0.0.0:$env:PORT deface_watcher.wsgi:app
```

## Cấu hình biến môi trường
Biến được đọc bởi API:
- `MODEL_PATH` (mặc định `ml/artifacts/bilstm_defacement_model.keras`)
- `TOKENIZER_PATH` (mặc định `ml/artifacts/tokenizer.json`)
- `SCRAPER_JS_PATH` (mặc định `tools/scraper/get_text_puppeteer.js`)
- `MAX_CHARS` (mặc định `20000`)
- `PROCESS_TIMEOUT` (mặc định `30`, giây)
- `REQUEST_TIMEOUT` (mặc định `15`, giây)
- `STRICT_EMPTY_TEXT` (nếu `1` sẽ trả về "Không có dữ liệu" khi text rỗng)
- `RETURN_TOKENS` (nếu `1` sẽ trả về `tokenized_sequence` trong response)
- `LOG_LEVEL` (mặc định `INFO`)
- `REQUEST_UA` (ghi đè User-Agent cho requests)

Ghi chú:
- `MAX_LENGTH` hiện là 128 và được hard-code trong `ml/training/step2_tokenize_data.py`,
  `ml/training/step3_train_model.py` và `apps/api/src/deface_watcher/config.py`.
- Repo không dùng `NODE_SCRIPT_PATH`. Nếu tài liệu cũ nhắc biến này thì hãy dùng `SCRAPER_JS_PATH`.

Ví dụ đặt biến trên Windows:
```powershell
$env:MODEL_PATH="ml\\artifacts\\bilstm_defacement_model.keras"
$env:TOKENIZER_PATH="ml\\artifacts\\tokenizer.json"
$env:SCRAPER_JS_PATH="tools\\scraper\\get_text_puppeteer.js"
$env:PROCESS_TIMEOUT=45
$env:REQUEST_TIMEOUT=20
```

Ví dụ đặt biến trên Linux/macOS:
```bash
export MODEL_PATH="ml/artifacts/bilstm_defacement_model.keras"
export TOKENIZER_PATH="ml/artifacts/tokenizer.json"
export SCRAPER_JS_PATH="tools/scraper/get_text_puppeteer.js"
export PROCESS_TIMEOUT=45
export REQUEST_TIMEOUT=20
```

## Troubleshooting
- Không có Node.js: bước extract sẽ fail khi gọi Puppeteer; fallback requests có thể hoạt động nhưng kết quả có thể thiếu nội dung.
- Puppeteer bị chặn/timeout: thử tăng `PROCESS_TIMEOUT`, giảm `MAX_WORKERS` (ở step1) hoặc chạy trên máy có kết nối ổn định.
- Trang web JS-heavy: requests không lấy được nội dung, cần Puppeteer và Chromium.
- Flask debug load 2 lần: sử dụng `--no-reload` để tránh chạy 2 process.

## Quy tắc dữ liệu và git
- `node_modules/`, `__pycache__/`, `*.npy` thường không commit.
- `ml/data/raw/rawData.json` có thể rất lớn, nên xem xét trước khi commit.
- `ml/data/urls/*.txt` có thể bỏ qua nếu không muốn chia sẻ danh sách URL.
- Trong `ml/artifacts/`, chỉ commit các file `*.png` và `*.keras` để theo dõi mô hình/biểu đồ; các file khác nên bỏ qua.
