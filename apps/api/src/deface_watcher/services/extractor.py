import json
import logging
import os
import re
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from ..config import load_settings

MIN_TEXT_LENGTH_BACKEND = 200
BLOCKED_STATUSES = {403, 429, 503}
BLOCKED_ERROR_PATTERN = re.compile(
    r"(captcha|cloudflare|challenge|access denied|forbidden|robot|verify you are human)",
    re.IGNORECASE,
)


def _normalize_text(text: str, max_chars: int, collapse_whitespace: bool = True):
    cleaned = " ".join(text.split()).strip() if collapse_whitespace else text.strip()
    if len(cleaned) > max_chars:
        return cleaned[:max_chars], True
    return cleaned, False


def _sanitize_errors(errors):
    sanitized = []
    for err in errors or []:
        item = str(err).strip()
        if not item:
            continue
        if "/" in item or "\\" in item:
            item = item.split(":")[0]
        sanitized.append(item[:200])
    return sanitized[:3]


def _is_blocked(puppeteer_meta) -> bool:
    if not puppeteer_meta:
        return False
    status = puppeteer_meta.get("http_status")
    if status in BLOCKED_STATUSES:
        return True
    for err in puppeteer_meta.get("errors") or []:
        if BLOCKED_ERROR_PATTERN.search(str(err)):
            return True
    return False


def _run_puppeteer(url: str, extra_env=None):
    settings = load_settings()
    command = ["node", str(settings.scraper_js_path), "--json", url]
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    meta = {
        "ok": False,
        "http_status": None,
        "final_url": url,
        "method": "fallback",
        "text_len": 0,
        "timings": {},
        "errors": [],
    }
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=settings.process_timeout,
        check=False,
        env=env,
    )
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        meta["errors"].append("puppeteer_failed")
        if stderr:
            meta["errors"].append(stderr.splitlines()[0][:200])
        return None, meta

    raw_output = result.stdout.strip()
    if not raw_output:
        meta["errors"].append("puppeteer_empty")
        return None, meta

    try:
        payload = json.loads(raw_output)
    except json.JSONDecodeError:
        meta.update(
            {
                "ok": True,
                "method": "legacy_stdout",
                "text_len": len(raw_output),
            }
        )
        return raw_output, meta

    if not payload.get("ok"):
        meta.update(
            {
                "ok": False,
                "http_status": payload.get("http_status"),
                "final_url": payload.get("final_url") or url,
                "method": payload.get("method") or "fallback",
                "errors": payload.get("errors") or [],
                "timings": payload.get("timings") or {},
            }
        )
        return None, meta

    text = payload.get("text", "") or ""
    meta.update(
        {
            "ok": True,
            "http_status": payload.get("http_status"),
            "final_url": payload.get("final_url") or url,
            "method": payload.get("method") or "fallback",
            "text_len": payload.get("text_len", len(text)),
            "timings": payload.get("timings") or {},
            "errors": payload.get("errors") or [],
        }
    )
    return text, meta


def _run_fallback(url: str):
    settings = load_settings()
    start = time.time()
    response = requests.get(
        url,
        headers=settings.request_headers,
        timeout=settings.request_timeout,
        verify=False,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.content, "html.parser")
    for script_or_style in soup(["script", "style", "noscript"]):
        script_or_style.decompose()

    raw_text = soup.get_text()
    elapsed_ms = round((time.time() - start) * 1000)
    return raw_text, response.status_code, elapsed_ms


def _read_latest_debug_html(debug_dir: Path, host: str, start_ts: float):
    if not debug_dir.exists():
        return ""
    candidates = []
    if host:
        candidates.extend(debug_dir.glob(f"{host}_*.html"))
    candidates.extend(debug_dir.glob("*.html"))
    recent = [path for path in candidates if path.stat().st_mtime >= start_ts - 2]
    if not recent:
        return ""
    latest = max(recent, key=lambda p: p.stat().st_mtime)
    try:
        return latest.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def _extract_jsonld_from_html(html: str):
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    texts = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text()
        if not raw:
            continue
        raw = raw.strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue

        candidates = data if isinstance(data, list) else [data]
        for item in candidates:
            if not isinstance(item, dict):
                continue
            for key in ("articleBody", "description", "headline"):
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    texts.append(value.strip())
    if not texts:
        return ""
    return max(texts, key=len)


