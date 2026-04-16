from flask import Blueprint, current_app, request

from app import extensions
from app.workers.ingest_jobs import enqueue_document_ingestion, enqueue_sitemap_sync
from app.workers.reindex_jobs import enqueue_document_reindex


admin_bp = Blueprint("admin", __name__)


@admin_bp.post("/ingest")
def ingest():
    payload = request.get_json(silent=True) or {}
    url = payload.get("url")

    if url:
        job = enqueue_document_ingestion(current_app.config, url=url)
        return {"status": "queued", "job_id": job.id, "url": url}, 202

    job = enqueue_sitemap_sync(current_app.config)
    return {"status": "queued", "job_id": job.id}, 202


@admin_bp.post("/reindex/<document_id>")
def reindex(document_id: str):
    job = enqueue_document_reindex(current_app.config, document_id=document_id)
    return {
        "status": "queued",
        "job_id": job.id,
        "document_id": document_id,
    }, 202


@admin_bp.get("/queue")
def queue_status():
    if extensions.rq_queue is None:
        return {"status": "unavailable"}, 503

    return {
        "queue": extensions.rq_queue.name,
        "length": len(extensions.rq_queue),
    }, 200
