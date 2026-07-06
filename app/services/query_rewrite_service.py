from __future__ import annotations

import logging
from pathlib import Path

from openai import OpenAI


PROMPT_FILE = (
    Path(__file__).resolve().parent.parent / "prompts" / "query_rewrite_prompt.txt"
)

logger = logging.getLogger(__name__)


class QueryRewriteService:
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

    def rewrite(self, *, query: str, recent_pairs: list[dict]) -> str:
        """Rewrite the query using recent conversation context.

        Returns the rewritten query, or the original query unchanged if:
        - recent_pairs is empty (no context to rewrite from)
        - OPENAI_API_KEY is not configured
        - The OpenAI call fails for any reason
        """
        if not recent_pairs:
            return query

        if not self.api_key:
            return query

        try:
            user_prompt = self._build_user_prompt(
                query=query, recent_pairs=recent_pairs
            )
            client = OpenAI(api_key=self.api_key)
            response = client.responses.create(
                model=self.model,
                instructions=self.system_prompt,
                input=user_prompt,
            )
            rewritten = (response.output_text or "").strip()
            if not rewritten:
                return query
            return rewritten
        except Exception as exc:
            logger.warning(
                "Query rewrite failed, falling back to original query: %s", exc
            )
            return query

    @staticmethod
    def _build_user_prompt(*, query: str, recent_pairs: list[dict]) -> str:
        history_block = "\n\n".join([
            f"User: {p['user']}\nAssistant: {p['assistant']}"
            for p in recent_pairs
        ])
        return "\n\n".join([
            "Recent conversation:",
            history_block,
            f"User query: {query}",
            "Rewritten query:",
        ])
