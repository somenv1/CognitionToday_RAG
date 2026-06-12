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
| 6a | Add concept retrieval channel to `RetrievalService` | Done — validated 2026-06-11 (live endpoint returned 8 concepts for the depression query; concept channel surfaced `/simplifying-depression-a-serious-mental-health-issue/`, which the chunk channel missed entirely) |
| 6b.1 | Extend litmus runner to score concept retrieval recall | Done — commit `67bbcb1`; live run results in "Step 6b.1 litmus results" below |
| 6b.2 | Wire concepts into answer prompt + citation handling | Decision pending — see "Step 6b.2 decision" below |

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

## Step 6a validation results

Live `/api/chat` curl for the depression query returned `debug.concepts` with 8 entries. Top concepts came from `/simplifying-depression-a-serious-mental-health-issue/` — an article that wasn't surfacing via chunks for this query at all. Side-by-side comparison of chunk URLs vs. concept URLs showed 3/5 overlap, with 2 channel-unique URLs on each side; the concept channel's unique pick was the most on-the-nose article for the query.

## Step 6b.1 litmus results (live run, `20260611T100229Z`)

Run: `tests/litmus/results/20260611T100229Z/` (git SHA `67bbcb1`, 8 questions, live `/api/chat` endpoint).

- **Mean chunk recall@5 = 0.300** vs. baseline 0.331 (`20260601T141053Z_post_mmr_and_webstories`). The drop is entirely attributable to `memory_002` (0.25 → 0.00); the other 7 of 8 questions have identical chunk recall@5 to baseline.
- **Mean chunk recall@10 = 0.429** vs. baseline 0.460. That drop is entirely attributable to `mental_health_001` (0.50 → 0.25); `memory_002`'s recall@10 is unchanged (0.25 → 0.25).
- **Mean concept recall@5 = 0.254** (new metric, Step 6b.1).
- **Mean union recall@5 = 0.367** — a +0.067 lift over chunk-only recall@5 (0.300).
- Hit rate 62.5% (5/8), Partial 37.5% (3/8), Full 0%.

## memory_002 diagnostic — concept channel under-delivery

For "How do I improve my memory?" (expected URLs include `/mnemonic-techniques-to-slay-at-memorizing-tutorial/`, which has 12 dry-run-validated concepts from Step 2), the concept channel returned 0/4 expected URLs in its top 8.

**Data integrity check** — all 4 expected URLs are active with fully embedded concepts:

| URL | concept_count | embedded_count |
|---|---|---|
| `/mnemonic-techniques-to-slay-at-memorizing-tutorial/` | 12 | 12 |
| `/sciency-guide-to-expert-level-memory-skills/` | 12 | 12 |
| `/boost-memory-delay-cognitive-decline-memory-loss/` | 15 | 15 |
| `/memorization-techniques-to-improve-memory-for-facts/` | 15 | 15 |

**Embedding similarity check** — cosine similarity between the query embedding ("How do I improve my memory?") and concept embeddings, computed via `tests/litmus/diagnostics/memory_002_concept_diag.py`.

Top 20 concepts from the 4 expected URLs:

