import os
import json
import numpy as np
import subprocess 
import requests    
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify, render_template
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing.text import tokenizer_from_json
from tensorflow.keras.preprocessing.sequence import pad_sequences
import warnings
import time
import traceback # 

# --- CẤU HÌNH ---
MODEL_FILE = 'bilstm_defacement_model.keras'
TOKENIZER_FILE = 'tokenizer.json'

SCRAPER_JS_FILE = 'get_text_puppeteer.js'
MAX_LENGTH = 128
PROCESS_TIMEOUT = 30
REQUEST_TIMEOUT = 15 
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# --- 1. Tải "Bộ não" & "Từ điển" ---
print(" * Đang tải mô hình BiLSTM (Bộ phân loại)...")
if not os.path.exists(MODEL_FILE):
    print(f"LỖI NGHIÊM TRỌNG: Không tìm thấy tệp mô hình '{MODEL_FILE}'. Dừng lại.")
    exit()
model = load_model(MODEL_FILE)

print(" * Đang tải Tokenizer (Từ điển)...")
if not os.path.exists(TOKENIZER_FILE):
    print(f"LỖI NGHIÊM TRỌNG: Không tìm thấy tệp từ điển '{TOKENIZER_FILE}'. Dừng lại.")
    exit()

try:
    with open(TOKENIZER_FILE, 'r', encoding='utf-8') as f:
        tokenizer_json_string = f.read()
        tokenizer = tokenizer_from_json(tokenizer_json_string)

except Exception as e:
    print(f"LỖI NGHIÊM TRỌNG khi tải hoặc xử lý tokenizer: {e}")
    exit()
# ===============================================

print(" * Máy chủ Deface Watcher đã sẵn sàng!")

app = Flask(__name__)
# --- 2. Logic Cào dữ liệu (Hybrid) ---

# Phương pháp 1 (Ưu tiên): Gọi Node.js/Puppeteer
def extract_text_primary(url):
    try:
        command = ['node', SCRAPER_JS_FILE, url]
        result = subprocess.run(
            command, capture_output=True, text=True, encoding='utf-8',
            timeout=PROCESS_TIMEOUT, check=False 
        )
        if result.returncode != 0:
            print(f"  -> Puppeteer thất bại. Stderr: {result.stderr.strip()}")
            return None 
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
    """Uses requests/BeautifulSoup to get text, returns text or None."""
    try:
        print(f"    -> Thử fallback với requests...")
        response = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT, verify=False)
        response.raise_for_status() 
        soup = BeautifulSoup(response.content, 'html.parser')
        for script_or_style in soup(["script", "style"]):
            script_or_style.decompose()
        raw_text = soup.get_text()
        cleaned_text = " ".join(raw_text.split()).strip()
        print(f"    -> Fallback requests thành công.")
        return cleaned_text
    except requests.exceptions.Timeout:
        print(f"    -> Fallback requests thất bại: Timeout sau {REQUEST_TIMEOUT} giây.")
        return None
    except requests.exceptions.RequestException as e:
        print(f"    -> Fallback requests thất bại: {e}")
        return None
    except Exception as e:
        print(f"    -> Lỗi không mong muốn trong fallback: {e}")
        print(traceback.format_exc()) 
        return None

    # --- 3. Tokenization ---
def preprocess_text(text):
    """Converts text to padded sequence."""
    sequence = tokenizer.texts_to_sequences([text])
    padded_sequence = pad_sequences(sequence, maxlen=MAX_LENGTH, padding='post', truncating='post')
    return padded_sequence
# --- 4. Định nghĩa các endpoint của Flask ---
@app.route('/')
def home():
    """Serves the main HTML page."""
    return render_template('index.html', app_name="DEFACE WATCHER")

