import os
import json
import numpy as np
import subprocess  # Dùng cho phương pháp chính (JS)
import requests    # Dùng cho phương pháp dự phòng (curl)
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify, render_template
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing.text import tokenizer_from_json
from tensorflow.keras.preprocessing.sequence import pad_sequences
import warnings
import time

# --- CẤU HÌNH ---
MODEL_FILE = 'bilstm_defacement_model.keras'
TOKENIZER_FILE = 'tokenizer.json'
SCRAPER_JS_FILE = 'get_text_puppeteer.js' # Tệp JS phụ trợ
MAX_LENGTH = 128
PROCESS_TIMEOUT = 30 # Timeout cho Puppeteer
REQUEST_TIMEOUT = 10 # Timeout cho Requests
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# --- 1. Tải "Bộ não" & "Từ điển" ---
print(" * Đang tải mô hình BiLSTM (Bộ phân loại)...")
model = load_model(MODEL_FILE)
print(" * Đang tải Tokenizer (Từ điển)...")
try:
    with open(TOKENIZER_FILE, 'r', encoding='utf-8') as f:
        tokenizer_data_string = json.load(f)
        tokenizer = tokenizer_from_json(tokenizer_data_string)
except Exception as e:
    print(f"LỖI NGHIÊM TRỌNG: Không thể đọc tệp tokenizer: {e}")
    exit()
print(" * Máy chủ Deface Watcher đã sẵn sàng!")

app = Flask(__name__)

# --- 2. Logic Cào dữ liệu (Hybrid) ---

# Phương pháp 1 (Ưu tiên): Gọi Node.js/Puppeteer
def extract_text_primary(url):
    try:
        command = ['node', SCRAPER_JS_FILE, url]
        result = subprocess.run(
            command, capture_output=True, text=True, encoding='utf-8',
            timeout=PROCESS_TIMEOUT, check=False # check=False để không báo lỗi nếu returncode != 0
        )
        if result.returncode != 0:
            print(f"  -> Puppeteer thất bại. Stderr: {result.stderr.strip()}")
            return None # Báo hiệu thất bại
        return result.stdout.strip()
    except FileNotFoundError:
        print("LỖI: Không tìm thấy 'node'. Bạn đã cài đặt Node.js chưa?")
        return None
    except subprocess.TimeoutExpired:
        print(f"  -> Puppeteer thất bại: Quá trình vượt quá {PROCESS_TIMEOUT} giây.")
        return None
    except Exception as e:
        print(f"Lỗi subprocess: {e}")
        return None

# Phương pháp 2 (Dự phòng): Dùng "curl" (Requests + BeautifulSoup)
def extract_text_fallback(url):
    try:
        response = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT, verify=False)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        for script_or_style in soup(["script", "style"]):
            script_or_style.decompose()
        raw_text = soup.get_text()
        return " ".join(raw_text.split()).strip()
    except Exception as e:
        print(f"  -> 'curl' (requests) cũng thất bại: {e}")
        return None

# --- 3. Tokenization (Giữ nguyên) ---
def preprocess_text(text):
    sequence = tokenizer.texts_to_sequences([text])
    padded_sequence = pad_sequences(sequence, maxlen=MAX_LENGTH, padding='post', truncating='post')
    return padded_sequence

# --- 4. Định tuyến (Routing) ---
@app.route('/')
def home():
    # Truyền tên ứng dụng vào template
    return render_template('index.html', app_name="DEFACE WATCHER")

@app.route('/predict', methods=['POST'])
def predict_api():
    start_api_time = time.time()
    try:
        data = request.get_json()
        url = data['url']

        print(f"\n[{time.strftime('%H:%M:%S')}] Nhận yêu cầu kiểm tra: {url}")

        # === LOGIC HYBRID MỚI ===
        print("  -> Đang thử Phương pháp 1 (Ưu tiên - Puppeteer)...")
        scrape_start_time = time.time()
        text = extract_text_primary(url)
        scrape_end_time = time.time()
        source = "Puppeteer (JS)"
        scrape_duration = (scrape_end_time - scrape_start_time) * 1000 # ms

        if text is None:
            print(f"  -> Thất bại sau {scrape_duration:.0f} ms. Đang thử Phương pháp 2 (Dự phòng - 'curl')...")
            scrape_start_time = time.time()
            text = extract_text_fallback(url)
            scrape_end_time = time.time()
            source = "Requests (curl)"
            scrape_duration = (scrape_end_time - scrape_start_time) * 1000 # ms

        if text is None: # Nếu cả hai đều thất bại
            print(f"  -> Cả hai phương pháp đều thất bại sau {scrape_duration:.0f} ms.")
            return jsonify({'error': 'Không thể cào dữ liệu từ URL này (bị chặn hoặc timeout ở cả hai phương pháp).'}), 400
        elif not text:
             print(f"  -> Cào thành công (trang không có văn bản) bằng {source} trong {scrape_duration:.0f} ms.")
             source += " - (Trang rỗng)"
        else:
            print(f"  -> Cào thành công (sử dụng {source}) trong {scrape_duration:.0f} ms. Độ dài text: {len(text)}")
        # === KẾT THÚC LOGIC HYBRID ===

        # 2. Tokenization
        preprocess_start_time = time.time()
        processed_text_vector = preprocess_text(text)
        preprocess_end_time = time.time()
        preprocess_duration = (preprocess_end_time - preprocess_start_time) * 1000 # ms

        # 3. Dự đoán
        predict_start_time = time.time()
        # Sử dụng verbose=0 để tắt log dự đoán của TensorFlow
        prediction = model.predict(processed_text_vector, verbose=0)
        predict_end_time = time.time()
        predict_duration = (predict_end_time - predict_start_time) * 1000 # ms

        # 4. Diễn giải kết quả
        probability_deface = prediction[0][1]
        predicted_class_index = np.argmax(prediction, axis=1)[0]
        status = "Tấn công Deface" if predicted_class_index == 1 else "Bình thường"

        total_api_time = (time.time() - start_api_time) * 1000 # ms
        print(f"  -> Tokenize: {preprocess_duration:.0f} ms | Dự đoán: {predict_duration:.0f} ms")
        print(f"  -> Kết quả: {status} (Xác suất Deface: {probability_deface:.2f})")
        print(f"  -> Tổng thời gian xử lý API: {total_api_time:.0f} ms")

        return jsonify({
            'status': status,
            'probability': float(probability_deface),
            'extracted_text': text or '(Trang không có văn bản)',
            'checked_url': url,
            'source': source,
            'scrape_time_ms': round(scrape_duration),
            'predict_time_ms': round(predict_duration)
        })
    except Exception as e:
        print(f"Lỗi máy chủ nghiêm trọng: {e}")
        return jsonify({'error': str(e)}), 500

# --- 5. Chạy máy chủ ---
if __name__ == '__main__':
    # Tắt cảnh báo SSL
    warnings.filterwarnings('ignore', message='Unverified HTTPS request')
    # Chạy trên tất cả các IP, hữu ích nếu muốn truy cập từ máy khác trong mạng LAN
    app.run(host='0.0.0.0', port=5000, debug=True)