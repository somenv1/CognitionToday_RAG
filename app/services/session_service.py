from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.services.embedding_service import EmbeddingService


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SessionService:
    def __init__(self, config, session_repo):
        self.config = config
        self.session_repo = session_repo
        self.embedding_service = EmbeddingService(config)

    def get_or_create(self, session_id: str | None) -> tuple[str, dict]:
        """Return existing session if session_id is given and live; else create fresh."""
        if session_id:
            session = self.session_repo.get_session(session_id)
            if session is not None:
                return session_id, session
        return self.session_repo.create_session()

    def extract_recent_pairs(self, session: dict) -> list[dict]:
        """Return the last n_pairs of (user, assistant) dicts in chronological order."""
        n_pairs = self.config["RAG_HISTORY_RECENT_PAIRS"]
        turns = session.get("turns", [])
        pairs: list[dict] = []
        i = len(turns) - 1
        while i >= 1 and len(pairs) < n_pairs:
            t_curr = turns[i]
            t_prev = turns[i - 1]
            if t_curr.get("role") == "assistant" and t_prev.get("role") == "user":
                pairs.insert(0, {
                    "user": t_prev["content"],
                    "assistant": t_curr["content"],
                })
                i -= 2
            else:
                i -= 1
        return pairs

    def search_older_turns(
        self,
        session_id: str,
        query_embedding: list[float],
    ) -> list[dict]:
        """Return pair-hydrated older turns from the session that are
        vector-similar to query_embedding.

        Excludes turns already in RECENT CONVERSATION.
        """
        recent_pairs = self.config["RAG_HISTORY_RECENT_PAIRS"]
        exclude_last_n = recent_pairs * 2
        top_k = self.config["RAG_HISTORY_TOP_K"]
        return self.session_repo.vector_search_turns(
            session_id=session_id,
            query_embedding=query_embedding,
            top_k=top_k,
            exclude_last_n=exclude_last_n,
        )

    def write_user_turn(self, session_id: str, content: str) -> str:
        """Embed and persist a user turn. Returns turn_id."""
        return self._write_turn(session_id, "user", content)

    def write_assistant_turn(self, session_id: str, content: str) -> str:
        """Embed and persist an assistant turn. Returns turn_id."""
        return self._write_turn(session_id, "assistant", content)

    def _write_turn(self, session_id: str, role: str, content: str) -> str:
        turn_id = str(uuid.uuid4())
        embedding: list[float] | None = None
        pending = True
        embedded_at: str | None = None
        try:
            embedding = self.embedding_service.embed_texts([content])[0]
            pending = False
            embedded_at = _now_iso()
        except Exception:
            # Soft-skip: turn stored without embedding; vector history retrieval
            # in Step 3.3 will ignore it via the embedding_pending flag.
            pass

        turn = {
            "turn_id": turn_id,
            "role": role,
            "content": content,
            "embedding": embedding,
            "embedded_at": embedded_at,
            "embedding_pending": pending,
        }
        self.session_repo.append_turn(session_id, turn)
        return turn_id
