#!/usr/bin/env python3
"""
Re-embed all concepts on active document versions using "{term}: {definition}"
instead of "{definition}" alone, and backfill the `embedding_input` column
(added in Step 6b.2a).

Idempotent: a concept whose embedding_input already equals
f"{term}: {definition}" is skipped (no re-embed, no API call).

Usage:
    python scripts/reembed_concepts.py
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select

from app import create_app
from app.extensions import db
from app.models.schema import Concept, DocumentVersion
from app.services.embedding_service import EmbeddingService

BATCH_SIZE = 50
TOKENS_PER_CONCEPT_ESTIMATE = 100
COST_PER_MILLION_TOKENS = 0.02  # text-embedding-3-large


def main() -> None:
    app = create_app()

    with app.app_context():
        embedding_service = EmbeddingService(app.config)
        if not embedding_service.api_key:
            print("ERROR: OPENAI_API_KEY not set — cannot call embeddings.", file=sys.stderr)
            sys.exit(1)

        stmt = (
            select(Concept)
            .join(DocumentVersion, Concept.document_version_id == DocumentVersion.id)
            .where(DocumentVersion.is_active.is_(True))
            .order_by(Concept.id)
        )
        concepts = list(db.session.scalars(stmt))
        total = len(concepts)

        estimated_cost = total * TOKENS_PER_CONCEPT_ESTIMATE / 1_000_000 * COST_PER_MILLION_TOKENS
        print(f"Found {total} concepts on active document versions.")
        print(
            f"Estimated cost: {total} concepts x ~{TOKENS_PER_CONCEPT_ESTIMATE} tokens "
            f"x ${COST_PER_MILLION_TOKENS}/1M tokens (text-embedding-3-large) "
            f"= ${estimated_cost:.4f}"
        )
        input("Press Enter to proceed, or Ctrl-C to abort... ")

        start = time.monotonic()
        reembedded = 0
        skipped = 0

        for batch_start in range(0, total, BATCH_SIZE):
            batch = concepts[batch_start:batch_start + BATCH_SIZE]

            to_embed: list[Concept] = []
            inputs: list[str] = []
            for concept in batch:
                expected_input = f"{concept.term}: {concept.definition}"
                if concept.embedding_input == expected_input:
                    skipped += 1
                    continue
                to_embed.append(concept)
                inputs.append(expected_input)

            if to_embed:
                embeddings = embedding_service.embed_texts(inputs)
                for concept, embedding_input, embedding in zip(to_embed, inputs, embeddings):
                    concept.embedding = embedding
                    concept.embedding_input = embedding_input
                db.session.commit()

            reembedded += len(to_embed)
            print(f"Re-embedded {reembedded}/{total} concepts ({skipped} skipped, idempotent)")

        elapsed = time.monotonic() - start
        actual_cost = reembedded * TOKENS_PER_CONCEPT_ESTIMATE / 1_000_000 * COST_PER_MILLION_TOKENS
        print()
        print(
            f"Done. Re-embedded {reembedded}/{total} concepts "
            f"({skipped} skipped) in {elapsed:.1f}s."
        )
        print(f"Estimated cost incurred: ${actual_cost:.4f}")


if __name__ == "__main__":
    main()
