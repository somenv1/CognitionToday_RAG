from app.extensions import db
from app.models.schema import QueryLog


class QueryLogRepository:
    def save(self, query_log: QueryLog) -> QueryLog:
        db.session.add(query_log)
        db.session.commit()
        return query_log
