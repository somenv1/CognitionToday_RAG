from __future__ import annotations

import logging

from rq import Retry


logger = logging.getLogger(__name__)


def embed_turn(session_id: str, turn_id: str) -> dict:
    """Compute embedding for a turn and back-fill it in Redis.

    Idempotent: if the turn no longer exists (session expired, evicted),
    returns without error. If the turn already has an embedding, this
    overwrites it — but the enqueue path only fires with pending=True
    turns, so overwrites shouldn't happen in practice.

    Runs inside the Flask app context so config and extensions are available.
    """
    from app import create_app, extensions
    from app.repositories.session_repo import SessionRepository
    from app.services.embedding_service import EmbeddingService

    app = create_app()
    with app.app_context():
        repo = SessionRepository(extensions.session_repo.redis)
        session = repo.get_session(session_id)
        if session is None:
            logger.info(
                "embed_turn: session %s no longer exists, skipping", session_id
            )
            return {"status": "session_gone"}

        # Find the turn.
        target = None
        for t in session.get("turns", []):
            if t.get("turn_id") == turn_id:
                target = t
                break

        if target is None:
            logger.info(
                "embed_turn: turn %s not found in session %s (evicted), skipping",
                turn_id, session_id,
            )
            return {"status": "turn_evicted"}

        content = target.get("content") or ""
        if not content.strip():
            logger.warning(
                "embed_turn: turn %s has empty content, skipping", turn_id
            )
            return {"status": "empty_content"}

        # Embed. Will raise on error, RQ retry catches it.
        embedder = EmbeddingService(app.config)
        embedding = embedder.embed_texts([content])[0]

        # Back-fill. This uses SET ... KEEPTTL so it doesn't extend session lifetime.
        repo.update_turn_embedding(
            session_id=session_id,
            turn_id=turn_id,
            embedding=embedding,
        )
        return {"status": "ok", "turn_id": turn_id}


def enqueue_embed_turn(session_id: str, turn_id: str) -> None:
    """Fire-and-forget enqueue of embed_turn.

    If enqueue fails (Redis unreachable, queue misconfigured), log a warning
    and return. The turn is already durably written; it can be re-embedded
    on a future chat message.
    """
    from app import extensions

    if extensions.rq_queue is None:
        logger.warning(
            "enqueue_embed_turn: rq_queue not initialized, turn %s stays pending",
            turn_id,
        )
        return

    try:
        extensions.rq_queue.enqueue(
            embed_turn,
            session_id,
            turn_id,
            retry=Retry(max=3, interval=[10, 30, 60]),
            job_timeout=60,  # seconds
        )
    except Exception as exc:
        logger.warning(
            "enqueue_embed_turn: enqueue failed for turn %s: %s (turn stays pending)",
            turn_id, exc,
        )
