# -*- coding: utf-8 -*-
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
MODEL_FILE = 'bilstm_defacement_model.keras' # Đảm bảo dùng model tốt nhất
TOKENIZER_FILE = 'tokenizer.json'
# Tệp JS phụ trợ để cào dữ liệu (đã sửa để trả về JSON)
SCRAPER_JS_FILE = 'get_text_puppeteer.js'
MAX_LENGTH = 128
PROCESS_TIMEOUT = 30 # Timeout cho Puppeteer (giây)
REQUEST_TIMEOUT = 10 # Timeout cho Requests (giây)
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# --- 1. Tải "Bộ não" & "Từ điển" ---
print(" * Đang tải mô hình BiLSTM (Bộ phân loại)...")
# Kiểm tra sự tồn tại của tệp model trước khi tải
if not os.path.exists(MODEL_FILE):
    print(f"LỖI NGHIÊM TRỌNG: Không tìm thấy tệp mô hình '{MODEL_FILE}'. Dừng lại.")
    exit()
model = load_model(MODEL_FILE)

print(" * Đang tải Tokenizer (Từ điển)...")
# Kiểm tra sự tồn tại của tệp tokenizer trước khi tải
if not os.path.exists(TOKENIZER_FILE):
    print(f"LỖI NGHIÊM TRỌNG: Không tìm thấy tệp từ điển '{TOKENIZER_FILE}'. Dừng lại.")
    exit()

# === ĐOẠN MÃ ĐÃ SỬA ĐỂ ĐỌC TOKENIZER ===
try:
    with open(TOKENIZER_FILE, 'r', encoding='utf-8') as f:
        # 1. Đọc file JSON bên ngoài, lấy ra chuỗi JSON bên trong (do bị mã hóa kép)
        tokenizer_data_string = json.load(f)

        # 2. Đưa thẳng chuỗi JSON đó cho hàm của Keras.
        #    Hàm này sẽ tự giải mã chuỗi đó.
        tokenizer = tokenizer_from_json(tokenizer_data_string)

except json.JSONDecodeError as e:
    # Xử lý trường hợp file tokenizer.json KHÔNG bị lồng (dự phòng)
    print(f"LƯU Ý: Tệp {TOKENIZER_FILE} không phải JSON lồng. Đang thử đọc trực tiếp...")
    try:
        with open(TOKENIZER_FILE, 'r', encoding='utf-8') as f:
            tokenizer_data_string_direct = f.read()
            # Đưa chuỗi đọc trực tiếp cho hàm Keras
            tokenizer = tokenizer_from_json(tokenizer_data_string_direct)
    except Exception as e2:
        print(f"LỖI NGHIÊM TRỌNG: Không thể đọc tệp tokenizer theo cả hai cách: {e2}")
        exit()
except Exception as e:
    print(f"LỖI NGHIÊM TRỌNG khi tải tokenizer: {e}")
    exit()
# ===============================================

print(" * Máy chủ Deface Watcher đã sẵn sàng!")

app = Flask(__name__)

# --- 2. Logic Cào dữ liệu (Hybrid, xử lý JSON từ JS) ---

# Phương pháp 1 (Ưu tiên): Gọi Node.js/Puppeteer, nhận JSON {text, html, screenshot?}
def extract_data_primary(url):
    """Gọi get_text_puppeteer.js và trả về (text, html) hoặc None nếu lỗi."""
    try:
        command = ['node', SCRAPER_JS_FILE, url]
        result = subprocess.run(
            command, capture_output=True, text=True, encoding='utf-8',
            timeout=PROCESS_TIMEOUT, check=False # check=False để không báo lỗi nếu returncode != 0
        )
        try:
            # Luôn cố gắng parse output, ngay cả khi có lỗi return code
            output_data = json.loads(result.stdout.strip())
            if 'error' in output_data:
                 # Nếu JSON chứa lỗi rõ ràng từ JS
                 print(f"  -> Puppeteer báo lỗi: {output_data['error']}")
                 return None, None # Báo hiệu thất bại
            # Trả về text và html (screenshot bị bỏ qua vì không dùng)
            return output_data.get('text'), output_data.get('html')
        except json.JSONDecodeError:
             # Nếu JS không in ra JSON hợp lệ (ví dụ: lỗi crash không mong muốn)
             stderr_output = result.stderr.strip() if result.stderr else "Không có stderr."
             print(f"  -> Lỗi: Puppeteer không trả về JSON. Return Code: {result.returncode}. Stderr: {stderr_output}. Output: {result.stdout.strip()[:100]}...")
             return None, None # Báo hiệu thất bại
    except FileNotFoundError:
        print("LỖI: Không tìm thấy lệnh 'node'. Bạn đã cài đặt Node.js và thêm vào PATH chưa?")
        return None, None
    except subprocess.TimeoutExpired:
        print(f"  -> Puppeteer thất bại: Quá trình vượt quá {PROCESS_TIMEOUT} giây.")
        return None, None
    except Exception as e:
        print(f"Lỗi không mong muốn khi gọi subprocess: {e}")
        return None, None

