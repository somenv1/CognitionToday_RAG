import uuid

from app import extensions
from app.models.schema import Chunk, DocumentVersion
from app.services.chunk_service import ChunkService
from app.services.embedding_service import EmbeddingService
from app.extensions import db


def _reindex_document(document_id: str) -> str:
    from app import create_app

    app = create_app()
    with app.app_context():
        version = (
            DocumentVersion.query.join(DocumentVersion.document)
            .filter_by(document_id=document_id, is_active=True)
            .order_by(DocumentVersion.created_at.desc())
            .first()
        )
        if version is None:
            raise ValueError(f"Active version for document {document_id} was not found")

        chunk_service = ChunkService()
        embedding_service = EmbeddingService(app.config)
        chunk_drafts = chunk_service.chunk_markdown(version.cleaned_markdown)
        try:
            embeddings = embedding_service.embed_texts(
                [chunk.embedding_text for chunk in chunk_drafts]
            )
        except RuntimeError:
            embeddings = [None for _ in chunk_drafts]
        chunk_ids = [str(uuid.uuid4()) for _ in chunk_drafts]

        Chunk.query.filter_by(document_version_id=version.id).delete()
        if len(chunk_drafts) != len(embeddings):
            raise ValueError("Chunk and embedding counts do not match during reindex")

        for index, (draft, embedding) in enumerate(zip(chunk_drafts, embeddings)):
            db.session.add(
                Chunk(
                    id=chunk_ids[index],
                    document_version_id=version.id,
                    chunk_index=draft.chunk_index,
                    heading_path=draft.heading_path,
                    token_count=draft.token_count,
                    text=draft.text,
                    prev_chunk_id=chunk_ids[index - 1] if index > 0 else None,
                    next_chunk_id=chunk_ids[index + 1] if index + 1 < len(chunk_ids) else None,
                    metadata_json={
                        "heading_path": draft.heading_path,
                        "word_count": draft.word_count,
                        "paragraph_count": draft.paragraph_count,
                        "embedding_text": draft.embedding_text,
                    },
                    embedding_model=(
                        app.config["OPENAI_EMBEDDING_MODEL"]
                        if embedding is not None
                        else None
                    ),
                    embedding=embedding,
                )
            )

        db.session.commit()
        return version.id


def enqueue_document_reindex(config, document_id: str):
    if extensions.rq_queue is None:
        raise RuntimeError("RQ queue is not initialized")

    return extensions.rq_queue.enqueue(_reindex_document, document_id)
