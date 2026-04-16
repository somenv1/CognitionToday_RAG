from flask import Blueprint, current_app, request

from app.services.answer_service import AnswerService, InsufficientContextError
from app.services.retrieval_service import RetrievalService


chat_bp = Blueprint("chat", __name__)


@chat_bp.post("/chat")
def chat():
    payload = request.get_json(silent=True) or {}
    query = (payload.get("query") or "").strip()
    filters = payload.get("filters") or {}

    if not query:
        return {"error": "query is required"}, 400

    retrieval_service = RetrievalService(current_app.config)
    answer_service = AnswerService(current_app.config)

    retrieval_result = retrieval_service.retrieve(query=query, filters=filters)

    try:
        answer = answer_service.answer(
            query=query,
            retrieval_result=retrieval_result,
        )
    except InsufficientContextError as exc:
        return {
            "answer": str(exc),
            "citations": [],
            "confidence": "low",
            "grounded": False,
            "debug": retrieval_result.to_dict(),
        }, 200

    return {
        "answer": answer.answer,
        "citations": answer.citations,
        "confidence": answer.confidence,
        "grounded": answer.grounded,
        "debug": retrieval_result.to_dict(),
    }, 200
