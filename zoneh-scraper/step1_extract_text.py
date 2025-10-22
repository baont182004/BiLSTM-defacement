import requests
from bs4 import BeautifulSoup
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

# --- CẤU HÌNH ---
DEFACED_URL_FILE = 'defacement_url.txt'
NORMAL_URL_FILE = 'normal_url.txt'
OUTPUT_JSON_FILE = 'rawData.json'
MAX_WORKERS = 10  # Số lượng URL xử lý song song (tăng/giảm tùy theo mạng)
REQUEST_TIMEOUT = 10 # Thời gian (giây) chờ mỗi URL
# --------------------

# Header để giả lập trình duyệt, tránh bị chặn
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def read_urls_from_file(filepath):
    """Đọc URL từ file .txt, mỗi dòng một URL."""
    if not os.path.exists(filepath):
        print(f"LỖI: Không tìm thấy tệp {filepath}")
        return []
    with open(filepath, 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip().startswith('http')]
    return urls

def extract_text_from_url(url, label):
    """
    Tải URL, trích xuất văn bản thuần túy (không có HTML, script)
    và trả về một dictionary.
    """
    try:
        # Tải nội dung trang
        response = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT, verify=False)
        response.raise_for_status() # Báo lỗi nếu mã http là 4xx hoặc 5xx

        # Sử dụng BeautifulSoup để phân tích HTML
        soup = BeautifulSoup(response.content, 'html.parser')

        # Xóa các thẻ script và style (mã nhúng)
        for script_or_style in soup(["script", "style"]):
            script_or_style.decompose()

        # Lấy văn bản thuần
        raw_text = soup.get_text()

        # Làm sạch văn bản: xóa xuống dòng, tab và khoảng trắng thừa
        cleaned_text = " ".join(raw_text.split()).strip()

        if cleaned_text:
            return {
                "url": url,
                "label": label,
                "text": cleaned_text
            }
        else:
            # Trả về None nếu trang không có văn bản
            return None 

    except requests.RequestException as e:
        # Ghi lại lỗi nhưng không dừng chương trình
        # print(f"Lỗi khi xử lý {url}: {e}")
        return None

def main():
    print("--- BẮT ĐẦU BƯỚC 1 (PHIÊN BẢN PYTHON) ---")
    print("Đang trích xuất văn bản thuần từ URL...")

    # 1. Đọc danh sách URL
    defaced_urls = read_urls_from_file(DEFACED_URL_FILE)
    normal_urls = read_urls_from_file(NORMAL_URL_FILE)
    
    if not defaced_urls or not normal_urls:
        print("LỖI: Cần cả hai tệp URL 'deface' và 'normal'. Dừng lại.")
        return

    print(f"Tìm thấy {len(defaced_urls)} URL deface và {len(normal_urls)} URL bình thường.")
    
    # Gộp 2 danh sách lại và gán nhãn
    tasks = [(url, 1) for url in defaced_urls] + [(url, 0) for url in normal_urls]
    
    all_data = []
    
    # 2. Xử lý song song
    print(f"Đang xử lý {len(tasks)} URL (sử dụng tối đa {MAX_WORKERS} luồng)...")
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Tạo các future
        future_to_task = {executor.submit(extract_text_from_url, url, label): (url, label) for url, label in tasks}
        
        # Dùng tqdm để hiển thị thanh tiến trình
        for future in tqdm(as_completed(future_to_task), total=len(tasks), desc="Đang cào dữ liệu"):
            result = future.result()
            if result:
                all_data.append(result)

    # 3. Lưu kết quả
    print(f"\nĐã trích xuất thành công {len(all_data)} / {len(tasks)} mẫu.")
    
    with open(OUTPUT_JSON_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
        
    print(f"🎉 Đã lưu 'Văn bản thô' vào tệp: {OUTPUT_JSON_FILE}")
    print("Bây giờ bạn có thể tiến hành Bước 2: Tokenization.")

if __name__ == "__main__":
    # Tắt cảnh báo về việc không xác thực SSL (verify=False)
    requests.packages.urllib3.disable_warnings() 
    main()