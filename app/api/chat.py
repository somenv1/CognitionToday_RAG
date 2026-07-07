from flask import Blueprint, current_app, request

from app import extensions
from app.services.answer_service import AnswerService, InsufficientContextError
from app.services.embedding_service import EmbeddingService
from app.services.query_rewrite_service import QueryRewriteService
from app.services.retrieval_service import RetrievalService
from app.services.session_service import SessionService


chat_bp = Blueprint("chat", __name__)


@chat_bp.post("/chat")
def chat():
    payload = request.get_json(silent=True) or {}
    query = (payload.get("query") or "").strip()
    filters = payload.get("filters") or {}
    requested_session_id = payload.get("session_id")

    if not query:
        return {"error": "query is required"}, 400

    retrieval_service = RetrievalService(current_app.config)
    answer_service = AnswerService(current_app.config)
    session_service = SessionService(current_app.config, extensions.session_repo)

    session_id, session = session_service.get_or_create(requested_session_id)
    recent_pairs = session_service.extract_recent_pairs(session)

    # Rewrite the query using session context so retrieval targets what
    # the user actually means, not their literal words. Returns the original
    # query unchanged when there's no session context to work from.
    query_rewrite_service = QueryRewriteService(current_app.config)
    retrieval_query = query_rewrite_service.rewrite(query=query, recent_pairs=recent_pairs)

    # Compute query embedding once, use for session history search.
    # Note: RetrievalService re-computes this internally today for chunk/concept
    # retrieval. That's a duplicate cost we'll optimize in a later step if needed.
    #
    # Must run before write_user_turn: search_older_turns excludes turns already
    # covered by RECENT CONVERSATION (recent_pairs, computed above), and that
    # exclusion window is turn-count-based. Appending the new user turn first
    # would shift the count by one and let the most recent pair leak into
    # "older" results.
    embedding_service = EmbeddingService(current_app.config)
    try:
        query_embedding = embedding_service.embed_texts([retrieval_query])[0]
    except Exception:
        query_embedding = None

    older_turns = []
    if query_embedding is not None:
        older_turns = session_service.search_older_turns(
            session_id=session_id,
            query_embedding=query_embedding,
        )

    # Write user turn (with the ORIGINAL query — that's what the user said).
    session_service.write_user_turn(session_id, query)

    # Use the REWRITTEN query for retrieval so chunks/concepts match intent.
    retrieval_result = retrieval_service.retrieve(query=retrieval_query, filters=filters)

    debug_payload = retrieval_result.to_dict() | {
        "retrieval_query": retrieval_query,
        "older_turns": [
            {"user": t["user"][:100], "assistant": t["assistant"][:100], "similarity": t["similarity"]}
            for t in older_turns
        ],
    }

    try:
        answer = answer_service.answer(
            query=query,
            retrieval_result=retrieval_result,
            recent_pairs=recent_pairs,
            older_turns=older_turns,
        )
    except InsufficientContextError as exc:
        return {
            "answer": str(exc),
            "citations": [],
            "confidence": "low",
            "grounded": False,
            "session_id": session_id,
            "debug": debug_payload,
        }, 200

    session_service.write_assistant_turn(session_id, answer.answer)

    return {
        "answer": answer.answer,
        "citations": answer.citations,
        "confidence": answer.confidence,
        "grounded": answer.grounded,
        "session_id": session_id,
        "debug": debug_payload,
    }, 200
