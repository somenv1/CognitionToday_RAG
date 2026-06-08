from flask import Blueprint, current_app, request
from sqlalchemy import exists, select

from app import extensions
from app.extensions import db
from app.models.schema import Concept, DocumentVersion
from app.workers.concept_jobs import enqueue_concept_backfill
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


@admin_bp.post("/concepts/backfill")
def concepts_backfill():
    payload = request.get_json(silent=True) or {}
    document_id = payload.get("document_id")
    limit = int(payload.get("limit", 10))

    if document_id:
        version = DocumentVersion.query.filter_by(
            document_id=document_id, is_active=True
        ).first()
        if not version:
            return {"error": "No active version found for document_id"}, 404
        job = enqueue_concept_backfill(current_app.config, version_id=version.id)
        return {
            "status": "queued",
            "job_id": job.id,
            "version_id": version.id,
            "document_id": document_id,
        }, 202

    stmt = (
        select(DocumentVersion)
        .where(DocumentVersion.is_active.is_(True))
        .where(~exists().where(Concept.document_version_id == DocumentVersion.id))
        .order_by(DocumentVersion.created_at.asc())
        .limit(limit)
    )
    versions = list(db.session.scalars(stmt))
    jobs = [enqueue_concept_backfill(current_app.config, version_id=v.id) for v in versions]
    return {
        "status": "queued",
        "queued": len(jobs),
        "version_ids": [v.id for v in versions],
    }, 202


@admin_bp.get("/queue")
def queue_status():
    if extensions.rq_queue is None:
        return {"status": "unavailable"}, 503

    return {
        "queue": extensions.rq_queue.name,
        "length": len(extensions.rq_queue),
    }, 200
