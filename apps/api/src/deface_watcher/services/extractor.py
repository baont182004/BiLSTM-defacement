import json
import logging
import subprocess
import time

import requests
from bs4 import BeautifulSoup

from ..config import load_settings


def _normalize_text(text: str, max_chars: int):
    cleaned = " ".join(text.split()).strip()
    if len(cleaned) > max_chars:
        return cleaned[:max_chars], True
    return cleaned, False


def _run_puppeteer(url: str):
    settings = load_settings()
    command = ["node", str(settings.scraper_js_path), url, "--json"]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=settings.process_timeout,
        check=False,
    )
    if result.returncode != 0:
        return None, f"puppeteer_failed:{result.stderr.strip() or 'unknown'}"

    raw_output = result.stdout.strip()
    if not raw_output:
        return None, "puppeteer_empty"

    try:
        payload = json.loads(raw_output)
    except json.JSONDecodeError:
        return raw_output, None

    if not payload.get("ok"):
        return None, f"puppeteer_error:{payload.get('errors')}"

    return payload.get("text", ""), payload


def _run_fallback(url: str):
    settings = load_settings()
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
    return raw_text


def extract_text(url: str):
    settings = load_settings()
    logger = logging.getLogger(__name__)

    start = time.time()
    puppeteer_meta = None
    try:
        text, meta = _run_puppeteer(url)
        if isinstance(meta, dict):
            puppeteer_meta = meta
            error = None
        else:
            error = meta
    except FileNotFoundError:
        error = "node_not_found"
        text = None
    except subprocess.TimeoutExpired:
        error = "puppeteer_timeout"
        text = None
    except Exception as exc:
        error = f"puppeteer_error:{exc}"
        text = None

    scrape_time_ms = (time.time() - start) * 1000
    if text is not None:
        normalized, truncated = _normalize_text(text, settings.max_chars)
        if puppeteer_meta:
            logger.info(
                "Puppeteer meta url=%s final=%s status=%s timings=%s",
                url,
                puppeteer_meta.get("finalUrl"),
                puppeteer_meta.get("httpStatus"),
                puppeteer_meta.get("timings"),
            )
        return normalized, "Puppeteer", round(scrape_time_ms), truncated, None

    logger.warning("Puppeteer failed: %s", error)

    start = time.time()
    try:
        fallback_text = _run_fallback(url)
        normalized, truncated = _normalize_text(fallback_text, settings.max_chars)
        scrape_time_ms = (time.time() - start) * 1000
        return normalized, "Requests", round(scrape_time_ms), truncated, None
    except requests.exceptions.Timeout:
        error = "requests_timeout"
    except requests.exceptions.RequestException as exc:
        error = f"requests_error:{exc}"
    except Exception as exc:
        error = f"requests_error:{exc}"

    scrape_time_ms = (time.time() - start) * 1000
    return None, "Requests", round(scrape_time_ms), False, error
