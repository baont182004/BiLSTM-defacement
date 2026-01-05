import os
import sys
from pathlib import Path


def _ensure_src_path():
    src_path = Path(__file__).resolve().parent / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))


def main() -> None:
    _ensure_src_path()
    from deface_watcher.web import create_app

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "5000"))
    app = create_app()
    print(f"* Server running on http://127.0.0.1:{port}")
    app.run(host=host, port=port, debug=True, use_reloader=False)


if __name__ == "__main__":
    main()
