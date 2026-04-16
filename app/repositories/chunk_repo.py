from __future__ import annotations

from sqlalchemy import desc, or_, select

from app.extensions import db
from app.models.schema import Chunk, DocumentVersion


class ChunkRepository:
    def bulk_replace_for_version(self, document_version_id: str, chunks: list[Chunk]) -> None:
        Chunk.query.filter_by(document_version_id=document_version_id).delete()
        db.session.add_all(chunks)
        db.session.commit()

    def list_for_version(self, document_version_id: str) -> list[Chunk]:
        return (
            Chunk.query.filter_by(document_version_id=document_version_id)
            .order_by(Chunk.chunk_index.asc())
            .all()
        )

    def vector_search(
        self,
        query_embedding: list[float],
        top_k: int,
        filters: dict | None = None,
    ) -> list[Chunk]:
        filters = filters or {}
        stmt = (
            select(Chunk)
            .join(DocumentVersion, Chunk.document_version_id == DocumentVersion.id)
            .where(Chunk.embedding.isnot(None))
            .where(DocumentVersion.is_active.is_(True))
        )

        if "document_version_id" in filters:
            stmt = stmt.where(Chunk.document_version_id == filters["document_version_id"])

        stmt = stmt.order_by(Chunk.embedding.cosine_distance(query_embedding)).limit(top_k)
        return list(db.session.scalars(stmt))

    def keyword_search(self, query: str, top_k: int) -> list[Chunk]:
        stopwords = {
            "the",
            "is",
            "a",
            "an",
            "and",
            "or",
            "of",
            "to",
            "in",
            "what",
            "about",
        }
        terms = [
            term
            for term in query.split()
            if len(term) >= 2 and term not in stopwords
        ]

        if not terms:
            terms = [query]

        term_filters = [Chunk.text.ilike(f"%{term}%") for term in terms]
        return (
            Chunk.query.join(
                DocumentVersion,
                Chunk.document_version_id == DocumentVersion.id,
            )
            .filter(DocumentVersion.is_active.is_(True))
            .filter(or_(*term_filters))
            .order_by(desc(Chunk.updated_at))
            .limit(top_k)
            .all()
        )