def _fetch_rendered_html(url: str, errors):
    settings = load_settings()
    start_ts = time.time()
    host = ""
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        host = ""
    debug_dir = Path(settings.scraper_js_path).resolve().parent / "debug"
    try:
        _run_puppeteer(url, extra_env={"SAVE_HTML": "1", "MIN_TEXT_LEN": str(MIN_TEXT_LENGTH_BACKEND)})
    except Exception as exc:
        errors.append(f"jsonld_html:{exc}")
        return ""
    return _read_latest_debug_html(debug_dir, host, start_ts)


def extract_text(url: str):
    settings = load_settings()
    logger = logging.getLogger(__name__)
    extraction_meta = {
        "puppeteer": None,
        "requests": {"used": False, "status_code": None, "elapsed_ms": None},
    }
    source_warning = None

    start = time.time()
    puppeteer_meta = None
    try:
        text, meta = _run_puppeteer(url)
        puppeteer_meta = meta
        error = None
    except FileNotFoundError:
        error = "node_not_found"
        text = None
        puppeteer_meta = {"ok": False, "errors": [error], "method": "fallback"}
    except subprocess.TimeoutExpired:
        error = "puppeteer_timeout"
        text = None
        puppeteer_meta = {"ok": False, "errors": [error], "method": "fallback"}
    except Exception as exc:
        error = "puppeteer_error"
        text = None
        puppeteer_meta = {"ok": False, "errors": [error], "method": "fallback"}

    scrape_time_ms = (time.time() - start) * 1000
    if puppeteer_meta:
        extraction_meta["puppeteer"] = {
            "ok": puppeteer_meta.get("ok", False),
            "http_status": puppeteer_meta.get("http_status"),
            "final_url": puppeteer_meta.get("final_url") or url,
            "method": puppeteer_meta.get("method"),
            "text_len": puppeteer_meta.get("text_len", 0),
            "timings": puppeteer_meta.get("timings") or {},
            "errors": _sanitize_errors(puppeteer_meta.get("errors") or []),
        }
        logger.info(
            "Puppeteer meta url=%s final=%s status=%s method=%s timings=%s",
            url,
            puppeteer_meta.get("final_url") or url,
            puppeteer_meta.get("http_status"),
            puppeteer_meta.get("method"),
            puppeteer_meta.get("timings"),
        )

    blocked = _is_blocked(puppeteer_meta)
    if extraction_meta["puppeteer"]:
        extraction_meta["puppeteer"]["blocked"] = blocked

    text_len = len(text) if text else 0
    puppeteer_ok = bool(puppeteer_meta and puppeteer_meta.get("ok")) and text_len > 0
    if blocked:
        extraction_meta["assessment"] = "blocked"
        return (
            None,
            "Puppeteer",
            round(scrape_time_ms),
            False,
            "blocked",
            extraction_meta,
            None,
        )

    if puppeteer_ok:
        normalized, truncated = _normalize_text(text, settings.max_chars, collapse_whitespace=False)
        method = puppeteer_meta.get("method") or "fallback"
        source = f"Puppeteer ({method})"
        scrape_ms = round(puppeteer_meta.get("timings", {}).get("total_ms", scrape_time_ms))
        if text_len < MIN_TEXT_LENGTH_BACKEND:
            extraction_meta["assessment"] = (
                "weak_extraction" if method in {"iframe", "shadowdom", "treewalker"} else "low_text"
            )
            html = _fetch_rendered_html(
                puppeteer_meta.get("final_url") or url,
                puppeteer_meta.get("errors") or [],
            )
            jsonld_text = _extract_jsonld_from_html(html)
            if jsonld_text and len(jsonld_text) >= MIN_TEXT_LENGTH_BACKEND:
                jsonld_normalized, jsonld_truncated = _normalize_text(
                    jsonld_text, settings.max_chars, collapse_whitespace=True
                )
                extraction_meta["puppeteer"]["method_override"] = "jsonld"
                return (
                    jsonld_normalized,
                    "Puppeteer (jsonld)",
                    scrape_ms,
                    jsonld_truncated,
                    None,
                    extraction_meta,
                    None,
                )
            source_warning = (
                "Nội dung trích xuất rất ngắn; có thể do trang ít văn bản/consent/iframe. Kết quả dự đoán có thể kém tin cậy."
                "K?t qu? d? đoán có th? kém tin c?y."
            )
        if text_len >= MIN_TEXT_LENGTH_BACKEND:
            return (
                normalized,
                source,
                scrape_ms,
                truncated,
                None,
                extraction_meta,
                source_warning,
            )
    logger.warning("Puppeteer failed: %s", error)

    start = time.time()
    try:
        fallback_text, status_code, elapsed_ms = _run_fallback(url)
        extraction_meta["requests"] = {
            "used": True,
            "status_code": status_code,
            "elapsed_ms": elapsed_ms,
        }
        normalized, truncated = _normalize_text(fallback_text, settings.max_chars, collapse_whitespace=True)
        scrape_time_ms = elapsed_ms
        if normalized and len(normalized) < MIN_TEXT_LENGTH_BACKEND:
            source_warning = "Nội dung trích xuất rất ngắn; có thể do trang ít văn bản/consent/iframe. Kết quả dự đoán có thể kém tin cậy."
            if not extraction_meta.get("assessment"):
                extraction_meta["assessment"] = "low_text"
        if normalized and len(normalized) >= MIN_TEXT_LENGTH_BACKEND:
            source_warning = None
        if normalized:
            if len(normalized) < MIN_TEXT_LENGTH_BACKEND and puppeteer_ok:
                source_warning = "Nội dung trích xuất ngắn; có thể bị chặn/iframe/challenge"
                method = puppeteer_meta.get("method") or "fallback"
                source = f"Puppeteer ({method})"
                puppeteer_normalized, puppeteer_truncated = _normalize_text(
                    text, settings.max_chars, collapse_whitespace=False
                )
                return (
                    puppeteer_normalized,
                    source,
                    round(puppeteer_meta.get("timings", {}).get("total_ms", scrape_time_ms)),
                    puppeteer_truncated,
                    None,
                    extraction_meta,
                    source_warning,
                )
            return (
                normalized,
                "Requests",
                round(scrape_time_ms),
                truncated,
                None,
                extraction_meta,
                source_warning,
            )
        if puppeteer_ok:
            source_warning = "Nội dung trích xuất ngắn; có thể bị chặn/iframe/challenge"
            method = puppeteer_meta.get("method") or "fallback"
            source = f"Puppeteer ({method})"
            puppeteer_normalized, puppeteer_truncated = _normalize_text(
                text, settings.max_chars, collapse_whitespace=False
            )
            return (
                puppeteer_normalized,
                source,
                round(puppeteer_meta.get("timings", {}).get("total_ms", scrape_time_ms)),
                puppeteer_truncated,
                None,
                extraction_meta,
                source_warning,
            )
        error = "requests_empty"
    except requests.exceptions.Timeout:
        error = "requests_timeout"
    except requests.exceptions.RequestException as exc:
        error = "requests_error"
    except Exception as exc:
        error = "requests_error"

    scrape_time_ms = (time.time() - start) * 1000
    return (
        None,
        "Requests",
        round(scrape_time_ms),
        False,
        error,
        extraction_meta,
        source_warning,
    )
