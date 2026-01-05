import json
import os
import random
import subprocess
import time
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from statistics import mean, median
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

# --- CONFIG ---
ROOT_DIR = Path(__file__).resolve().parents[2]
URLS_DIR = ROOT_DIR / "ml" / "data" / "urls"
RAW_DIR = ROOT_DIR / "ml" / "data" / "raw"
DEFACED_URL_FILE = URLS_DIR / "defacement_url.txt"
NORMAL_URL_FILE = URLS_DIR / "normal_url.txt"
OUTPUT_JSON_FILE = RAW_DIR / "rawData.json"
SCRAPER_JS_FILE = ROOT_DIR / "tools" / "scraper" / "get_text_puppeteer.js"

DEFAULT_MAX_WORKERS = 10
DEFAULT_PROCESS_TIMEOUT = 45
DEFAULT_REQUEST_TIMEOUT = 12
DEFAULT_RETRIES = 2
DEFAULT_BACKOFF_BASE = 0.5
DEFAULT_MIN_TEXT_LENGTH = 200
DEFAULT_MAX_TEXT_LENGTH = 20000
DEFAULT_ENABLE_META = 0
DEFAULT_WRITE_FAILURES = 1
DEFAULT_FAILURES_PATH = RAW_DIR / "failures.jsonl"
DEFAULT_SORT_OUTPUT = 1
DEFAULT_STRIP_UTM = 0
DEFAULT_USE_PUPPETEER_JSON = 1

TRANSIENT_STATUS = {429, 500, 502, 503, 504}
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def _get_int_env(name, default):
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_float_env(name, default):
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _get_bool_env(name, default):
    value = os.getenv(name)
    if value is None:
        return bool(default)
    return value.strip().lower() in {"1", "true", "yes", "on"}


MAX_WORKERS = _get_int_env("MAX_WORKERS", DEFAULT_MAX_WORKERS)
PROCESS_TIMEOUT = _get_int_env("PROCESS_TIMEOUT", DEFAULT_PROCESS_TIMEOUT)
REQUEST_TIMEOUT = _get_int_env("REQUEST_TIMEOUT", DEFAULT_REQUEST_TIMEOUT)
RETRIES = _get_int_env("RETRIES", DEFAULT_RETRIES)
BACKOFF_BASE = _get_float_env("BACKOFF_BASE", DEFAULT_BACKOFF_BASE)
MIN_TEXT_LENGTH = _get_int_env("MIN_TEXT_LENGTH", DEFAULT_MIN_TEXT_LENGTH)
MAX_TEXT_LENGTH = _get_int_env("MAX_TEXT_LENGTH", DEFAULT_MAX_TEXT_LENGTH)
ENABLE_META = _get_bool_env("ENABLE_META", DEFAULT_ENABLE_META)
WRITE_FAILURES = _get_bool_env("WRITE_FAILURES", DEFAULT_WRITE_FAILURES)
FAILURES_PATH = Path(os.getenv("FAILURES_PATH", DEFAULT_FAILURES_PATH))
SORT_OUTPUT = _get_bool_env("SORT_OUTPUT", DEFAULT_SORT_OUTPUT)
STRIP_UTM = _get_bool_env("STRIP_UTM", DEFAULT_STRIP_UTM)
USE_PUPPETEER_JSON = _get_bool_env("USE_PUPPETEER_JSON", DEFAULT_USE_PUPPETEER_JSON)


def _safe_write_failure(record):
    if not WRITE_FAILURES:
        return
    try:
        FAILURES_PATH.parent.mkdir(parents=True, exist_ok=True)
        with FAILURES_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _sleep_backoff(attempt):
    jitter = random.uniform(0, 0.2)
    time.sleep(BACKOFF_BASE * (2**attempt) + jitter)


def _normalize_url(raw_url):
    url = raw_url.strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = f"http://{url}"
    if not STRIP_UTM:
        return url
    parsed = urlparse(url)
    query = [(k, v) for k, v in parse_qsl(parsed.query) if not k.startswith("utm_")]
    rebuilt = parsed._replace(query=urlencode(query))
    return urlunparse(rebuilt)


