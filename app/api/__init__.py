from flask import Flask

from app.api.admin import admin_bp
from app.api.chat import chat_bp
from app.api.health import health_bp


def register_blueprints(app: Flask) -> None:
    app.register_blueprint(chat_bp, url_prefix="/api")
    app.register_blueprint(admin_bp, url_prefix="/api/admin")
    app.register_blueprint(health_bp)
