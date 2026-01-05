import logging
import time
import uuid

from flask import Blueprint, jsonify, request

from .config import load_settings
from .services.extractor import extract_text
from .services.predictor import predict_text

api_bp = Blueprint("api", __name__)


def _normalize_url(value: str):
    if not value:
        return None
    url = value.strip()
    if not url:
        return None
    if not url.startswith(("http://", "https://")):
        url = f"http://{url}"
    return url


@api_bp.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@api_bp.route("/predict", methods=["POST"])
def predict():
    settings = load_settings()
    logger = logging.getLogger(__name__)
    request_id = str(uuid.uuid4())

    start_time = time.time()
    data = request.get_json(silent=True) or {}
    url = _normalize_url(data.get("url"))
    if not url:
        return jsonify({"error": "Dữ liệu JSON không hợp lệ hoặc thiếu URL.", "request_id": request_id}), 400

    try:
        (
            text,
            source,
            scrape_time_ms,
            truncated,
            scrape_error,
            extraction_meta,
            source_warning,
        ) = extract_text(url)
        if text is None:
            error_message = "Không th? cào d? li?u t? URL này (b? ch?n/timeout/l?i)."
            if scrape_error == "blocked":
                error_message = (
                    "Trang web có cơ chế chống bot hoặc yêu cầu xác minh; không thể trích xuất nội dung."
                )
            return (
                jsonify(
                    {
                        "error": "Không thể cào dữ liệu từ URL này (bị chặn/timeout/lỗi).",
                        "request_id": request_id,
                        "checked_url": url,
                        "source": source,
                        "scrape_time_ms": scrape_time_ms,
                        "scrape_error": scrape_error,
                        "extraction_meta": extraction_meta,
                    }
                ),
                400,
            )

        status, probability, tokenized_sequence, predict_time_ms = predict_text(text)
        total_time_ms = round((time.time() - start_time) * 1000)

        include_tokens = settings.return_tokens or request.args.get("debug") == "1"
        text_response = text if text else "(Không tìm thấy văn bản)"
        response = {
            "status": status,
            "probability": float(probability),
            "extracted_text": text_response,
            "extracted_text_truncated": truncated,
            "tokenized_sequence": tokenized_sequence if include_tokens else None,
            "tokenized_sequence_included": include_tokens,
            "checked_url": url,
            "source": source,
            "scrape_time_ms": scrape_time_ms,
            "predict_time_ms": predict_time_ms,
            "total_time_ms": total_time_ms,
            "request_id": request_id,
        }
        if extraction_meta:
            response["extraction_meta"] = extraction_meta
        if source_warning:
            response["source_warning"] = source_warning

        logger.info(
            "predict url=%s source=%s scrape_ms=%s predict_ms=%s status=%s prob=%.4f",
            url,
            source,
            scrape_time_ms,
            predict_time_ms,
            status,
            probability,
        )
        return jsonify(response)
    except Exception:
        logger.exception("Unhandled error in /predict request_id=%s", request_id)
        return jsonify({"error": "Lỗi máy chủ không mong muốn.", "request_id": request_id}), 500
