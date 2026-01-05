import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = BASE_DIR / "defacement_url.txt"
OUTPUT_FILE = BASE_DIR / "defacement_url_valid.txt"
ERROR_FILE = BASE_DIR / "defacement_url_errors.txt"

TIMEOUT = 3
MAX_WORKERS = 10
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
}


def is_url_accessible(url, timeout=TIMEOUT):
    try:
        response = requests.get(url, headers=REQUEST_HEADERS, allow_redirects=True, timeout=timeout)
        return response.status_code < 400
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
        return False
    except Exception:
        return False


def read_urls():
    if not INPUT_FILE.exists():
        print(f"ERROR: Missing input file {INPUT_FILE}")
        sys.exit(1)
    with INPUT_FILE.open("r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def write_lines(path, items):
    with path.open("w", encoding="utf-8") as f:
        for item in items:
            f.write(item + "\n")


def main():
    urls = read_urls()
    if not urls:
        print("Input file is empty. Nothing to do.")
        return

    total_urls = len(urls)
    valid_urls = []
    error_urls = []

    print(f"Checking {total_urls} URLs with {MAX_WORKERS} workers...")
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_url = {executor.submit(is_url_accessible, url): url for url in urls}
        for i, future in enumerate(as_completed(future_to_url), start=1):
            url = future_to_url[future]
            try:
                if future.result():
                    valid_urls.append(url)
                else:
                    error_urls.append(url)
            except Exception:
                error_urls.append(url)

            if i % 100 == 0 or i == total_urls:
                print(
                    f"Progress {i}/{total_urls} | valid: {len(valid_urls)} | invalid: {len(error_urls)}"
                )

    write_lines(OUTPUT_FILE, valid_urls)
    write_lines(ERROR_FILE, error_urls)

    print("\n--- DONE ---")
    print(f"Valid URLs saved to: {OUTPUT_FILE}")
    print(f"Invalid URLs saved to: {ERROR_FILE}")


if __name__ == "__main__":
    start_time = time.time()
    main()
    end_time = time.time()
    print(f"Elapsed time: {end_time - start_time:.2f} seconds")