def _should_retry_requests(exc, status_code):
    if isinstance(exc, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)):
        return True
    if status_code in TRANSIENT_STATUS:
        return True
    return False


def _apply_quality_gate(text):
    if text is None:
        return None, False, "empty_text"
    text = text.strip()
    if MIN_TEXT_LENGTH > 0 and len(text) < MIN_TEXT_LENGTH:
        return None, False, "too_short"
    truncated = False
    if MAX_TEXT_LENGTH > 0 and len(text) > MAX_TEXT_LENGTH:
        text = text[:MAX_TEXT_LENGTH]
        truncated = True
    return text, truncated, None


def extract_text_primary(url):
    attempts = 0
    last_error = None
    last_meta = None
    for attempt in range(RETRIES + 1):
        attempts = attempt + 1
        start = time.time()
        meta = {"errors": [], "timings": {}, "http_status": None, "final_url": None}
        try:
            command = ["node", str(SCRAPER_JS_FILE)]
            if USE_PUPPETEER_JSON:
                command.append("--json")
            command.append(url)
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=PROCESS_TIMEOUT,
                check=False,
            )
            meta["timings"]["process_ms"] = round((time.time() - start) * 1000)
            if result.returncode != 0:
                meta["errors"].append(result.stderr.strip() or "puppeteer_failed")
                last_error = "returncode"
                last_meta = meta
                _sleep_backoff(attempt)
                continue

            output = result.stdout.strip()
            if USE_PUPPETEER_JSON:
                try:
                    payload = json.loads(output)
                except json.JSONDecodeError:
                    if USE_PUPPETEER_JSON:
                        # Retry once without JSON mode if parse fails.
                        USE_JSON_FALLBACK = False
                        try:
                            plain_result = subprocess.run(
                                ["node", str(SCRAPER_JS_FILE), url],
                                capture_output=True,
                                text=True,
                                encoding="utf-8",
                                timeout=PROCESS_TIMEOUT,
                                check=False,
                            )
                            if plain_result.returncode == 0:
                                output = plain_result.stdout.strip()
                                return output or None, meta, attempts
                        except Exception:
                            pass
                    meta["errors"].append("puppeteer_json_parse_failed")
                    last_error = "json_parse"
                    last_meta = meta
                    _sleep_backoff(attempt)
                    continue

                if not payload.get("ok"):
                    meta["errors"].extend(payload.get("errors") or ["puppeteer_ok_false"])
                    last_error = "ok_false"
                    last_meta = meta
                    _sleep_backoff(attempt)
                    continue

                meta["http_status"] = payload.get("httpStatus")
                meta["final_url"] = payload.get("finalUrl")
                meta["timings"].update(payload.get("timings") or {})
                text = payload.get("text", "")
                return text or None, meta, attempts

            return output or None, meta, attempts
        except subprocess.TimeoutExpired:
            meta["errors"].append("puppeteer_timeout")
            last_error = "timeout"
            last_meta = meta
            _sleep_backoff(attempt)
        except Exception as exc:
            meta["errors"].append(f"puppeteer_error:{exc}")
            last_error = "exception"
            last_meta = meta
            _sleep_backoff(attempt)

    return None, last_meta, attempts


def extract_text_fallback(url):
    attempts = 0
    last_error = None
    last_meta = None
    for attempt in range(RETRIES + 1):
        attempts = attempt + 1
        start = time.time()
        meta = {"errors": [], "timings": {}, "http_status": None, "final_url": None}
        try:
            response = requests.get(
                url,
                headers=REQUEST_HEADERS,
                timeout=REQUEST_TIMEOUT,
                verify=False,
                allow_redirects=True,
            )
            meta["timings"]["request_ms"] = round((time.time() - start) * 1000)
            meta["http_status"] = response.status_code
            meta["final_url"] = response.url
            if response.status_code in TRANSIENT_STATUS:
                last_error = f"status_{response.status_code}"
                last_meta = meta
                _sleep_backoff(attempt)
                continue
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")
            for script_or_style in soup(["script", "style", "noscript"]):
                script_or_style.decompose()
            raw_text = soup.get_text()
            cleaned = " ".join(raw_text.split()).strip()
            return cleaned or None, meta, attempts
        except Exception as exc:
            meta["errors"].append(f"requests_error:{exc}")
            last_error = "exception"
            last_meta = meta
            if _should_retry_requests(exc, meta.get("http_status")):
                _sleep_backoff(attempt)
                continue
            break

    return None, last_meta, attempts


