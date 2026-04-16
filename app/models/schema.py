from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db


def new_uuid() -> str:
    return str(uuid.uuid4())


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(default=_utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=_utc_now,
        onupdate=_utc_now,
        nullable=False,
    )


class Document(db.Model, TimestampMixin):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(primary_key=True, default=new_uuid)
    canonical_url: Mapped[str] = mapped_column(unique=True, nullable=False)
    title: Mapped[str] = mapped_column(nullable=False)
    slug: Mapped[Optional[str]]
    author: Mapped[Optional[str]]
    language: Mapped[str] = mapped_column(default="en", nullable=False)
    source_type: Mapped[str] = mapped_column(default="blog", nullable=False)
    published_at: Mapped[Optional[datetime]]
    last_seen_at: Mapped[Optional[datetime]]
    active_version_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey(
            "document_versions.id",
            use_alter=True,
            name="fk_documents_active_version_id",
        ),
        nullable=True,
    )

    versions: Mapped[list["DocumentVersion"]] = relationship(
        back_populates="document",
        foreign_keys="DocumentVersion.document_id",
        cascade="all, delete-orphan",
    )


class DocumentVersion(db.Model, TimestampMixin):
    __tablename__ = "document_versions"

    id: Mapped[str] = mapped_column(primary_key=True, default=new_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), nullable=False)
    content_hash: Mapped[str] = mapped_column(nullable=False, index=True)
    raw_html: Mapped[Optional[str]] = mapped_column(Text)
    cleaned_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    document: Mapped["Document"] = relationship(
        back_populates="versions",
        foreign_keys=[document_id],
    )
    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document_version",
        cascade="all, delete-orphan",
    )


class Chunk(db.Model, TimestampMixin):
    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(primary_key=True, default=new_uuid)
    document_version_id: Mapped[str] = mapped_column(
        ForeignKey("document_versions.id"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(nullable=False)
    heading_path: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    token_count: Mapped[int] = mapped_column(nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    prev_chunk_id: Mapped[Optional[str]]
    next_chunk_id: Mapped[Optional[str]]
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    embedding_model: Mapped[Optional[str]]
    embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(3072))

    document_version: Mapped["DocumentVersion"] = relationship(back_populates="chunks")

    __table_args__ = (
        Index("ix_chunks_document_version_chunk_index", "document_version_id", "chunk_index"),
    )


class IngestionJob(db.Model, TimestampMixin):
    __tablename__ = "ingestion_jobs"

    id: Mapped[str] = mapped_column(primary_key=True, default=new_uuid)
    job_type: Mapped[str] = mapped_column(nullable=False)
    source_url: Mapped[Optional[str]]
    status: Mapped[str] = mapped_column(default="queued", nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class QueryLog(db.Model, TimestampMixin):
    __tablename__ = "query_logs"

    id: Mapped[str] = mapped_column(primary_key=True, default=new_uuid)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_query: Mapped[str] = mapped_column(Text, nullable=False)
    filters_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    retrieved_chunk_ids: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    retrieval_debug_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    answer_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
