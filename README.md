# Web Defacement Detection (BiLSTM)

Ứng dụng học máy phát hiện tấn công thay đổi giao diện (defacement) từ nội dung trang web sử dụng đặc trưng văn bản thuần. Mô hình dùng BiLSTM, dữ liệu lấy từ các URL: defacement thu thập từ Zone-H, normal là các website thông thường.

## Quy trình dự án

1. Lọc URL: tổng hợp và làm sạch danh sách `defacement` (Zone-H) và `normal`.
2. Step 1 – Cào dữ liệu: trích xuất văn bản từ URL (ưu tiên Puppeteer, fallback sang requests).
3. Step 2 – Tiền xử lý & tokenize: làm sạch dữ liệu và tạo tập train/valid/test.
4. Step 3 – Huấn luyện: train BiLSTM, xuất model và tokenizer.
5. Chạy ứng dụng: API nhận URL, trích xuất text, dự đoán và trả kết quả.

## Cách sử dụng mô hình

1. Tạo 2 file url:
   - `ml/data/urls/defacement_url.txt` (zone-H, có công cụ hỗ trợ cào với file scraper_final.js)
   - `ml/data/urls/normal_url.txt` (các web thông thường)
2. Chạy Step 1, 2, 3 theo thứ tự raw/processed và artifacts.

## Cách chạy nhanh (local)

Dev:

```powershell
python -m apps.api.dev
```

Prod (Gunicorn):

```powershell
$env:PORT=8000
gunicorn -w 2 -b 0.0.0.0:$env:PORT apps.api.wsgi:app
```

## Docker (khuyến nghị)

Dev:

```bash
docker compose -f deploy/docker-compose.yml up --build
```

Prod:

```bash
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml up --build -d
```

Tài liệu Docker chi tiết: `deploy/DOCKER.md`.

## Lưu ý ngắn

- Kết quả phụ thuộc vào chất lượng URL đầu vào (defacement/normal).
- Nếu cần tuỳ biến, chỉ cần quan tâm `PORT` và đường dẫn model/tokenizer.
