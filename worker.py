from redis import Redis
from rq import Worker

from app import create_app
from app import extensions


app = create_app()


def main() -> None:
    with app.app_context():
        connection = Redis.from_url(app.config["REDIS_URL"])
        if extensions.rq_queue is None:
            raise RuntimeError("RQ queue is not initialized")

        worker = Worker([extensions.rq_queue.name], connection=connection)
        worker.work()


if __name__ == "__main__":
    main()
