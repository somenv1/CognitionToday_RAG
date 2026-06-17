from flask import Blueprint, current_app, request

from app import extensions
from app.services.answer_service import AnswerService, InsufficientContextError
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

    # Write user turn before retrieval so it's persisted even if retrieval fails.
    session_service.write_user_turn(session_id, query)

    retrieval_result = retrieval_service.retrieve(query=query, filters=filters)

    try:
        answer = answer_service.answer(
            query=query,
            retrieval_result=retrieval_result,
            recent_pairs=recent_pairs,
        )
    except InsufficientContextError as exc:
        return {
            "answer": str(exc),
            "citations": [],
            "confidence": "low",
            "grounded": False,
            "session_id": session_id,
            "debug": retrieval_result.to_dict(),
        }, 200

    session_service.write_assistant_turn(session_id, answer.answer)

    return {
        "answer": answer.answer,
        "citations": answer.citations,
        "confidence": answer.confidence,
        "grounded": answer.grounded,
        "session_id": session_id,
        "debug": retrieval_result.to_dict(),
    }, 200