| Similarity | Source URL | Concept |
|---|---|---|
| 0.4479 | `/boost-memory-delay-cognitive-decline-memory-loss/` | Pygmalion effect |
| 0.4287 | `/mnemonic-techniques-to-slay-at-memorizing-tutorial/` | Mnemonics |
| 0.4146 | `/memorization-techniques-to-improve-memory-for-facts/` | Testing effect |
| 0.4078 | `/mnemonic-techniques-to-slay-at-memorizing-tutorial/` | Mind Palace (Method of Loci) |
| 0.3930 | `/memorization-techniques-to-improve-memory-for-facts/` | Retrieval practice |
| 0.3890 | `/boost-memory-delay-cognitive-decline-memory-loss/` | Memory processes: Encoding, consolidation, retrieval, updating |
| 0.3859 | `/sciency-guide-to-expert-level-memory-skills/` | Retrieval practice |
| 0.3848 | `/memorization-techniques-to-improve-memory-for-facts/` | Procedural memory |
| 0.3844 | `/boost-memory-delay-cognitive-decline-memory-loss/` | Transactive memory |
| 0.3771 | `/sciency-guide-to-expert-level-memory-skills/` | Elaborative rehearsal |
| 0.3743 | `/mnemonic-techniques-to-slay-at-memorizing-tutorial/` | Musical Rhythm |
| 0.3676 | `/memorization-techniques-to-improve-memory-for-facts/` | Elaborative rehearsal |
| 0.3632 | `/sciency-guide-to-expert-level-memory-skills/` | Spacing |
| 0.3550 | `/sciency-guide-to-expert-level-memory-skills/` | Memory reconstruction |
| 0.3526 | `/memorization-techniques-to-improve-memory-for-facts/` | Spacing effect (Distributed practice) |
| 0.3442 | `/boost-memory-delay-cognitive-decline-memory-loss/` | Reconsolidation |
| 0.3433 | `/sciency-guide-to-expert-level-memory-skills/` | Maintenance rehearsal |
| 0.3387 | `/memorization-techniques-to-improve-memory-for-facts/` | Prospective memory |
| 0.3355 | `/memorization-techniques-to-improve-memory-for-facts/` | Forgetting curve |
| 0.3345 | `/sciency-guide-to-expert-level-memory-skills/` | Forgetting |

Actual top-8 returned (entire DB):

| Similarity | Source URL | Concept |
|---|---|---|
| 0.5271 | `/brain-benefits-from-exercise-mechanisms/` | Memory boost from exercise |
| 0.5197 | `/daily-memory-habits-to-improve-confidence-in-memory/` | Long-term memory |
| 0.5166 | `/psychology-facts-neuroscience-trivia/` | Eye movement and memory enhancement in right-handed people |
| 0.5162 | `/how-to-be-smarter-50-actionable-tips-to-have-a-sharp-mind-and-increase-intelligence/` | Memory techniques (peg system & memory palace) |
| 0.4831 | `/brain-hacking-tricks/` | Remember-to-remember trick |
| 0.4820 | `/repetition-tricks-us-into-liking-and-believing-anything/` | Spacing effect in memorization |
| 0.4813 | `/how-to-be-smarter-50-actionable-tips-to-have-a-sharp-mind-and-increase-intelligence/` | Dual n-back task |
| 0.4788 | `/brain-hacking-tricks/` | Side-to-side eye movement for memory boost |

**Finding**: the best concept from any of the 4 expected URLs (0.4479, "Pygmalion effect") scores below the worst concept in the actual top-8 (0.4788) — a decisive, non-marginal gap of 0.031. This is not a data or filtering bug; both checks above confirm the data is clean. The embedding model favors definitions whose text shares query vocabulary ("memory", "remember") over canonically-named concepts (`Mnemonics`, `Method of Loci`) whose definitions describe the same ideas in more abstract/technical terms. Concepts help when query vocabulary overlaps with definition vocabulary; they underperform when canonical naming dominates.

## Step 6b.2 decision (pending)

Two options under consideration, not yet decided:

1. **Proceed as planned** — wire concepts into the answer prompt and citation handling, accepting that the concept channel currently provides the +0.067 union recall@5 lift measured above but doesn't directly help on canonical-naming queries like `memory_002`.
2. **Pause and improve concept embedding quality first** — e.g., embed `term + definition` (or another weighting) instead of `definition` alone, so canonical names like "Mnemonics" and "Method of Loci" pull more weight in the embedding, then re-run the `memory_002` diagnostic and the litmus suite before wiring concepts into the prompt.

No code changes have been made for either option.

## Next action when resuming

Resume with the Step 6b.2 decision above (proceed with prompt wiring, or improve concept embeddings first).

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
- **Step 6b.1 live run (`20260611T100229Z`, git `67bbcb1`):** mean chunk recall@5 = 0.300, recall@10 = 0.429; mean concept recall@5 = 0.254; mean union recall@5 = 0.367. See "Step 6b.1 litmus results" and "memory_002 diagnostic" above.
- **MAX_CHUNKS_PER_DOCUMENT = 1** is a litmus-driven experiment (was 2); revert if Phase 2 doesn't justify the loss.
- Concept-aware metrics (concept recall, union recall) are new in Step 6b.1 and have no pre-Phase-2 baseline to compare against.
