#!/usr/bin/env python3
"""
Dry-run concept extraction for a single article. Does NOT write to the database.

Usage:
    python scripts/dry_run_concepts.py <canonical_url>

Example:
    python scripts/dry_run_concepts.py https://cognitiontoday.com/what-is-cognition-executive-functions-and-cognitive-processes/
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app
from app.models.schema import Document, DocumentVersion
from app.services.concept_extraction_service import (
    ConceptExtractionService,
    SYSTEM_PROMPT,
    _user_message,
)


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    url = sys.argv[1]
    app = create_app()

    with app.app_context():
        doc = Document.query.filter_by(canonical_url=url).first()
        if not doc:
            # Try with/without trailing slash
            alt = url.rstrip("/") if url.endswith("/") else url + "/"
            doc = Document.query.filter_by(canonical_url=alt).first()
        if not doc:
            print(f"No document found for URL: {url}", file=sys.stderr)
            sys.exit(1)

        version = DocumentVersion.query.filter_by(
            document_id=doc.id, is_active=True
        ).first()
        if not version:
            print(f"No active version for document: {url}", file=sys.stderr)
            sys.exit(1)

        print("=" * 72)
        print(f"Document : {doc.title}")
        print(f"URL      : {doc.canonical_url}")
        print(f"Version  : {version.id}")
        print(f"Markdown : {len(version.cleaned_markdown)} chars")
        print("=" * 72)
        print()

        service = ConceptExtractionService(app.config)

        if not service.api_key:
            print("ERROR: OPENAI_API_KEY not set — cannot call extraction.", file=sys.stderr)
            sys.exit(1)

        print(f"Model    : {service.model}")
        print()
        print("--- SYSTEM PROMPT (exact) ---")
        print(SYSTEM_PROMPT)
        print()
        print("--- USER MESSAGE (first 400 chars) ---")
        user_msg = _user_message(doc.title, version.cleaned_markdown)
        print(user_msg[:400] + ("..." if len(user_msg) > 400 else ""))
        print()
        print("Calling OpenAI…")
        print()

        concepts = service.extract(title=doc.title, markdown=version.cleaned_markdown)

        print(f"Extracted {len(concepts)} concept(s):")
        print()

        for c in concepts:
            print(f"[{c.extraction_order + 1:2d}] {c.term}  [{c.kind}]")
            print(f"      Definition   : {c.definition}")
            if c.context_hint:
                print(f"      Context hint : {c.context_hint}")
            print()

        print("--- RAW JSON ---")
        print(json.dumps(
            [
                {
                    "term": c.term,
                    "definition": c.definition,
                    "context_hint": c.context_hint,
                    "kind": c.kind,
                    "extraction_order": c.extraction_order,
                    "metadata": c.metadata,
                }
                for c in concepts
            ],
            indent=2,
        ))


if __name__ == "__main__":
    main()
