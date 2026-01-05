import logging
import os
from threading import Lock

from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing.text import tokenizer_from_json

from ..config import load_settings

_LOCK = Lock()
_CACHE = None


def get_artifacts():
    global _CACHE
    if _CACHE is not None:
        return _CACHE

    with _LOCK:
        if _CACHE is not None:
            return _CACHE

        settings = load_settings()
        logger = logging.getLogger(__name__)
        logger.info(
            "Loading artifacts (pid=%s): model=%s tokenizer=%s",
            os.getpid(),
            settings.model_path,
            settings.tokenizer_path,
        )

        if not settings.model_path.exists():
            raise FileNotFoundError(f"Model not found: {settings.model_path}")
        if not settings.tokenizer_path.exists():
            raise FileNotFoundError(f"Tokenizer not found: {settings.tokenizer_path}")

        model = load_model(settings.model_path)
        with settings.tokenizer_path.open("r", encoding="utf-8") as handle:
            tokenizer = tokenizer_from_json(handle.read())

        _CACHE = (model, tokenizer)
        logger.info("Artifacts loaded successfully (pid=%s).", os.getpid())
        return _CACHE
