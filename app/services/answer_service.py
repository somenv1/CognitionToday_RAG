from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from openai import OpenAI


PROMPT_FILE = Path(__file__).resolve().parent.parent / "prompts" / "answer_prompt.txt"

logger = logging.getLogger(__name__)


class InsufficientContextError(Exception):
    pass


@dataclass
class AnswerResult:
    answer: str
    citations: list[dict]
    confidence: str
    grounded: bool


class AnswerService:
    def __init__(self, config) -> None:
        self.config = config
        self.api_key = config.get("OPENAI_API_KEY")
        self.model = config["OPENAI_CHAT_MODEL"]
        self._system_prompt: str | None = None

    @property
    def system_prompt(self) -> str:
        if self._system_prompt is None:
            self._system_prompt = PROMPT_FILE.read_text().strip()
        return self._system_prompt

    def answer(self, *, query: str, retrieval_result) -> AnswerResult:
        if not retrieval_result.chunks:
            raise InsufficientContextError(
                "I do not have enough evidence from the blog to answer that."
            )

        final_concept_k = self.config.get("RAG_FINAL_CONCEPT_K", 8)
        concepts = retrieval_result.concepts[:final_concept_k]

        chunk_citations = [
            {"url": chunk.url, "title": chunk.title, "source": "chunk", "chunk_id": chunk.chunk_id}
            for chunk in retrieval_result.chunks
        ]
        concept_citations = [
            {"url": concept.url, "title": concept.title, "source": "concept",
             "concept_id": concept.concept_id, "concept_term": concept.term}
            for concept in concepts
        ]
        # Order matters: must match the source numbering in _build_user_prompt.
        # Chunks occupy indices 1..len(chunks), concepts occupy indices len(chunks)+1..end.
        all_citations = chunk_citations + concept_citations

        if not self.api_key:
            return AnswerResult(
                answer=(
                    "Local retrieval is working — relevant blog chunks and concepts "
                    "were found. Set OPENAI_API_KEY to generate a grounded "
                    "natural-language answer."
                ),
                citations=all_citations,
                confidence="medium",
                grounded=True,
            )

        top_score = retrieval_result.chunks[0].retrieval_score
        if top_score < self.config["RAG_SCORE_THRESHOLD"]:
            raise InsufficientContextError(
                "I found related content, but not enough strong evidence "
                "to answer reliably."
            )

        user_prompt = self._build_user_prompt(
            query=query, chunks=retrieval_result.chunks, concepts=concepts
        )
        client = OpenAI(api_key=self.api_key)

        # Request structured JSON output. The prompt instructs the model to return
        # {"answer": "...", "used_sources": [1, 3]}.
        response = client.responses.create(
            model=self.model,
            instructions=self.system_prompt,
            input=user_prompt,
            text={"format": {"type": "json_object"}},
        )

        raw_output = response.output_text

        # Parse the JSON. Fall back gracefully on any failure — we'd rather show
        # raw text with all citations than break the UX.
        answer_text, used_source_indices = self._parse_structured_response(raw_output)

        # Filter citations based on what the LLM said it used.
        # - None → parse failure, show all retrieved citations (degraded but safe)
        # - [] → LLM explicitly used no sources (refusal case), show no citations
        # - [n, m, ...] → filter to only those source indices
        if used_source_indices is None:
            filtered_citations = all_citations
            logger.warning(
                "Could not parse used_sources from LLM response; showing all citations"
            )
        elif len(used_source_indices) == 0:
            filtered_citations = []
        else:
            filtered_citations = self._filter_citations_by_index(
                all_citations, used_source_indices
            )

        return AnswerResult(
            answer=answer_text,
            citations=filtered_citations,
            confidence="medium",
            grounded=True,
        )

    @staticmethod
    def _parse_structured_response(raw_output: str) -> tuple[str, list[int] | None]:
        """Parse the LLM's JSON output into (answer_text, used_source_indices).

        Returns (raw_output, None) on any parse failure so the caller falls back
        to showing the unparsed text with all citations.
        """
        try:
            parsed = json.loads(raw_output)
        except (json.JSONDecodeError, TypeError):
            return raw_output, None

        if not isinstance(parsed, dict):
            return raw_output, None

        answer_text = parsed.get("answer")
        if not isinstance(answer_text, str):
            return raw_output, None

        used_sources = parsed.get("used_sources")
        if not isinstance(used_sources, list):
            return answer_text, None

        # Validate each index is an integer; silently drop non-integer entries.
        clean_indices = [i for i in used_sources if isinstance(i, int)]
        return answer_text, clean_indices

    @staticmethod
    def _filter_citations_by_index(
        all_citations: list[dict], used_indices: list[int]
    ) -> list[dict]:
        """Keep only citations at the given 1-indexed positions, deduped by URL."""
        seen_urls = set()
        filtered = []
        for index in used_indices:
            zero_based = index - 1
            if 0 <= zero_based < len(all_citations):
                citation = all_citations[zero_based]
                if citation["url"] not in seen_urls:
                    seen_urls.add(citation["url"])
                    filtered.append(citation)
        return filtered

    @staticmethod
    def _build_user_prompt(*, query: str, chunks, concepts) -> str:
        chunk_blocks = []
        for index, chunk in enumerate(chunks, start=1):
            chunk_blocks.append(
                "\n".join(
                    [
                        f"[Source {index}]",
                        f"Title: {chunk.title}",
                        f"URL: {chunk.url}",
                        f"Section: {' > '.join(chunk.heading_path)}",
                        "",
                        chunk.text,
                    ]
                )
            )

        sections = [
            f"User question: {query}",
            "ARTICLE PASSAGES:\n" + "\n\n---\n\n".join(chunk_blocks),
        ]

        if concepts:
            concept_blocks = []
            for index, concept in enumerate(concepts, start=len(chunks) + 1):
                concept_blocks.append(
                    "\n".join(
                        [
                            f"[Source {index}]",
                            f"Term: {concept.term}",
                            f"Article: {concept.title}",
                            f"URL: {concept.url}",
                            "",
                            concept.definition,
                        ]
                    )
                )
            sections.append("KEY CONCEPTS:\n" + "\n\n---\n\n".join(concept_blocks))

        sections.append("Respond with a JSON object as specified in the instructions.")

        return "\n\n".join(sections)
