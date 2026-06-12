from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from app import extensions
from app.models.schema import Concept, DocumentVersion
from app.repositories.concept_repo import ConceptRepository
from app.services.concept_extraction_service import ConceptExtractionService
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


def _backfill_concepts_for_version(version_id: str) -> dict:
    """Re-extract and persist concepts for a single document version.

    Idempotent at the persistence level (bulk_replace_for_version deletes
    existing concepts first). Safe to retry."""
    from app import create_app
    app = create_app()
    with app.app_context():
        from app.extensions import db
        version = db.session.get(DocumentVersion, version_id)
        if not version or not version.is_active:
            app.logger.info(
                "Concept backfill skipped: version %s not found or inactive", version_id
            )
            return {"version_id": version_id, "status": "skipped"}

        title = version.document.title
        config = app.config

        concept_extraction_service = ConceptExtractionService(config)
        embedding_service = EmbeddingService(config)
        concept_repo = ConceptRepository()

        try:
            concept_drafts = concept_extraction_service.extract(
                title=title, markdown=version.cleaned_markdown
            )
        except Exception as exc:
            app.logger.warning(
                "Concept backfill extraction failed for version %s: %s", version_id, exc
            )
            return {"version_id": version_id, "status": "extraction_failed"}

        if not concept_drafts:
            return {"version_id": version_id, "concept_count": 0, "embedded_count": 0}

        # Embedding text: "{term}: {definition}" — same format as ingest_service.py.
        embedding_inputs = [f"{draft.term}: {draft.definition}" for draft in concept_drafts]
        try:
            concept_embeddings = embedding_service.embed_texts(embedding_inputs)
        except RuntimeError:
            concept_embeddings = [None for _ in concept_drafts]

        concepts: list[Concept] = []
        for index, (draft, concept_embedding) in enumerate(zip(concept_drafts, concept_embeddings)):
            concepts.append(
                Concept(
                    id=str(uuid.uuid4()),
                    document_version_id=version_id,
                    term=draft.term,
                    definition=draft.definition,
                    context_hint=draft.context_hint,
                    embedding_input=embedding_inputs[index],
                    embedding=concept_embedding,
                    embedding_model=(
                        config["OPENAI_EMBEDDING_MODEL"]
                        if concept_embedding is not None
                        else None
                    ),
                    extraction_order=draft.extraction_order,
                    metadata_json=draft.metadata,
                    created_at=datetime.now(timezone.utc),
                )
            )

        concept_repo.bulk_replace_for_version(version_id, concepts)

        embedded_count = sum(1 for c in concepts if c.embedding is not None)
        app.logger.info(
            "Concept backfill: persisted %d concepts (%d embedded) for version %s",
            len(concepts), embedded_count, version_id,
        )
        return {
            "version_id": version_id,
            "concept_count": len(concepts),
            "embedded_count": embedded_count,
        }


def enqueue_concept_backfill(config, version_id: str):
    if extensions.rq_queue is None:
        raise RuntimeError("RQ queue is not initialized")
    return extensions.rq_queue.enqueue(_backfill_concepts_for_version, version_id)
