from flask import Blueprint


health_bp = Blueprint("health", __name__)


@health_bp.get("/healthz")
def healthz():
    return {"status": "ok"}, 200
