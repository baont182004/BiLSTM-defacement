import os
import sys
from pathlib import Path


def _ensure_import_path():
    repo_root = Path(__file__).resolve().parents[1]
    src_path = repo_root / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))


def run_smoke_test():
    _ensure_import_path()
    from deface_watcher.web import create_app
    from deface_watcher.services import extractor as extractor_module

    app = create_app()
    client = app.test_client()

    original_extract = extractor_module.extract_text
    extractor_module.extract_text = lambda url: ("Smoke test content", "Mock", 1, False, None)

    try:
        health = client.get("/health")
        assert health.status_code == 200, health.data

        response = client.post("/predict", json={"url": "https://example.com"})
        assert response.status_code == 200, response.data
        payload = response.get_json()
        assert "status" in payload
        assert "probability" in payload
        assert payload.get("checked_url")
    finally:
        extractor_module.extract_text = original_extract


if __name__ == "__main__":
    os.environ.setdefault("RETURN_TOKENS", "1")
    run_smoke_test()
    print("Smoke test passed.")
