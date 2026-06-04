# Phase 2 Handoff — Concepts DB

## Where we are

### Phase 2 step status

| Step | Description | Status |
|------|-------------|--------|
| 1 | Schema + migration (`concepts` table) | Done — commit `1367a6a` |
| 2 | `ConceptExtractionService` + dry-run script | Done — validated via dry-run |
| 3 | `ConceptRepository` | Done — commit `9d76ac9` |
| 4 | Ingest integration | Done — commit `eea7e95` |
| 5 | Admin backfill endpoint (`POST /api/admin/concepts/backfill`) | **Next action** |
| 6 | Retrieval integration (concept-derived candidates in RRF merge) | Not started |

---

## Step 2 validation results

Dry-run executed across all three articles. All runs returned 12 concepts.

| Article | Concepts | Notes |
|---------|----------|-------|
| `https://cognitiontoday.com/why-you-are-consistently-unhappy/` | 12 | Mixed kinds; named concepts verbatim ("Heaven's reward fallacy", "optimism bias") |
| `https://cognitiontoday.com/your-brain-on-productivity-thinking-doing-modes/` | 12 | All 6 brain networks named verbatim with acronyms; author's "city/industries" metaphor preserved |
| `https://cognitiontoday.com/mnemonic-techniques-to-slay-at-memorizing-tutorial/` | 12 | All 10 named techniques captured plus umbrella definition and framework concept |

**Known limitation — `kind` field definition-bias:** Article 3 returned 10 of 12 as "definition" (most should arguably be "technique"). Acceptable because no retrieval logic reads `kind`; the `definition` text that gets embedded is high quality. Documented in `concept_extraction_service.py`. Revisit if Phase 3+ adds kind-based filtering.

## Next action when resuming

**Step 5: Admin backfill endpoint** — ingestion now creates concepts automatically for new document versions. Existing documents ingested before `eea7e95` have zero concepts and need backfill before Step 6 (retrieval integration) can use them.

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
