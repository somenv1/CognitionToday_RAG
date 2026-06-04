from __future__ import annotations

from sqlalchemy import select

from app.extensions import db
from app.models.schema import Concept, DocumentVersion


class ConceptRepository:
    def bulk_replace_for_version(self, document_version_id: str, concepts: list[Concept]) -> None:
        Concept.query.filter_by(document_version_id=document_version_id).delete()
        db.session.add_all(concepts)
        db.session.commit()

    def list_for_version(self, document_version_id: str) -> list[Concept]:
        return (
            Concept.query.filter_by(document_version_id=document_version_id)
            .order_by(Concept.extraction_order.asc())
            .all()
        )

    def vector_search(
        self,
        query_embedding: list[float],
        top_k: int,
        filters: dict | None = None,
    ) -> list[Concept]:
        filters = filters or {}
        stmt = (
            select(Concept)
            .join(DocumentVersion, Concept.document_version_id == DocumentVersion.id)
            .where(Concept.embedding.isnot(None))
            .where(DocumentVersion.is_active.is_(True))
        )

        if "document_version_id" in filters:
            stmt = stmt.where(Concept.document_version_id == filters["document_version_id"])

        stmt = stmt.order_by(Concept.embedding.cosine_distance(query_embedding)).limit(top_k)
        return list(db.session.scalars(stmt))
