# Phase 2 Handoff — Concepts DB

## Where we are

### Phase 2 step status

| Step | Description | Status |
|------|-------------|--------|
| 1 | Schema + migration (`concepts` table) | Done — commit `1367a6a` |
| 2 | `ConceptExtractionService` + dry-run script | Done — validated via dry-run |
| 3 | `ConceptRepository` | Done — commit `9d76ac9` |
| 4 | Ingest integration | Done — validated 2026-06-08 (12/12 concepts + embeddings) |
| 5 | Admin backfill endpoint (`POST /api/admin/concepts/backfill`) | Done — validated 2026-06-08 (single-doc + bulk backfill passed); corpus cleanup commit `0717414` |
| 6 | Retrieval integration (concept-derived candidates in RRF merge) | **Next action** |

---

## Step 2 validation results

Dry-run executed across all three articles. All runs returned 12 concepts.

| Article | Concepts | Notes |
|---------|----------|-------|
| `https://cognitiontoday.com/why-you-are-consistently-unhappy/` | 12 | Mixed kinds; named concepts verbatim ("Heaven's reward fallacy", "optimism bias") |
| `https://cognitiontoday.com/your-brain-on-productivity-thinking-doing-modes/` | 12 | All 6 brain networks named verbatim with acronyms; author's "city/industries" metaphor preserved |
| `https://cognitiontoday.com/mnemonic-techniques-to-slay-at-memorizing-tutorial/` | 12 | All 10 named techniques captured plus umbrella definition and framework concept |

**Known limitation — `kind` field definition-bias:** Article 3 returned 10 of 12 as "definition" (most should arguably be "technique"). Acceptable because no retrieval logic reads `kind`; the `definition` text that gets embedded is high quality. Documented in `concept_extraction_service.py`. Revisit if Phase 3+ adds kind-based filtering.

## Step 5 validation results

Two integration tests passed: single-doc backfill returned 13 concepts; bulk backfill enqueued 3 jobs that all completed.

**Corpus pollution found during Test 2** — non-article URLs (contact-us, membership pages, login, disclaimer, donate, an interactive quiz) had been ingested and were producing junk concepts (e.g. `contact-us/` yielded 4 "concepts" that were really form bullets). This prompted a corpus audit of all documents with markdown <2000 chars, which found 16 short non-article URLs.

Cleanup (commit `0717414`):
- Extended `_BLOCKED_PATH_SEGMENTS` (`ingest_service.py`) and `NON_ARTICLE_PATTERNS` (`ingest_jobs.py`) with 8 new patterns: `/membership-`, `/login/`, `/contact-us/`, `/contact/`, `/subscribe-`, `/disclaimer`, `/donate`, `/can-you-spot-these-cognitive-biases/`
- Soft-deleted the 14 affected documents (`document_versions.is_active = false`, `documents.active_version_id = NULL`); verified 0 still active, 14 inactive
- `/introduction/` intentionally kept — extracted 8 valid concepts, treated as a real article

## Next action when resuming

**Step 6: Retrieval integration** — concept vector search runs in parallel with chunk searches; high-scoring concept matches derive their source article's chunks into the candidate pool with a concept-derived boost; RRF merge becomes 3-way (vector + lexical + concept-derived); `retrieval_source` field tracks provenance.

---

## Full Phase 2 plan

1. **Schema + migration** — `concepts` table with term, definition, context_hint, embedding (3072-dim), extraction_order, metadata_json (JSONB), FK to document_versions CASCADE.
2. **ConceptExtractionService** — OpenAI structured outputs, model `gpt-4.1`, 8–12 concepts per article (max 15), 5-kind taxonomy (definition / framework / technique / claim / distinction). Committed at `6f9af2f`, validated via dry-run.
3. **ConceptRepository** — `vector_search`, `bulk_replace_for_version`, `get_by_document`; filters to active versions only.
4. **Ingest integration** — concept extraction runs after chunks are built, before version is committed; failures are swallowed with a warning (chunk ingestion is more important).
5. **Admin backfill endpoint** — `POST /api/admin/concepts/backfill` enqueues extraction for all active versions with zero concepts.
6. **Retrieval integration** — concept vector search runs in parallel with chunk searches; high-scoring concept matches derive their source article's chunks into the candidate pool with a concept-derived boost; RRF merge becomes 3-way (vector + lexical + concept-derived); `retrieval_source` field tracks provenance.

---

## Key baselines and experiments

- **Litmus baseline (pre-Phase 2):** mean recall@5 = 0.331, recall@10 = 0.460 — git tag `baseline-post-cleanup`
- **MAX_CHUNKS_PER_DOCUMENT = 1** is a litmus-driven experiment (was 2); revert if Phase 2 doesn't justify the loss.
- After retrieval integration (step 6), re-run the litmus and compare against `baseline-post-cleanup`.