@app.route('/predict', methods=['POST'])
def predict_api():
    """API endpoint to handle prediction requests."""
    start_api_time = time.time()
    text = None 
    source = "Không xác định"
    scrape_duration = 0
    padded_sequence_list = [0] * MAX_LENGTH

    try:        
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({'error': 'Dữ liệu JSON không hợp lệ hoặc thiếu URL.'}), 400
        url = data['url']
        if not url.startswith(('http://', 'https://')):
             url = 'http://' + url
        
        print(f"\n[{time.strftime('%H:%M:%S')}] Nhận yêu cầu kiểm tra: {url}")
        # --- Cào Dữ liệu Từ URL ---
        print("  -> Đang thử Phương pháp 1 (Ưu tiên - Puppeteer)...")
        scrape_start_time = time.time()
        text = extract_text_primary(url) 
        scrape_end_time = time.time()
        scrape_duration = (scrape_end_time - scrape_start_time) * 1000

        if text is not None: 
            source = "Puppeteer (JS)"
            print(f"  -> Cào thành công (bằng {source}) trong {scrape_duration:.0f} ms.")
        else:
            print(f"  -> Puppeteer thất bại sau {scrape_duration:.0f} ms. Đang thử Phương pháp 2 (Dự phòng - 'curl')...")
            scrape_start_time = time.time()
            text = extract_text_fallback(url)
            scrape_end_time = time.time()
            source = "Requests (curl)"
            scrape_duration = (scrape_end_time - scrape_start_time) * 1000

            if text is None: 
                print(f"  -> Cả hai phương pháp đều thất bại sau {scrape_duration:.0f} ms.")
                return jsonify({'error': 'Không thể cào dữ liệu từ URL này (bị chặn/timeout/lỗi).'}), 400
            else:
                 print(f"  -> Cào thành công (bằng {source}) trong {scrape_duration:.0f} ms.")

        # --- Dự đoán với Mô hình BiLSTM ---
        final_status = ""
        final_probability = 0.0
        predict_duration = 0
        text_to_tokenize = text if isinstance(text, str) else ""

        processed_text_vector = preprocess_text(text_to_tokenize)
        padded_sequence_list = processed_text_vector[0].tolist()

        if not text_to_tokenize:
            print("  -> Văn bản trích xuất rỗng. Kiểm tra HTML (nếu có từ fallback)...")
            print("  -> Không có text, dự đoán là Bình thường.")
            final_status = "Bình thường"
            final_probability = 0.00
            source += " - (Trang rỗng)"
        else:
            print(f"  -> Tìm thấy {len(text_to_tokenize)} ký tự. Đang dự đoán bằng BiLSTM...")
            predict_start_time = time.time()
            prediction = model.predict(processed_text_vector, verbose=0)
            predict_duration = (time.time() - predict_start_time) * 1000

            final_probability = prediction[0][1]
            predicted_class_index = np.argmax(prediction, axis=1)[0]
            final_status = "Tấn công Deface" if predicted_class_index == 1 else "Bình thường"
            source += " - (Dự đoán BiLSTM)"
            print(f"  -> Thời gian dự đoán: {predict_duration:.0f} ms")

        total_api_time = (time.time() - start_api_time) * 1000
        print(f"  -> Kết quả cuối cùng: {final_status} (Xác suất Deface: {final_probability:.2f})")
        print(f"  -> Tổng thời gian xử lý API: {total_api_time:.0f} ms")

        return jsonify({
            'status': final_status,
            'probability': float(final_probability),
            'extracted_text': text_to_tokenize or '(Không tìm thấy văn bản)',
            'tokenized_sequence': padded_sequence_list,
            'checked_url': url,
            'source': source,
            'scrape_time_ms': round(scrape_duration),
            'predict_time_ms': round(predict_duration),
        })
        
    except Exception as e:
        print(f"Lỗi máy chủ nghiêm trọng tại endpoint /predict: {e}")
        print(traceback.format_exc()) 
        return jsonify({'error': f'Lỗi máy chủ không mong muốn: {str(e)}'}), 500

# --- 5. Chạy máy chủ ---
if __name__ == '__main__':
    warnings.filterwarnings('ignore', message='Unverified HTTPS request')
    app.run(host='0.0.0.0', port=5000, debug=True)