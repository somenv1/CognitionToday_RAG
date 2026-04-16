from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from openai import OpenAI


PROMPT_FILE = Path(__file__).resolve().parent.parent / "prompts" / "answer_prompt.txt"


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

        citations = [
            {"url": chunk.url, "title": chunk.title, "chunk_id": chunk.chunk_id}
            for chunk in retrieval_result.chunks
        ]

        if not self.api_key:
            return AnswerResult(
                answer=(
                    "Local retrieval is working and relevant blog chunks were found. "
                    "Set OPENAI_API_KEY to generate a grounded natural-language answer."
                ),
                citations=citations,
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
            query=query, retrieval_result=retrieval_result
        )
        client = OpenAI(api_key=self.api_key)
        response = client.responses.create(
            model=self.model,
            instructions=self.system_prompt,
            input=user_prompt,
        )

        return AnswerResult(
            answer=response.output_text,
            citations=citations,
            confidence="medium",
            grounded=True,
        )

    @staticmethod
    def _build_user_prompt(*, query: str, retrieval_result) -> str:
        context_blocks = []
        for chunk in retrieval_result.chunks:
            context_blocks.append(
                "\n".join(
                    [
                        f"Chunk ID: {chunk.chunk_id}",
                        f"Title: {chunk.title}",
                        f"URL: {chunk.url}",
                        f"Heading Path: {' > '.join(chunk.heading_path)}",
                        "Content:",
                        chunk.text,
                    ]
                )
            )

        return "\n\n".join(
            [
                f"User question: {query}",
                "Retrieved context:",
                "\n\n---\n\n".join(context_blocks),
            ]
        )
