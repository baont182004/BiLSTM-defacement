import logging
import os
import warnings
from flask import Flask

from .api import api_bp
from .config import configure_logging, load_settings
from .routes import ui_bp


def create_app():
    settings = load_settings()
    configure_logging(settings.log_level)
    log_level = os.getenv("LOG_LEVEL", "WARNING").upper()
    if log_level != "INFO":
        werk_logger = logging.getLogger("werkzeug")
        werk_logger.setLevel(logging.ERROR)
        werk_logger.propagate = False

    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )
    app.config["SETTINGS"] = settings
    app.json.ensure_ascii = False

    warnings.filterwarnings("ignore", message="Unverified HTTPS request")

    app.register_blueprint(ui_bp)
    app.register_blueprint(api_bp)

    return app


if __name__ == "__main__":
    application = create_app()
    application.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
