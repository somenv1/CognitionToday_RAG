class RerankService:
    def rerank(self, query: str, candidates: list[tuple], limit: int) -> list[tuple]:
        query_terms = set(query.lower().split())

        rescored = []
        for chunk, score, source in candidates:
            chunk_terms = set(chunk.text.lower().split())
            lexical_overlap = len(query_terms.intersection(chunk_terms))
            overlap_ratio = lexical_overlap / max(len(query_terms), 1)
            rescored.append((chunk, score + (overlap_ratio * 0.01), source))

        rescored.sort(key=lambda item: item[1], reverse=True)
        return rescored[:limit]