# Phương pháp 2 (Dự phòng): Requests + BeautifulSoup, trả về (text, html)
def extract_data_fallback(url):
    """Sử dụng requests để lấy text và html, trả về (text, html) hoặc (None, None)."""
    try:
        response = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT, verify=False)
        response.raise_for_status() # Ném lỗi nếu mã trạng thái là 4xx hoặc 5xx
        html_content = response.text # Lấy HTML gốc
        soup = BeautifulSoup(html_content, 'html.parser')
        # Loại bỏ script và style trước khi lấy text
        for script_or_style in soup(["script", "style"]):
            script_or_style.decompose()
        raw_text = soup.get_text()
        cleaned_text = " ".join(raw_text.split()).strip() # Chuẩn hóa khoảng trắng
        return cleaned_text, html_content # Trả về cả hai
    except requests.exceptions.RequestException as e: # Bắt lỗi cụ thể của requests
        print(f"  -> 'curl' (requests) thất bại: {e}")
        return None, None # Trả về None cho cả hai
    except Exception as e: # Bắt các lỗi khác (ví dụ: từ BeautifulSoup)
        print(f"  -> Lỗi khi xử lý fallback request: {e}")
        return None, None

# --- 3. Tokenization (Giữ nguyên) ---
def preprocess_text(text):
    """Chuyển đổi văn bản thành chuỗi số đã đệm."""
    # texts_to_sequences nhận vào một list các văn bản
    sequence = tokenizer.texts_to_sequences([text])
    # pad_sequences nhận vào list các chuỗi số
    padded_sequence = pad_sequences(sequence, maxlen=MAX_LENGTH, padding='post', truncating='post')
    # Trả về mảng NumPy gốc (vì model.predict cần NumPy array)
    return padded_sequence

# --- 4. Định tuyến (Routing) ---
@app.route('/')
def home():
    """Hiển thị trang chính (index.html)."""
    return render_template('index.html', app_name="DEFACE WATCHER")

