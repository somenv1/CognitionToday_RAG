from __future__ import annotations


# How much to weight relevance vs diversity. 1.0 = pure relevance (no diversity),
# 0.0 = pure diversity. 0.7 favors relevance while still nudging toward diversity.
MMR_LAMBDA = 0.7

# Max chunks allowed from any single article (source URL) in the final result.
MAX_CHUNKS_PER_DOCUMENT = 2

# How much extra score to add per query term found in the article's title.
# Kept small so it nudges ordering without dominating semantic+lexical signals.
TITLE_MATCH_BOOST = 0.005


class RerankService:
    def rerank(self, query: str, candidates: list[tuple], limit: int) -> list[tuple]:
        """Rerank candidates with three diversity-aware techniques:

        1. Title-match boost: chunks from articles whose title contains query
           terms get a small relevance boost.
        2. MMR (Maximal Marginal Relevance) with Jaccard similarity: balances
           pure relevance with diversity from already-selected chunks.
        3. Per-document cap: limits how many chunks from one article can
           appear in the final result.
        """
        if not candidates:
            return []

        query_terms = self._tokenize(query)

        # Step 1: Compute an enhanced relevance score for each candidate.
        # Existing logic (RRF score + lexical overlap) + new title-match boost.
        scored = self._score_candidates(query_terms, candidates)

        # Step 2: Apply MMR with per-document cap to pick the final set.
        return self._mmr_select_with_doc_cap(
            scored_candidates=scored, limit=limit, query_terms=query_terms
        )

    def _score_candidates(
        self, query_terms: set, candidates: list[tuple]
    ) -> list[tuple]:
        rescored = []
        for chunk, score, source in candidates:
            chunk_terms = self._tokenize(chunk.text)

            # Existing logic: lexical overlap boost.
            lexical_overlap = len(query_terms.intersection(chunk_terms))
            overlap_ratio = lexical_overlap / max(len(query_terms), 1)
            new_score = score + (overlap_ratio * 0.01)

            # New: title-match boost. If query terms appear in the document
            # title, that's a strong signal of intent match.
            title = self._get_title(chunk)
            title_terms = self._tokenize(title)
            title_matches = len(query_terms.intersection(title_terms))
            new_score += title_matches * TITLE_MATCH_BOOST

            rescored.append((chunk, new_score, source))

        rescored.sort(key=lambda item: item[1], reverse=True)
        return rescored

    def _mmr_select_with_doc_cap(
        self,
        *,
        scored_candidates: list[tuple],
        limit: int,
        query_terms: set,
    ) -> list[tuple]:
        """Iteratively select chunks balancing relevance and diversity, with
        a hard cap on how many chunks per article we allow."""
        selected: list[tuple] = []
        selected_term_sets: list[set] = []
        doc_counts: dict[str, int] = {}
        remaining = list(scored_candidates)

        while remaining and len(selected) < limit:
            best_index = None
            best_mmr_score = float("-inf")

            for i, (chunk, relevance, source) in enumerate(remaining):
                # Skip if this article has already hit its cap.
                doc_url = self._get_url(chunk)
                if doc_counts.get(doc_url, 0) >= MAX_CHUNKS_PER_DOCUMENT:
                    continue

                # Compute the MMR score: lambda * relevance minus
                # (1 - lambda) * max similarity to anything already selected.
                if not selected_term_sets:
                    # First pick — just take the most relevant.
                    mmr_score = relevance
                else:
                    chunk_terms = self._tokenize(chunk.text)
                    max_sim = max(
                        self._jaccard(chunk_terms, prev_terms)
                        for prev_terms in selected_term_sets
                    )
                    mmr_score = (
                        MMR_LAMBDA * relevance
                        - (1 - MMR_LAMBDA) * max_sim
                    )

                if mmr_score > best_mmr_score:
                    best_mmr_score = mmr_score
                    best_index = i

            if best_index is None:
                # All remaining candidates are blocked by doc caps.
                break

            chosen = remaining.pop(best_index)
            chunk, _, _ = chosen
            selected.append(chosen)
            selected_term_sets.append(self._tokenize(chunk.text))
            doc_counts[self._get_url(chunk)] = (
                doc_counts.get(self._get_url(chunk), 0) + 1
            )

        return selected

    @staticmethod
    def _tokenize(text: str) -> set:
        """Lowercase-and-split tokenizer. Good enough for Jaccard similarity
        on natural language content."""
        if not text:
            return set()
        return set(text.lower().split())

    @staticmethod
    def _jaccard(a: set, b: set) -> float:
        """Jaccard similarity: |A ∩ B| / |A ∪ B|. Returns 0 if both empty."""
        if not a and not b:
            return 0.0
        union = a | b
        if not union:
            return 0.0
        return len(a & b) / len(union)

    @staticmethod
    def _get_url(chunk) -> str:
        """Get the article URL for a chunk, handling both RetrievedChunk
        (which has chunk.url) and Chunk (which has document_version.document.canonical_url)."""
        if hasattr(chunk, "url"):
            return chunk.url
        try:
            return chunk.document_version.document.canonical_url
        except AttributeError:
            return ""

    @staticmethod
    def _get_title(chunk) -> str:
        """Get the article title for a chunk, handling both shapes."""
        if hasattr(chunk, "title"):
            return chunk.title
        try:
            return chunk.document_version.document.title
        except AttributeError:
            return ""
