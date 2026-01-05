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
    command = ["node", str(settings.scraper_js_path), url]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=settings.process_timeout,
        check=False,
    )
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        return None, f"puppeteer_failed:{stderr.splitlines()[0] if stderr else 'unknown'}"

    return result.stdout or "", None


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
    try:
        text, error = _run_puppeteer(url)
        if error:
            logger.warning("Puppeteer failed: %s", error)
    except FileNotFoundError:
        error = "node_not_found"
        text = None
        logger.warning("Puppeteer failed: %s", error)
    except subprocess.TimeoutExpired:
        error = "puppeteer_timeout"
        text = None
        logger.warning("Puppeteer failed: %s", error)
    except Exception:
        error = "puppeteer_error"
        text = None
        logger.warning("Puppeteer failed: %s", error)

    scrape_time_ms = (time.time() - start) * 1000
    if text is not None:
        normalized, truncated = _normalize_text(text, settings.max_chars)
        return normalized, "Puppeteer", round(scrape_time_ms), truncated, None

    start = time.time()
    try:
        fallback_text = _run_fallback(url)
        normalized, truncated = _normalize_text(fallback_text, settings.max_chars)
        scrape_time_ms = (time.time() - start) * 1000
        return normalized, "Requests", round(scrape_time_ms), truncated, None
    except requests.exceptions.Timeout:
        error = "requests_timeout"
    except requests.exceptions.RequestException:
        error = "requests_error"
    except Exception:
        error = "requests_error"

    logger.warning("Requests fallback failed: %s", error)

    scrape_time_ms = (time.time() - start) * 1000
    return None, "Requests", round(scrape_time_ms), False, error
