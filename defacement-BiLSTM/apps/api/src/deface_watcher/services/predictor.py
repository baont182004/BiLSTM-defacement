import logging
import time

import numpy as np

from ..config import load_settings
from .artifacts import get_artifacts
from .preprocess import preprocess_text


def predict_text(text: str):
    settings = load_settings()
    model, tokenizer = get_artifacts()

    text_to_tokenize = text if isinstance(text, str) else ""
    processed = preprocess_text(text_to_tokenize, tokenizer, settings.max_length)
    tokenized_sequence = processed[0].tolist()

    if not text_to_tokenize:
        if settings.strict_empty_text:
            return "Không đủ dữ liệu", 0.0, tokenized_sequence, 0
        return "Bình thường", 0.0, tokenized_sequence, 0

    logger = logging.getLogger(__name__)
    start = time.time()
    prediction = model.predict(processed, verbose=0)
    predict_time_ms = (time.time() - start) * 1000

    probability = float(prediction[0][1])
    predicted_class_index = int(np.argmax(prediction, axis=1)[0])
    status = "Tấn công Deface" if predicted_class_index == 1 else "Bình thường"
    logger.debug("Prediction done: status=%s prob=%.4f", status, probability)

    return status, probability, tokenized_sequence, round(predict_time_ms)
