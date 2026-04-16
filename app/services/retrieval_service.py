from __future__ import annotations

from dataclasses import asdict, dataclass

from app.repositories.chunk_repo import ChunkRepository
from app.repositories.query_log_repo import QueryLogRepository
from app.services.embedding_service import EmbeddingService
from app.services.rerank_service import RerankService
from app.models.schema import QueryLog


@dataclass
class RetrievedChunk:
    chunk_id: str
    text: str
    title: str
    url: str
    heading_path: list[str]
    retrieval_score: float
    retrieval_source: str


@dataclass
class RetrievalResult:
    query: str
    normalized_query: str
    chunks: list[RetrievedChunk]
    vector_top_k: int
    lexical_top_k: int
    rerank_top_k: int

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "normalized_query": self.normalized_query,
            "vector_top_k": self.vector_top_k,
            "lexical_top_k": self.lexical_top_k,
            "rerank_top_k": self.rerank_top_k,
            "chunks": [asdict(chunk) for chunk in self.chunks],
        }


class RetrievalService:
    def __init__(self, config) -> None:
        self.config = config
        self.chunk_repo = ChunkRepository()
        self.query_log_repo = QueryLogRepository()
        self.embedding_service = EmbeddingService(config)
        self.rerank_service = RerankService()

    def retrieve(self, query: str, filters: dict | None = None) -> RetrievalResult:
        normalized_query = " ".join(query.lower().split())
        filters = filters or {}

        vector_candidates = []
        try:
            query_embedding = self.embedding_service.embed_texts([normalized_query])[0]
            vector_candidates = self.chunk_repo.vector_search(
                query_embedding=query_embedding,
                top_k=self.config["RAG_VECTOR_TOP_K"],
                filters=filters,
            )
        except RuntimeError:
            query_embedding = None

        lexical_candidates = self.chunk_repo.keyword_search(
            query=normalized_query,
            top_k=self.config["RAG_LEXICAL_TOP_K"],
        )

        merged = self._merge_candidates(vector_candidates, lexical_candidates)
        reranked = self.rerank_service.rerank(
            query=normalized_query,
            candidates=merged,
            limit=self.config["RAG_RERANK_TOP_K"],
        )

        final_chunks = [
            RetrievedChunk(
                chunk_id=chunk.id,
                text=chunk.text,
                title=chunk.document_version.document.title,
                url=chunk.document_version.document.canonical_url,
                heading_path=chunk.heading_path,
                retrieval_score=score,
                retrieval_source=source,
            )
            for chunk, score, source in reranked[: self.config["RAG_FINAL_CONTEXT_K"]]
        ]

        retrieval_result = RetrievalResult(
            query=query,
            normalized_query=normalized_query,
            chunks=final_chunks,
            vector_top_k=self.config["RAG_VECTOR_TOP_K"],
            lexical_top_k=self.config["RAG_LEXICAL_TOP_K"],
            rerank_top_k=self.config["RAG_RERANK_TOP_K"],
        )

        query_log = QueryLog(
            query_text=query,
            normalized_query=normalized_query,
            filters_json=filters,
            retrieved_chunk_ids=[chunk.chunk_id for chunk in final_chunks],
            retrieval_debug_json=retrieval_result.to_dict(),
            answer_json={},
        )
        self.query_log_repo.save(query_log)

        return retrieval_result

    @staticmethod
    def _merge_candidates(vector_candidates, lexical_candidates):
        merged = {}

        for rank, chunk in enumerate(vector_candidates, start=1):
            merged.setdefault(chunk.id, {"chunk": chunk, "score": 0.0, "source": set()})
            merged[chunk.id]["score"] += 1.0 / (60 + rank)
            merged[chunk.id]["source"].add("vector")

        for rank, chunk in enumerate(lexical_candidates, start=1):
            merged.setdefault(chunk.id, {"chunk": chunk, "score": 0.0, "source": set()})
            merged[chunk.id]["score"] += 1.0 / (60 + rank)
            merged[chunk.id]["source"].add("lexical")

        return [
            (payload["chunk"], payload["score"], "+".join(sorted(payload["source"])))
            for payload in merged.values()
        ]
