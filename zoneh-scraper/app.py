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
import traceback # To print detailed error trace

# --- CẤU HÌNH ---
MODEL_FILE = 'bilstm_defacement_model.keras' # Ensure this uses the latest model
TOKENIZER_FILE = 'tokenizer.json'
# Assuming you are using the JS script that prints ONLY text to stdout
SCRAPER_JS_FILE = 'get_text_puppeteer.js'
MAX_LENGTH = 128
PROCESS_TIMEOUT = 30 # Timeout for Puppeteer (seconds)
REQUEST_TIMEOUT = 10 # Timeout for Requests (seconds)
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

# === ĐOẠN MÃ ĐÃ SỬA ĐỂ ĐỌC JSON CHUẨN ===
try:
    with open(TOKENIZER_FILE, 'r', encoding='utf-8') as f:
        # 1. Đọc toàn bộ nội dung file JSON thành một chuỗi (string)
        tokenizer_json_string = f.read()
        # 2. Đưa chuỗi JSON đó trực tiếp cho hàm của Keras
        tokenizer = tokenizer_from_json(tokenizer_json_string)

except Exception as e:
    # Bắt lỗi chung nếu có vấn đề khi đọc file hoặc Keras xử lý
    print(f"LỖI NGHIÊM TRỌNG khi tải hoặc xử lý tokenizer: {e}")
    exit()
# ===============================================

print(" * Máy chủ Deface Watcher đã sẵn sàng!")

app = Flask(__name__)
# --- 2. Logic Cào dữ liệu (Hybrid) ---

# Phương pháp 1 (Ưu tiên): Gọi Node.js/Puppeteer
def extract_text_primary(url):
    """Calls the Node.js scraper script and returns text or None."""
    try:
        command = ['node', SCRAPER_JS_FILE, url]
        print(f"    -> Chạy lệnh: {' '.join(command)}") # Log the command being run
        result = subprocess.run(
            command, capture_output=True, text=True, encoding='utf-8',
            timeout=PROCESS_TIMEOUT, check=False # Don't raise error on non-zero exit
        )

        # Check return code AND stderr
        if result.returncode != 0:
            stderr_output = result.stderr.strip() if result.stderr else "Không có stderr."
            print(f"    -> Puppeteer thất bại (Mã lỗi {result.returncode}). Stderr: {stderr_output}")
            return None # Signal failure

        # Check if stdout is empty even if return code is 0
        stdout_output = result.stdout.strip() if result.stdout else ""
        if not stdout_output and result.stderr: # Check stderr again if stdout is empty
             stderr_output = result.stderr.strip()
             print(f"    -> Puppeteer chạy xong nhưng stdout rỗng. Stderr: {stderr_output}")
             # Treat as failure if stdout is empty but there was an error message
             # This depends on how get_text_puppeteer.js handles empty pages vs errors
             if "Lỗi Puppeteer" in stderr_output: # Check for specific error prefix from JS
                 return None

        # Return the captured text
        return stdout_output

    except FileNotFoundError:
        print("    -> LỖI: Không tìm thấy lệnh 'node'. Bạn đã cài đặt Node.js và thêm vào PATH chưa?")
        return None
    except subprocess.TimeoutExpired:
        print(f"    -> Puppeteer thất bại: Quá trình vượt quá {PROCESS_TIMEOUT} giây.")
        return None
    except Exception as e:
        print(f"    -> Lỗi không mong muốn khi gọi subprocess: {e}")
        print(traceback.format_exc()) # Print full traceback for unexpected errors
        return None

# Phương pháp 2 (Dự phòng): Dùng "curl" (Requests + BeautifulSoup)
def extract_text_fallback(url):
    """Uses requests/BeautifulSoup to get text, returns text or None."""
    try:
        print(f"    -> Thử fallback với requests...")
        response = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT, verify=False)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
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
        print(traceback.format_exc()) # Print full traceback
        return None

# --- 3. Tokenization (Giữ nguyên) ---
def preprocess_text(text):
    """Converts text to padded sequence."""
    sequence = tokenizer.texts_to_sequences([text])
    padded_sequence = pad_sequences(sequence, maxlen=MAX_LENGTH, padding='post', truncating='post')
    return padded_sequence

# --- 4. Định tuyến (Routing) ---
@app.route('/')
def home():
    """Serves the main HTML page."""
    return render_template('index.html', app_name="DEFACE WATCHER")

