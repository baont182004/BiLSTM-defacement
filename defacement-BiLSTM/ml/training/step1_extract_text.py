import json
import numpy as np
import subprocess
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings
from pathlib import Path
import time
import random

# --- CONFIG ---
ROOT_DIR = Path(__file__).resolve().parents[2]
URLS_DIR = ROOT_DIR / "ml" / "data" / "urls"
RAW_DIR = ROOT_DIR / "ml" / "data" / "raw"
DEFACED_URL_FILE = URLS_DIR / "defacement_url.txt"
NORMAL_URL_FILE = URLS_DIR / "normal_url.txt"
OUTPUT_JSON_FILE = RAW_DIR / "rawData.json"
SCRAPER_JS_FILE = ROOT_DIR / "tools" / "scraper" / "get_text_puppeteer.js" 
MAX_WORKERS = 10   
PROCESS_TIMEOUT = 45 
REQUEST_TIMEOUT = 12  
RETRY_MAX = 2
MIN_TEXT_LENGTH = 200
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7'
}
# ----------------


def _run_with_retry(func, retries=RETRY_MAX):
    last_error = None
    for attempt in range(retries + 1):
        result, meta = func()
        if result:
            return result, meta
        last_error = meta
        sleep_for = 0.5 * (2 ** attempt) + random.uniform(0, 0.3)
        time.sleep(sleep_for)
    return None, last_error



def extract_text_primary(url):
    def _call():
        meta = {"errors": [], "timings": {}, "http_status": None}
        try:
            command = ['node', str(SCRAPER_JS_FILE), url, '--json']
            start = time.time()
            result = subprocess.run(
                command, capture_output=True, text=True, encoding='utf-8',
                timeout=PROCESS_TIMEOUT
            )
            meta["timings"]["process_ms"] = round((time.time() - start) * 1000)
            if result.returncode != 0:
                meta["errors"].append(result.stderr.strip() or "puppeteer_failed")
                return None, meta
            output = result.stdout.strip()
            if not output:
                meta["errors"].append("puppeteer_empty")
                return None, meta
            try:
                payload = json.loads(output)
                meta["http_status"] = payload.get("httpStatus")
                meta["timings"].update(payload.get("timings") or {})
                meta["errors"].extend(payload.get("errors") or [])
                text = payload.get("text", "")
                return text.strip() or None, meta
            except json.JSONDecodeError:
                return output.strip() or None, meta
        except Exception as exc:
            meta["errors"].append(f"puppeteer_error:{exc}")
            return None, meta

    return _run_with_retry(_call)


def extract_text_fallback(url):
    def _call():
        meta = {"errors": [], "timings": {}, "http_status": None}
        try:
            start = time.time()
            response = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT, verify=False)
            meta["timings"]["request_ms"] = round((time.time() - start) * 1000)
            meta["http_status"] = response.status_code
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            for script_or_style in soup(["script", "style", "noscript"]):
                script_or_style.decompose()
            raw_text = soup.get_text()
            cleaned = " ".join(raw_text.split()).strip()
            return cleaned or None, meta
        except Exception as exc:
            meta["errors"].append(f"requests_error:{exc}")
            return None, meta

    return _run_with_retry(_call)

def process_url(task):
    url, label = task
    
    text, primary_meta = extract_text_primary(url)
    source = "Puppeteer (JS)"
    meta = {
        "primary": primary_meta,
        "fallback": None,
    }
    
    if text is None: 
        text, fallback_meta = extract_text_fallback(url)
        source = "Requests (curl)"
        meta["fallback"] = fallback_meta
    
    if text and len(text) >= MIN_TEXT_LENGTH:
        return { 'url': url, 'label': label, 'text': text, 'source': source, 'meta': meta }
    return None

def main():
    print("--- BẮT ĐẦU BƯỚC 1 (PHIÊN BẢN HYBRID) ---")
    
    def read_urls(filepath, label):
        if not filepath.exists():
            print(f"LỖI: Không tìm thấy tệp {filepath}")
            return []
        with filepath.open('r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip().startswith('http')]
        return [(url, label) for url in urls]

    tasks = read_urls(DEFACED_URL_FILE, 1) + read_urls(NORMAL_URL_FILE, 0)
    seen = set()
    deduped = []
    for url, label in tasks:
        if url in seen:
            continue
        seen.add(url)
        deduped.append((url, label))
    tasks = deduped
    
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
    
    OUTPUT_JSON_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_JSON_FILE.open('w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

    print(f"\n--- HOÀN TẤT BƯỚC 1 ---")
    print(f"🎉 Đã lưu {len(all_data)} / {len(tasks)} mẫu thành công vào file {OUTPUT_JSON_FILE}")

if __name__ == "__main__":
    warnings.filterwarnings('ignore', message='Unverified HTTPS request')
    main()
