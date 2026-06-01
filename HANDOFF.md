# Phase 2 Handoff — Concepts DB

## Where we are

### Phase 2 step status

| Step | Description | Status |
|------|-------------|--------|
| 1 | Schema + migration (`concepts` table) | Done — commit `1367a6a` |
| 2 | `ConceptExtractionService` + dry-run script | Built, **not yet committed** |
| 3 | `ConceptRepository` | Not started |
| 4 | Ingest integration | Not started |
| 5 | Admin backfill endpoint (`POST /api/admin/concepts/backfill`) | Not started |
| 6 | Retrieval integration (concept-derived candidates in RRF merge) | Not started |

### Uncommitted files
- `app/services/concept_extraction_service.py`
- `scripts/dry_run_concepts.py`

---

## Next action when resuming

**Do not skip straight to step 3.** The dry-run has NOT been executed yet.

1. Run the dry-run against the three review articles below and inspect the extracted concepts.
2. Review prompt quality with the user before proceeding.
3. If extraction looks good, commit step 2 and move to step 3.

### Dry-run command
```bash
python scripts/dry_run_concepts.py <canonical_url>
```

### Three articles slated for dry-run review
- `https://cognitiontoday.com/why-you-are-consistently-unhappy/`
- `https://cognitiontoday.com/your-brain-on-productivity-thinking-doing-modes/`
- `https://cognitiontoday.com/mnemonic-techniques-to-slay-at-memorizing-tutorial/`

---

## Full Phase 2 plan

1. **Schema + migration** — `concepts` table with term, definition, context_hint, embedding (3072-dim), extraction_order, metadata_json (JSONB), FK to document_versions CASCADE.
2. **ConceptExtractionService** — OpenAI structured outputs, model `gpt-4.1`, 8–12 concepts per article (max 15), 5-kind taxonomy (definition / framework / technique / claim / distinction).
3. **ConceptRepository** — `vector_search`, `bulk_replace_for_version`, `get_by_document`; filters to active versions only.
4. **Ingest integration** — concept extraction runs after chunks are built, before version is committed; failures are swallowed with a warning (chunk ingestion is more important).
5. **Admin backfill endpoint** — `POST /api/admin/concepts/backfill` enqueues extraction for all active versions with zero concepts.
6. **Retrieval integration** — concept vector search runs in parallel with chunk searches; high-scoring concept matches derive their source article's chunks into the candidate pool with a concept-derived boost; RRF merge becomes 3-way (vector + lexical + concept-derived); `retrieval_source` field tracks provenance.

---

## Key baselines and experiments

- **Litmus baseline (pre-Phase 2):** mean recall@5 = 0.331, recall@10 = 0.460 — git tag `baseline-post-cleanup`
- **MAX_CHUNKS_PER_DOCUMENT = 1** is a litmus-driven experiment (was 2); revert if Phase 2 doesn't justify the loss.
- After retrieval integration (step 6), re-run the litmus and compare against `baseline-post-cleanup`.
