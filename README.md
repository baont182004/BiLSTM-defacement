# Web Defacement Detection (BiLSTM)

## Muc luc
- Gioi thieu
- Cau truc repo
- Yeu cau he thong
- Cai dat
- Chay pipeline huan luyen
- Chay API Web (Flask)
- Chay production (Gunicorn)
- Cau hinh bien moi truong
- Troubleshooting
- Quy tac du lieu va git

## Gioi thieu
Du an giai quyet bai toan phat hien web defacement bang mo hinh BiLSTM dua tren van ban trich xuat tu URL. Du lieu van ban duoc thu thap bang Puppeteer (trong truong hop trang can JavaScript) va fallback sang requests khi can. Pipeline huan luyen gom 3 buoc: extract -> tokenize -> train, va cung cap API `/predict` de phan loai.

## Cau truc repo
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

## Yeu cau he thong
- Python 3.10+ (khuyen nghi)
- Node.js 18+ (khuyen nghi) de chay Puppeteer
- Windows/Linux: Puppeteer se tu tai Chromium khi `npm ci`. Neu bi chan tai ve hoac chay tren server khong co GUI, can cau hinh lai Puppeteer/Chromium cho phu hop.

## Cai dat
Tao moi truong Python va cai dependencies cho API (dung chung cho training):
```powershell
python -m venv .venv
.venv\Scripts\activate
cd apps/api
pip install -r requirements.txt
```

Cai dependencies cho scraper:
```powershell
cd tools/scraper
npm ci
```

Neu ban su dung Linux/macOS:
```bash
python -m venv .venv
source .venv/bin/activate
cd apps/api
pip install -r requirements.txt
```

## Chay pipeline huan luyen
Chay tu root cua repo.

### 1) Step 1: Cao du lieu
```powershell
python ml/training/step1_extract_text.py
```
Input:
- `ml/data/urls/normal_url.txt`
- `ml/data/urls/defacement_url.txt`

Output:
- `ml/data/raw/rawData.json`

Ghi chu: buoc nay uu tien Puppeteer (`tools/scraper/get_text_puppeteer.js`) va fallback sang requests neu can.

### 2) Step 2: Tokenize/tien xu ly
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

## Chay API Web (Flask)
Dev (tu root):
```powershell
$env:PYTHONPATH="apps/api/src"
flask --app deface_watcher.web run --host 0.0.0.0 --port 5000 --no-reload
```

Dev (tu `apps/api`):
```powershell
$env:PYTHONPATH="src"
flask --app deface_watcher.web run --host 0.0.0.0 --port 5000 --no-reload
```

Smoke test:
```powershell
$env:PYTHONPATH="apps/api/src"
python apps/api/smoke_test.py
```

Goi API bang curl:
```bash
curl -X POST http://127.0.0.1:5000/predict \
  -H "Content-Type: application/json" \
  -d "{\"url\":\"https://example.com\"}"
```

## Chay production (Gunicorn)
Tu `apps/api`:
```powershell
$env:PYTHONPATH="src"
$env:PORT=5000
gunicorn -w 2 -b 0.0.0.0:$env:PORT deface_watcher.wsgi:app
```

Tu root:
```powershell
$env:PYTHONPATH="apps/api/src"
$env:PORT=5000
gunicorn -w 2 -b 0.0.0.0:$env:PORT deface_watcher.wsgi:app
```

## Cau hinh bien moi truong
Bien duoc doc boi API:
- `MODEL_PATH` (mac dinh `ml/artifacts/bilstm_defacement_model.keras`)
- `TOKENIZER_PATH` (mac dinh `ml/artifacts/tokenizer.json`)
- `SCRAPER_JS_PATH` (mac dinh `tools/scraper/get_text_puppeteer.js`)
- `MAX_CHARS` (mac dinh `20000`)
- `PROCESS_TIMEOUT` (mac dinh `30`, giay)
- `REQUEST_TIMEOUT` (mac dinh `15`, giay)
- `STRICT_EMPTY_TEXT` (neu `1` se tra ve "Khong co du lieu" khi text rong)
- `RETURN_TOKENS` (neu `1` se tra ve `tokenized_sequence` trong response)
- `LOG_LEVEL` (mac dinh `INFO`)
- `REQUEST_UA` (ghi de User-Agent cho requests)

Ghi chu:
- `MAX_LENGTH` hien la 128 va duoc hard-code trong `ml/training/step2_tokenize_data.py`,
  `ml/training/step3_train_model.py` va `apps/api/src/deface_watcher/config.py`.
- Repo khong su dung `NODE_SCRIPT_PATH`. Neu tai lieu cu nhac bien nay thi hay su dung `SCRAPER_JS_PATH`.

Vi du dat bien tren Windows:
```powershell
$env:MODEL_PATH="d:\\ATWebCSDL\\BiLSTM-defacement\\ml\\artifacts\\bilstm_defacement_model.keras"
$env:TOKENIZER_PATH="d:\\ATWebCSDL\\BiLSTM-defacement\\ml\\artifacts\\tokenizer.json"
$env:SCRAPER_JS_PATH="d:\\ATWebCSDL\\BiLSTM-defacement\\tools\\scraper\\get_text_puppeteer.js"
$env:PROCESS_TIMEOUT=45
$env:REQUEST_TIMEOUT=20
```

Vi du dat bien tren Linux/macOS:
```bash
export MODEL_PATH="/path/to/ml/artifacts/bilstm_defacement_model.keras"
export TOKENIZER_PATH="/path/to/ml/artifacts/tokenizer.json"
export SCRAPER_JS_PATH="/path/to/tools/scraper/get_text_puppeteer.js"
export PROCESS_TIMEOUT=45
export REQUEST_TIMEOUT=20
```

## Troubleshooting
- Khong co Node.js: buoc extract se fail khi goi Puppeteer; fallback requests co the hoat dong nhung ket qua co the thieu noi dung.
- Puppeteer bi chan/timeout: thu tang `PROCESS_TIMEOUT`, giam `MAX_WORKERS` (o step1) hoac chay tren may co ket noi on dinh.
- Trang web JS-heavy: requests khong lay duoc noi dung, can Puppeteer va Chromium.
- Flask debug load 2 lan: su dung `--no-reload` de tranh chay 2 process.

## Quy tac du lieu va git
- `node_modules/`, `__pycache__/`, `*.npy` thuong khong commit.
- `ml/data/raw/rawData.json` co the rat lon, nen xem xet truoc khi commit.
- `ml/data/urls/*.txt` co the bo qua neu khong muon chia se danh sach URL.
