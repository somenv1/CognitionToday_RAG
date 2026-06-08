from datetime import datetime, timezone
import logging
import uuid

import requests

from app.models.schema import Chunk, Concept, Document, DocumentVersion
from app.repositories.chunk_repo import ChunkRepository
from app.repositories.concept_repo import ConceptRepository
from app.repositories.document_repo import DocumentRepository
from app.services.chunk_service import ChunkService
from app.services.clean_service import CleanService
from app.services.concept_extraction_service import ConceptExtractionService
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)

# URL path segments that identify non-article content we must never index.
# Keep in sync with NON_ARTICLE_PATTERNS in app/workers/ingest_jobs.py.
_BLOCKED_PATH_SEGMENTS = ("/web-stories/", "/web-story/")


REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*; q=0.01",
}


class IngestService:
    def __init__(self, config) -> None:
        self.config = config
        self.clean_service = CleanService()
        self.chunk_service = ChunkService()
        self.embedding_service = EmbeddingService(config)
        self.concept_extraction_service = ConceptExtractionService(config)
        self.document_repo = DocumentRepository()
        self.chunk_repo = ChunkRepository()
        self.concept_repo = ConceptRepository()

    def ingest_url(self, url: str) -> Document:
        for segment in _BLOCKED_PATH_SEGMENTS:
            if segment in url:
                logger.info("Refusing to ingest non-article URL (blocked segment %r): %s", segment, url)
                raise ValueError(f"URL contains blocked path segment {segment!r}: {url}")

        response = requests.get(url, headers=REQUEST_HEADERS, timeout=20)
        response.raise_for_status()

        cleaned = self.clean_service.clean(url=url, html=response.text)
        document = self.document_repo.get_by_url(cleaned.canonical_url)

        if document is None:
            document = Document(
                canonical_url=cleaned.canonical_url,
                title=cleaned.title,
                last_seen_at=datetime.now(timezone.utc),
            )
            self.document_repo.save(document)
        else:
            document.title = cleaned.title
            document.last_seen_at = datetime.now(timezone.utc)

        active_version = self.document_repo.get_active_version(document.id)
        if active_version and active_version.content_hash == cleaned.content_hash:
            self.document_repo.save(document)
            return document

        if active_version:
            active_version.is_active = False

        version = DocumentVersion(
            document_id=document.id,
            content_hash=cleaned.content_hash,
            raw_html=cleaned.raw_html,
            cleaned_markdown=cleaned.cleaned_markdown,
            metadata_json=cleaned.metadata,
            is_active=True,
        )
        self.document_repo.save_version(version)
        document.active_version_id = version.id
        self.document_repo.save(document)

        chunk_drafts = self.chunk_service.chunk_markdown(cleaned.cleaned_markdown)
        try:
            embeddings = self.embedding_service.embed_texts(
                [chunk.embedding_text for chunk in chunk_drafts]
            )
        except RuntimeError:
            embeddings = [None for _ in chunk_drafts]

        chunks: list[Chunk] = []
        chunk_ids = [str(uuid.uuid4()) for _ in chunk_drafts]

        if len(chunk_drafts) != len(embeddings):
            raise ValueError("Chunk and embedding counts do not match during ingestion")

        for index, (draft, embedding) in enumerate(zip(chunk_drafts, embeddings)):
            chunks.append(
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
                        self.config["OPENAI_EMBEDDING_MODEL"]
                        if embedding is not None
                        else None
                    ),
                    embedding=embedding,
                )
            )

        try:
            concept_drafts = self.concept_extraction_service.extract(
                title=cleaned.title, markdown=cleaned.cleaned_markdown
            )
        except Exception as exc:
            logger.warning("Concept extraction failed for %s: %s", cleaned.canonical_url, exc)
            concept_drafts = []

        concept_embeddings: list = []
        if concept_drafts:
            try:
                concept_embeddings = self.embedding_service.embed_texts(
                    [draft.definition for draft in concept_drafts]
                )
            except RuntimeError:
                concept_embeddings = [None for _ in concept_drafts]

        concepts: list[Concept] = []
        for draft, concept_embedding in zip(concept_drafts, concept_embeddings):
            concepts.append(
                Concept(
                    id=str(uuid.uuid4()),
                    document_version_id=version.id,
                    term=draft.term,
                    definition=draft.definition,
                    context_hint=draft.context_hint,
                    embedding=concept_embedding,
                    embedding_model=(
                        self.config["OPENAI_EMBEDDING_MODEL"]
                        if concept_embedding is not None
                        else None
                    ),
                    extraction_order=draft.extraction_order,
                    metadata_json=draft.metadata,
                    created_at=datetime.now(timezone.utc),
                )
            )

        self.chunk_repo.bulk_replace_for_version(version.id, chunks)

        if concepts:
            self.concept_repo.bulk_replace_for_version(version.id, concepts)
            logger.info("Persisted %d concepts for document %s", len(concepts), cleaned.canonical_url)

        return document
