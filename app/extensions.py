from __future__ import annotations

from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from redis import Redis
from rq import Queue

from app.repositories.session_repo import SessionRepository


db = SQLAlchemy()
migrate = Migrate()
rq_queue: Queue | None = None
session_repo: SessionRepository | None = None


def init_extensions(app) -> None:
    global rq_queue, session_repo

    db.init_app(app)
    migrate.init_app(app, db)

    redis_connection = Redis.from_url(app.config["REDIS_URL"])
    rq_queue = Queue("rag-jobs", connection=redis_connection)
    session_repo = SessionRepository(redis_connection)