@app.route('/predict', methods=['POST'])
def predict_api():
    """API endpoint để xử lý yêu cầu dự đoán."""
    start_api_time = time.time()
    text = "" # Khởi tạo text
    html_content = "" # Khởi tạo html
    source = "Không xác định"
    scrape_duration = 0
    # Khởi tạo chuỗi token rỗng (dạng list để gửi JSON)
    padded_sequence_list = [0] * MAX_LENGTH

    try:
        # Lấy URL từ request JSON
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({'error': 'Dữ liệu JSON không hợp lệ hoặc thiếu URL.'}), 400
        url = data['url']
        # Thêm http:// nếu người dùng quên
        if not url.startswith(('http://', 'https://')):
             url = 'http://' + url

        print(f"\n[{time.strftime('%H:%M:%S')}] Nhận yêu cầu kiểm tra: {url}")

        # === LOGIC HYBRID ĐỂ CÀO DỮ LIỆU ===
        print("  -> Đang thử Phương pháp 1 (Ưu tiên - Puppeteer)...")
        scrape_start_time = time.time()
        text_primary, html_primary = extract_data_primary(url)
        scrape_end_time = time.time()
        scrape_duration = (scrape_end_time - scrape_start_time) * 1000

        if text_primary is not None: # Chỉ cần text không phải None là thành công
            text, html_content = text_primary, html_primary if html_primary else ""
            source = "Puppeteer (JS)"
            print(f"  -> Cào thành công (bằng {source}) trong {scrape_duration:.0f} ms.")
        else:
            print(f"  -> Thất bại sau {scrape_duration:.0f} ms. Đang thử Phương pháp 2 (Dự phòng - 'curl')...")
            scrape_start_time = time.time()
            text_fallback, html_fallback = extract_data_fallback(url)
            scrape_end_time = time.time()
            scrape_duration = (scrape_end_time - scrape_start_time) * 1000
            source = "Requests (curl)"

            if text_fallback is None: # Nếu cả hai đều thất bại
                print(f"  -> Cả hai phương pháp đều thất bại sau {scrape_duration:.0f} ms.")
                return jsonify({'error': 'Không thể cào dữ liệu từ URL này (bị chặn/timeout/lỗi).'}), 400
            else:
                 text, html_content = text_fallback, html_fallback if html_fallback else ""
                 print(f"  -> Cào thành công (bằng {source}) trong {scrape_duration:.0f} ms.")
        # === KẾT THÚC LOGIC HYBRID ===

        # === Xử lý văn bản và Dự đoán ===
        final_status = ""
        final_probability = 0.0
        predict_duration = 0

        # Luôn thực hiện tokenization, ngay cả khi text rỗng
        # Đảm bảo text là string trước khi token hóa
        text_to_tokenize = text if isinstance(text, str) else ""
        processed_text_vector = preprocess_text(text_to_tokenize)
        # Chuyển đổi mảng NumPy thành list để gửi qua JSON
        padded_sequence_list = processed_text_vector[0].tolist()

        if not text_to_tokenize: # Nếu không có văn bản nào được trích xuất
            print("  -> Không tìm thấy văn bản thuần túy.")
            # Kiểm tra xem HTML gốc có thẻ <img> không
            if html_content and '<img' in html_content.lower():
                print("  -> Phát hiện thẻ <img> trong HTML.")
                final_status = "Nghi ngờ Deface (Chỉ hình ảnh)"
                final_probability = 0.90 # Gán xác suất cao giả định
                source += " - (Phát hiện ảnh)"
            else:
                # Nếu không có text và không có ảnh, coi là Bình thường
                print("  -> Không có text/ảnh, dự đoán là Bình thường.")
                final_status = "Bình thường"
                final_probability = 0.00 # Xác suất deface = 0
                source += " - (Trang rỗng)"
        else:
            # Nếu có văn bản, tiến hành dự đoán bằng mô hình BiLSTM
            print(f"  -> Tìm thấy {len(text_to_tokenize)} ký tự. Đang dự đoán bằng BiLSTM...")
            predict_start_time = time.time()
            # Sử dụng verbose=0 để tắt log từng bước dự đoán của TensorFlow
            prediction = model.predict(processed_text_vector, verbose=0)
            predict_end_time = time.time()
            predict_duration = (predict_end_time - predict_start_time) * 1000 # ms

            # Diễn giải kết quả dự đoán từ softmax
            final_probability = prediction[0][1] # Xác suất của lớp 1 (Deface)
            predicted_class_index = np.argmax(prediction, axis=1)[0] # Lấy index của lớp có xác suất cao nhất
            final_status = "Tấn công Deface" if predicted_class_index == 1 else "Bình thường"
            source += " - (Dự đoán BiLSTM)"
            print(f"  -> Thời gian dự đoán: {predict_duration:.0f} ms")


        total_api_time = (time.time() - start_api_time) * 1000 # ms
        print(f"  -> Kết quả cuối cùng: {final_status} (Xác suất Deface: {final_probability:.2f})")
        print(f"  -> Tổng thời gian xử lý API: {total_api_time:.0f} ms")

        # === TRẢ VỀ KẾT QUẢ CHO FRONTEND ===
        return jsonify({
            'status': final_status,
            'probability': float(final_probability),
            'extracted_text': text_to_tokenize or '(Không tìm thấy văn bản)', # Đảm bảo trả về string
            'tokenized_sequence': padded_sequence_list, # Trả về list các số nguyên
            'checked_url': url,
            'source': source,
            'scrape_time_ms': round(scrape_duration),
            'predict_time_ms': round(predict_duration),
        })
    # Bắt lỗi chung và trả về lỗi 500
    except Exception as e:
        # Ghi log lỗi chi tiết hơn ở server
        import traceback
        print(f"Lỗi máy chủ nghiêm trọng tại endpoint /predict: {e}")
        print(traceback.format_exc()) # In traceback để debug
        return jsonify({'error': f'Lỗi máy chủ không mong muốn: {str(e)}'}), 500

# --- 5. Chạy máy chủ ---
if __name__ == '__main__':
    # Tắt cảnh báo SSL từ requests
    warnings.filterwarnings('ignore', message='Unverified HTTPS request')
    # Chạy trên tất cả các IP (0.0.0.0), port 5000, bật chế độ debug
    app.run(host='0.0.0.0', port=5000, debug=True)