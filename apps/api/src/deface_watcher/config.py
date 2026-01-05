import logging
import os
from dataclasses import dataclass
from pathlib import Path


def _get_project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _get_bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    root_dir: Path
    model_path: Path
    tokenizer_path: Path
    scraper_js_path: Path
    max_length: int
    process_timeout: int
    request_timeout: int
    max_chars: int
    strict_empty_text: bool
    return_tokens: bool
    log_level: str
    request_headers: dict


_SETTINGS = None


def load_settings() -> Settings:
    global _SETTINGS
    if _SETTINGS is not None:
        return _SETTINGS

    root_dir = _get_project_root()
    artifacts_dir = root_dir / "ml" / "artifacts"
    scraper_dir = root_dir / "tools" / "scraper"

    model_path = Path(os.getenv("MODEL_PATH", artifacts_dir / "bilstm_defacement_model.keras"))
    tokenizer_path = Path(os.getenv("TOKENIZER_PATH", artifacts_dir / "tokenizer.json"))
    scraper_js_path = Path(os.getenv("SCRAPER_JS_PATH", scraper_dir / "get_text_puppeteer.js"))

    _SETTINGS = Settings(
        root_dir=root_dir,
        model_path=model_path,
        tokenizer_path=tokenizer_path,
        scraper_js_path=scraper_js_path,
        max_length=128,
        process_timeout=int(os.getenv("PROCESS_TIMEOUT", "15")),
        request_timeout=int(os.getenv("REQUEST_TIMEOUT", "6")),
        max_chars=int(os.getenv("MAX_CHARS", "20000")),
        strict_empty_text=_get_bool_env("STRICT_EMPTY_TEXT", False),
        return_tokens=_get_bool_env("RETURN_TOKENS", False),
        log_level=os.getenv("LOG_LEVEL", "WARNING").upper(),
        request_headers={
            "User-Agent": os.getenv(
                "REQUEST_UA",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/91.0.4472.124 Safari/537.36",
            )
        },
    )
    return _SETTINGS


def configure_logging(level: str) -> None:
    root_logger = logging.getLogger()
    if root_logger.handlers:
        root_logger.setLevel(level)
        return

    logging.basicConfig(
        level=level,
        format="%(levelname)s %(name)s - %(message)s",
    )
