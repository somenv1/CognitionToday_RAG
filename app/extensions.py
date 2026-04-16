from __future__ import annotations

from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from redis import Redis
from rq import Queue


db = SQLAlchemy()
migrate = Migrate()
rq_queue: Queue | None = None


def init_extensions(app) -> None:
    global rq_queue

    db.init_app(app)
    migrate.init_app(app, db)

    redis_connection = Redis.from_url(app.config["REDIS_URL"])
    rq_queue = Queue("rag-jobs", connection=redis_connection)
