from __future__ import annotations

from app.extensions import db
from app.models.schema import Document, DocumentVersion


class DocumentRepository:
    def get_by_url(self, canonical_url: str) -> Document | None:
        return Document.query.filter_by(canonical_url=canonical_url).one_or_none()

    def get_by_id(self, document_id: str) -> Document | None:
        return Document.query.get(document_id)

    def get_active_version(self, document_id: str) -> DocumentVersion | None:
        return (
            DocumentVersion.query.filter_by(document_id=document_id, is_active=True)
            .order_by(DocumentVersion.created_at.desc())
            .first()
        )

    def save(self, document: Document) -> Document:
        db.session.add(document)
        db.session.commit()
        return document

    def save_version(self, document_version: DocumentVersion) -> DocumentVersion:
        db.session.add(document_version)
        db.session.commit()
        return document_version