@app.route('/predict', methods=['POST'])
def predict_api():
    """API endpoint to handle prediction requests."""
    start_api_time = time.time()
    text = None # Initialize text as None to clearly track success/failure
    source = "Không xác định"
    scrape_duration = 0
    padded_sequence_list = [0] * MAX_LENGTH # Default empty token list

    try:
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({'error': 'Dữ liệu JSON không hợp lệ hoặc thiếu URL.'}), 400
        url = data['url']
        if not url.startswith(('http://', 'https://')):
             url = 'http://' + url

        print(f"\n[{time.strftime('%H:%M:%S')}] Nhận yêu cầu kiểm tra: {url}")

        # === HYBRID SCRAPING LOGIC ===
        print("  -> Đang thử Phương pháp 1 (Ưu tiên - Puppeteer)...")
        scrape_start_time = time.time()
        text = extract_text_primary(url) # Returns text string or None
        scrape_end_time = time.time()
        scrape_duration = (scrape_end_time - scrape_start_time) * 1000

        if text is not None: # Check if Puppeteer succeeded (even if text is "")
            source = "Puppeteer (JS)"
            print(f"  -> Cào thành công (bằng {source}) trong {scrape_duration:.0f} ms.")
        else:
            # Puppeteer failed, try fallback
            print(f"  -> Puppeteer thất bại sau {scrape_duration:.0f} ms. Đang thử Phương pháp 2 (Dự phòng - 'curl')...")
            scrape_start_time = time.time()
            text = extract_text_fallback(url) # Returns text string or None
            scrape_end_time = time.time()
            source = "Requests (curl)"
            scrape_duration = (scrape_end_time - scrape_start_time) * 1000

            if text is None: # If fallback also failed
                print(f"  -> Cả hai phương pháp đều thất bại sau {scrape_duration:.0f} ms.")
                return jsonify({'error': 'Không thể cào dữ liệu từ URL này (bị chặn/timeout/lỗi).'}), 400
            else: # Fallback succeeded
                 print(f"  -> Cào thành công (bằng {source}) trong {scrape_duration:.0f} ms.")
        # === END HYBRID SCRAPING ===

        # --- Process text and Predict ---
        final_status = ""
        final_probability = 0.0
        predict_duration = 0
        # Ensure text is a string for tokenization, default to empty string if None was somehow passed
        text_to_tokenize = text if isinstance(text, str) else ""

        # Always tokenize, even empty strings
        processed_text_vector = preprocess_text(text_to_tokenize)
        padded_sequence_list = processed_text_vector[0].tolist() # For JSON response

        # Check for empty text AFTER successful scrape
        if not text_to_tokenize:
            print("  -> Văn bản trích xuất rỗng. Kiểm tra HTML (nếu có từ fallback)...")
            # Currently, extract_text_primary doesn't return HTML, only fallback does.
            # This logic might need adjustment if JS returns HTML too.
            # Let's simplify: If text is empty, just predict Normal directly.
            # The 'Suspicious' logic adds complexity and relies on having HTML consistently.
            print("  -> Không có text, dự đoán là Bình thường.")
            final_status = "Bình thường"
            final_probability = 0.00
            source += " - (Trang rỗng)"
        else:
            # If text exists, predict using the BiLSTM model
            print(f"  -> Tìm thấy {len(text_to_tokenize)} ký tự. Đang dự đoán bằng BiLSTM...")
            predict_start_time = time.time()
            prediction = model.predict(processed_text_vector, verbose=0)
            predict_duration = (time.time() - predict_start_time) * 1000

            final_probability = prediction[0][1] # Probability of class 1 (Deface)
            predicted_class_index = np.argmax(prediction, axis=1)[0]
            final_status = "Tấn công Deface" if predicted_class_index == 1 else "Bình thường"
            source += " - (Dự đoán BiLSTM)"
            print(f"  -> Thời gian dự đoán: {predict_duration:.0f} ms")

        total_api_time = (time.time() - start_api_time) * 1000
        print(f"  -> Kết quả cuối cùng: {final_status} (Xác suất Deface: {final_probability:.2f})")
        print(f"  -> Tổng thời gian xử lý API: {total_api_time:.0f} ms")

        # Return results to frontend
        return jsonify({
            'status': final_status,
            'probability': float(final_probability),
            'extracted_text': text_to_tokenize or '(Không tìm thấy văn bản)', # Display message if empty
            'tokenized_sequence': padded_sequence_list,
            'checked_url': url,
            'source': source,
            'scrape_time_ms': round(scrape_duration),
            'predict_time_ms': round(predict_duration),
        })

    except Exception as e:
        print(f"Lỗi máy chủ nghiêm trọng tại endpoint /predict: {e}")
        print(traceback.format_exc()) # Print full traceback for debugging
        return jsonify({'error': f'Lỗi máy chủ không mong muốn: {str(e)}'}), 500

# --- 5. Chạy máy chủ ---
if __name__ == '__main__':
    # Suppress insecure request warnings from requests
    warnings.filterwarnings('ignore', message='Unverified HTTPS request')
    # Run on all available IPs (0.0.0.0), port 5000, with debug mode on
    app.run(host='0.0.0.0', port=5000, debug=True)