def read_urls(filepath, label):
    if not filepath.exists():
        print(f"ERROR: Missing file {filepath}")
        return []
    with filepath.open("r", encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip()]
    return [(url, label) for url in urls]


def process_url(task):
    url, label = task
    text, primary_meta, primary_attempts = extract_text_primary(url)
    source = "Puppeteer (JS)"
    method = "puppeteer"
    meta = primary_meta or {}

    text, truncated, reason = _apply_quality_gate(text)
    if text is None:
        text, fallback_meta, fallback_attempts = extract_text_fallback(url)
        source = "Requests (curl)"
        method = "requests"
        meta = fallback_meta or {}
        text, truncated, reason = _apply_quality_gate(text)
        if text is None:
            _safe_write_failure(
                {
                    "url": url,
                    "label": label,
                    "stage": "extract",
                    "method": method,
                    "attempt": fallback_attempts,
                    "elapsed_ms": meta.get("timings", {}).get("request_ms"),
                    "http_status": meta.get("http_status"),
                    "error": reason or "fallback_failed",
                }
            )
            return None
        attempts = fallback_attempts
    else:
        attempts = primary_attempts

    result = {"url": url, "label": label, "text": text, "source": source}
    if ENABLE_META:
        result.update(
            {
                "scrape_time_ms": meta.get("timings", {}).get("process_ms")
                or meta.get("timings", {}).get("request_ms"),
                "method": method,
                "http_status": meta.get("http_status"),
                "final_url": meta.get("final_url"),
                "text_len": len(text),
                "text_truncated": bool(truncated),
                "attempts": attempts,
            }
        )
    return result, truncated, method, result.get("scrape_time_ms")


def main():
    print("--- STEP 1: HYBRID CRAWL ---")
    tasks = read_urls(DEFACED_URL_FILE, 1) + read_urls(NORMAL_URL_FILE, 0)
    total_read = len(tasks)

    deduped = {}
    for url, label in tasks:
        normalized = _normalize_url(url)
        if not normalized:
            continue
        if normalized in deduped and label == 0:
            continue
        if normalized in deduped and label == 1 and deduped[normalized] == 0:
            print(f"WARNING: URL appears in both lists, keeping label=1: {normalized}")
        deduped[normalized] = label
    tasks = [(url, label) for url, label in deduped.items()]

    if not tasks:
        print("ERROR: No URLs found to process.")
        return

    print(f"Read {total_read} URLs, {len(tasks)} after normalization/dedupe.")
    print(f"Processing with {MAX_WORKERS} workers...")

    all_data = []
    success_by_method = {"puppeteer": 0, "requests": 0}
    truncated_count = 0
    scrape_times = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(process_url, task) for task in tasks]
        for future in tqdm(as_completed(futures), total=len(tasks), desc="Crawling"):
            result = future.result()
            if not result:
                continue
            record, truncated, method, scrape_time = result
            all_data.append(record)
            success_by_method[method] += 1
            if truncated:
                truncated_count += 1
            if ENABLE_META and scrape_time is not None:
                scrape_times.append(scrape_time)

    if SORT_OUTPUT:
        all_data.sort(key=lambda item: item["url"])

    OUTPUT_JSON_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_JSON_FILE.open("w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

    failed = len(tasks) - len(all_data)
    print("\n--- SUMMARY ---")
    print(f"Total read: {total_read}")
    print(f"After dedupe: {len(tasks)}")
    print(f"Success: {len(all_data)}")
    print(f"Failed: {failed}")
    print(f"Success by method: {success_by_method}")
    print(f"Truncated samples: {truncated_count}")
    if ENABLE_META and scrape_times:
        print(f"Avg scrape time (ms): {mean(scrape_times):.2f}")
        print(f"Median scrape time (ms): {median(scrape_times):.2f}")
    print(f"Output saved to {OUTPUT_JSON_FILE}")


if __name__ == "__main__":
    warnings.filterwarnings("ignore", message="Unverified HTTPS request")
    main()
