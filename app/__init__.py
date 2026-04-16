from __future__ import annotations

from flask import Flask

from app.api import register_blueprints
from app.config import config_by_name
from app.extensions import init_extensions
from app.models import schema  # noqa: F401


def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__)
    selected_config = config_name or "default"
    app.config.from_object(config_by_name[selected_config])

    init_extensions(app)
    register_blueprints(app)

    @app.get("/")
    def index() -> dict[str, str]:
        return {
            "service": "cognition-today-rag-assistant",
            "status": "ok",
        }

    return app
