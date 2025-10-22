#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import random
import time
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

INPUT_FILE = "urls_raw.txt"
OUTPUT_FILE = "urls_valid.txt"
ERROR_FILE  = "urls_errors.txt"
TARGET_COUNT = 6000
TIMEOUT = 3
MAX_WORKERS = 10  # số luồng đồng thời

def is_url_accessible(url, timeout=TIMEOUT):
    try:
        resp = requests.get(url, allow_redirects=True, timeout=timeout)
        return resp.status_code < 400
    except Exception:
        return False

def main():
    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            urls = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"Error: không tìm thấy file {INPUT_FILE}")
        sys.exit(1)

    valid_urls = []
    error_urls = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_url = {executor.submit(is_url_accessible, url): url for url in urls}
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
            if i % 100 == 0:
                print(f"Đã kiểm {i} URLs — hợp lệ: {len(valid_urls)}")
            if len(valid_urls) >= TARGET_COUNT:
                break

    random.shuffle(valid_urls)
    selected = valid_urls[:TARGET_COUNT]

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for u in selected:
            f.write(u + "\n")

    with open(ERROR_FILE, "w", encoding="utf-8") as f:
        for u in error_urls:
            f.write(u + "\n")

    print(f"Hoàn thành: {len(selected)} URLs hợp lệ được lưu vào {OUTPUT_FILE}")
    print(f"URLs lỗi được ghi vào {ERROR_FILE}")

if __name__ == "__main__":
    main()
