import os
import json
import numpy as np
import subprocess
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings

# --- CẤU HÌNH (ĐÃ TỐI ƯU TỐC ĐỘ) ---
DEFACED_URL_FILE = 'defacement_url.txt'
NORMAL_URL_FILE = 'normal_url.txt'
OUTPUT_JSON_FILE = 'rawData.json'
SCRAPER_JS_FILE = 'get_text_puppeteer.js' 
MAX_WORKERS = 10     # <-- TĂNG SỐ LUỒNG SONG SONG (Tăng lên 15 hoặc 20 nếu máy bạn mạnh)
PROCESS_TIMEOUT = 25 # Giảm một chút (từ 30)
REQUEST_TIMEOUT = 8  # Giảm một chút (từ 10)
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# --- 2. Logic Cào dữ liệu (Hybrid) ---

# Phương pháp 1 (Ưu tiên): Gọi Node.js/Puppeteer
def extract_text_primary(url):
    try:
        command = ['node', SCRAPER_JS_FILE, url]
        result = subprocess.run(
            command, capture_output=True, text=True, encoding='utf-8',
            timeout=PROCESS_TIMEOUT
        )
        if result.returncode != 0:
            return None 
        return result.stdout.strip()
    except Exception:
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
    except Exception:
        return None

# Hàm xử lý cho mỗi URL
def process_url(task):
    url, label = task
    
    text = extract_text_primary(url) # Ưu tiên Puppeteer
    source = "Puppeteer (JS)"
    
    if text is None: # Nếu Puppeteer thất bại
        text = extract_text_fallback(url) # Thử dùng 'curl'
        source = "Requests (curl)"
    
    if text: 
        return { 'url': url, 'label': label, 'text': text, 'source': source }
    return None

# --- HÀM CHÍNH ---
def main():
    print("--- BẮT ĐẦU BƯỚC 1 (PHIÊN BẢN HYBRID) ---")
    
    def read_urls(filepath, label):
        if not os.path.exists(filepath):
            print(f"LỖI: Không tìm thấy tệp {filepath}")
            return []
        with open(filepath, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip().startswith('http')]
        return [(url, label) for url in urls]

    tasks = read_urls(DEFACED_URL_FILE, 1) + read_urls(NORMAL_URL_FILE, 0)
    
    if not tasks:
        print("LỖI: Không tìm thấy URL nào để xử lý. Dừng lại.")
        return

    print(f"Tìm thấy tổng cộng {len(tasks)} URL. Bắt đầu xử lý với {MAX_WORKERS} luồng...")
    all_data = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(process_url, task) for task in tasks]
        
        for future in tqdm(as_completed(futures), total=len(tasks), desc="Đang cào dữ liệu"):
            result = future.result()
            if result:
                all_data.append(result)
    
    with open(OUTPUT_JSON_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

    print(f"\n--- HOÀN TẤT BƯỚC 1 ---")
    print(f"🎉 Đã lưu {len(all_data)} / {len(tasks)} mẫu thành công vào file {OUTPUT_JSON_FILE}")

if __name__ == "__main__":
    warnings.filterwarnings('ignore', message='Unverified HTTPS request')
    main()