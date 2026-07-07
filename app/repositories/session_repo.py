from __future__ import annotations

import json
import math
import uuid
from datetime import datetime, timezone


class SessionNotFoundError(Exception):
    pass


MAX_TURNS = 40


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SessionRepository:
    def __init__(self, redis_client):
        self.redis = redis_client
        self.ttl_seconds = 3600  # 60 minutes

    # ------------------------------------------------------------------
    # Key helpers
    # ------------------------------------------------------------------

    def _data_key(self, session_id: str) -> str:
        return f"session:{session_id}"

    def _meta_key(self, session_id: str) -> str:
        return f"session:{session_id}:meta"

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get_session(self, session_id: str) -> dict | None:
        data_raw = self.redis.get(self._data_key(session_id))
        meta_raw = self.redis.get(self._meta_key(session_id))
        if data_raw is None or meta_raw is None:
            return None
        return json.loads(data_raw)

    def create_session(self) -> tuple[str, dict]:
        session_id = str(uuid.uuid4())
        now = _now_iso()

        blob: dict = {"session_id": session_id, "turns": []}
        meta: dict = {"created_at": now, "last_active_at": now, "turn_count": 0}

        pipe = self.redis.pipeline()
        pipe.setex(self._data_key(session_id), self.ttl_seconds, json.dumps(blob))
        pipe.setex(self._meta_key(session_id), self.ttl_seconds, json.dumps(meta))
        pipe.execute()

        return session_id, blob

    def append_turn(self, session_id: str, turn: dict) -> dict:
        data_raw = self.redis.get(self._data_key(session_id))
        if data_raw is None:
            raise SessionNotFoundError(f"Session {session_id!r} not found or expired")

        blob = json.loads(data_raw)
        blob["turns"].append(turn)

        if len(blob["turns"]) > MAX_TURNS:
            blob["turns"] = blob["turns"][-MAX_TURNS:]

        now = _now_iso()
        meta = {"created_at": self._get_meta_field(session_id, "created_at", now),
                "last_active_at": now,
                "turn_count": len(blob["turns"])}

        pipe = self.redis.pipeline()
        pipe.setex(self._data_key(session_id), self.ttl_seconds, json.dumps(blob))
        pipe.setex(self._meta_key(session_id), self.ttl_seconds, json.dumps(meta))
        pipe.execute()

        return blob

    def update_turn_embedding(
        self, session_id: str, turn_id: str, embedding: list[float]
    ) -> dict | None:
        data_raw = self.redis.get(self._data_key(session_id))
        if data_raw is None:
            return None

        blob = json.loads(data_raw)
        target = next((t for t in blob["turns"] if t.get("turn_id") == turn_id), None)
        if target is None:
            return None

        target["embedding"] = embedding
        target["embedded_at"] = _now_iso()
        target["embedding_pending"] = False

        # Intentionally no TTL refresh — stale write-back should not extend session life
        self.redis.set(self._data_key(session_id), json.dumps(blob), keepttl=True)

        return blob

    def delete_session(self, session_id: str) -> bool:
        deleted = self.redis.delete(self._data_key(session_id), self._meta_key(session_id))
        return deleted > 0

    def get_pending_embeddings(self, session_id: str) -> list[dict]:
        data_raw = self.redis.get(self._data_key(session_id))
        if data_raw is None:
            return []
        blob = json.loads(data_raw)
        return [t for t in blob["turns"] if t.get("embedding_pending") is True]

    def refresh_ttl(self, session_id: str) -> None:
        self.redis.expire(self._data_key(session_id), self.ttl_seconds)
        self.redis.expire(self._meta_key(session_id), self.ttl_seconds)

    def vector_search_turns(
        self,
        session_id: str,
        query_embedding: list[float],
        top_k: int,
        exclude_last_n: int,
    ) -> list[dict]:
        """Search turn embeddings in this session by cosine similarity to query_embedding.

        Returns up to top_k pair-hydrated results in descending similarity order.
        Each result is {"user": str, "assistant": str, "similarity": float}.

        Excludes the last exclude_last_n turns (already in RECENT CONVERSATION)
        and any turns where embedding_pending is True (embedding not yet computed).
        """
        session = self.get_session(session_id)
        if session is None:
            return []

        turns = session.get("turns", [])
        eligible_end = max(0, len(turns) - exclude_last_n)
        searchable = [
            (i, turn) for i, turn in enumerate(turns[:eligible_end])
            if turn.get("embedding") is not None
            and turn.get("embedding_pending") is False
        ]

        if not searchable:
            return []

        scored: list[tuple[int, dict, float]] = []
        for idx, turn in searchable:
            sim = _cosine_similarity(query_embedding, turn["embedding"])
            scored.append((idx, turn, sim))

        scored.sort(key=lambda x: x[2], reverse=True)

        # Pair-hydrate each result, de-duping matches that belong to the same
        # pair (keep only the higher-scoring one, since scored is sorted desc).
        seen_pairs: set[tuple[int, int]] = set()
        results: list[dict] = []
        for idx, turn, sim in scored:
            pair_indices = _get_pair_indices(turns, idx)
            if pair_indices is None:
                continue
            if pair_indices in seen_pairs:
                continue
            seen_pairs.add(pair_indices)
            user_idx, assistant_idx = pair_indices
            results.append({
                "user": turns[user_idx]["content"],
                "assistant": turns[assistant_idx]["content"],
                "similarity": sim,
            })
            if len(results) >= top_k:
                break

        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_meta_field(self, session_id: str, field: str, default: str) -> str:
        meta_raw = self.redis.get(self._meta_key(session_id))
        if meta_raw is None:
            return default
        return json.loads(meta_raw).get(field, default)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _get_pair_indices(turns: list[dict], idx: int) -> tuple[int, int] | None:
    """Given a turn index, return (user_idx, assistant_idx) for its pair,
    or None if no valid pair can be formed."""
    turn = turns[idx]
    role = turn.get("role")
    if role == "user":
        if idx + 1 < len(turns) and turns[idx + 1].get("role") == "assistant":
            return (idx, idx + 1)
        return None
    elif role == "assistant":
        if idx - 1 >= 0 and turns[idx - 1].get("role") == "user":
            return (idx - 1, idx)
        return None
    return None
