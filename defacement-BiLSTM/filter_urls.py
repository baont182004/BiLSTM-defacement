

import requests
import time
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed


INPUT_FILE = "defacement_url.txt"
OUTPUT_FILE = "defacement_url_valid.txt"
ERROR_FILE = "defacement_url_errors.txt"


TIMEOUT = 3
MAX_WORKERS = 10 

def is_url_accessible(url, timeout=TIMEOUT):
    """
    Kiểm tra xem URL có thể truy cập được không (status < 400).
    """
    try:

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        resp = requests.get(url, headers=headers, allow_redirects=True, timeout=timeout)

        return resp.status_code < 400
    except requests.exceptions.Timeout:

        return False
    except requests.exceptions.ConnectionError:

        return False
    except Exception as e:
        return False

def main():
    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            urls = [line.strip() for line in f if line.strip()]
        print(f"Đã tìm thấy {len(urls)} URLs trong {INPUT_FILE}")
    except FileNotFoundError:
        print(f"Lỗi: không tìm thấy file {INPUT_FILE}")
        sys.exit(1)
    except Exception as e:
        print(f"Lỗi khi đọc file {INPUT_FILE}: {e}")
        sys.exit(1)

    if not urls:
        print("Tệp đầu vào trống. Kết thúc.")
        return

    valid_urls = []
    error_urls = []
    total_urls = len(urls)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_url = {executor.submit(is_url_accessible, url): url for url in urls}
        
        print(f"Bắt đầu kiểm tra {total_urls} URLs với {MAX_WORKERS} luồng...")
        
        for i, fut in enumerate(as_completed(future_to_url), start=1):
            url = future_to_url[fut]
            try:
                ok = fut.result()
                if ok:
                    valid_urls.append(url)
                else:
                    error_urls.append(url)
            except Exception as e:
                error_urls.append(url)
            
            if i % 100 == 0 or i == total_urls:
                print(f"Đã kiểm tra {i}/{total_urls} URLs — Hợp lệ: {len(valid_urls)} — Lỗi: {len(error_urls)}")

    selected = valid_urls

    try:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            for u in selected:
                f.write(u + "\n")

        with open(ERROR_FILE, "w", encoding="utf-8") as f:
            for u in error_urls:
                f.write(u + "\n")
    except IOError as e:
        print(f"Lỗi khi ghi file: {e}")

    print("\n--- HOÀN THÀNH ---")
    print(f"Tổng cộng {len(selected)} URLs hợp lệ đã được lưu vào: {OUTPUT_FILE}")
    print(f"Tổng cộng {len(error_urls)} URLs lỗi/không hợp lệ được ghi vào: {ERROR_FILE}")

if __name__ == "__main__":
    start_time = time.time()
    main()
    end_time = time.time()
    print(f"Tổng thời gian thực thi: {end_time - start_time:.2f} giây")
