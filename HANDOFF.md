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
| 6b.2 | Wire concepts into answer prompt + citation handling | Done — see "Phase 2 close — final litmus and accounting" below for final accounting |

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

Run: `tests/litmus/results/20260611T100229Z_concepts_retrieval_only/` (git SHA `67bbcb1`, 8 questions, live `/api/chat` endpoint).

- **Mean chunk recall@5 = 0.300** vs. baseline 0.331 (`20260601T141053Z_post_mmr_and_webstories`). The drop is entirely attributable to `memory_002` (0.25 → 0.00); the other 7 of 8 questions have identical chunk recall@5 to baseline.
- **Mean chunk recall@10 = 0.429** vs. baseline 0.460. That drop is entirely attributable to `mental_health_001` (0.50 → 0.25); `memory_002`'s recall@10 is unchanged (0.25 → 0.25).
- **Mean concept recall@5 = 0.254** (new metric, Step 6b.1).
- **Mean union recall@5 = 0.367** — a +0.067 lift over chunk-only recall@5 (0.300).
- Hit rate 62.5% (5/8), Partial 37.5% (3/8), Full 0%.

## Step 6b.2a diagnostic finding

Step 6b.2a executed 2026-06-12: re-embedded all 3933 concepts using "{term}: {definition}". Diagnostic re-run showed only marginal improvement — Mnemonics moved from 0.4287 to 0.4349, Mind Palace from 0.4078 to 0.4231, but the top-8 floor also dropped (0.4788 → 0.4686), so the relative gap is essentially unchanged. The intervention applied uniformly to all concepts, so concepts that already had query-vocabulary-rich terms benefited as much as the canonical-named ones we hoped to help. The litmus run was skipped — the diagnostic was conclusive enough. Proceeding to 6b.2b (concepts in LLM prompt) to measure that intervention's effect; if Phase 2 needs further retrieval improvement, options like query expansion or concept-to-chunk derivation are documented for Phase 3.

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

---

## Phase 2 close — final litmus and accounting

**Final run:** `tests/litmus/results/20260613T083908Z_with_cited_recall/` (git SHA `c8a33a2`).

### Final numbers (8 questions, against `baseline-post-cleanup` recall@5 = 0.331)

| Metric | Value | Notes |
|---|---|---|
| Mean chunk recall@5 | 0.300 | Identical across last 3 runs — chunk pipeline untouched |
| Mean concept recall@5 | 0.254 | Concept channel retrieval recall |
| Mean union recall@5 | 0.367 | +0.067 lift over chunks-only; the headline Phase 2 retrieval gain |
| Mean cited recall | 0.238 | LLM-filtered citations matching expected URLs |
| Hit rate | 62.5% (5/8) | ≥1 expected URL in top 5 |

### What Phase 2 delivered

1. **Concept extraction pipeline.** 3933 concepts across 325 articles, all embedded (text-embedding-3-large), backfilled idempotently via admin endpoint. Extraction prompt produces 7–15 concepts per article (mean 12.1).
2. **Concept retrieval channel.** Parallel to chunk vector + lexical search; RRF-style scored; surfaces articles chunk retrieval misses (Test B: `/simplifying-depression-a-serious-mental-health-issue/` surfaced via concepts, missed by chunks).
3. **Concepts in LLM prompt.** Unified [Source N] numbering across ARTICLE PASSAGES and KEY CONCEPTS sections. Citations gain `source` field ("chunk" or "concept"). The LLM cites canonical concept definitions for named-term queries.
4. **Litmus infrastructure.** Three new metrics: concept recall, union recall, cited recall. Failure analysis shows chunk URLs, concept URLs, and LLM-cited URLs side-by-side for debugging.

### Known limitations

1. **Memory_002 stubborn miss.** Expected URLs (mnemonic-techniques tutorial, etc.) have 12 high-quality concepts in the DB but rank below verbose memory-themed definitions from tangential articles. Cosine gap is 0.031 — decisive. Documented in `tests/litmus/diagnostics/memory_002_concept_diag.py`. Term+definition re-embedding (Step 6b.2a) gave only marginal improvement (~0.01 in similarity) and didn't move retrieval ranking.
2. **Mental_health_001 ground-truth gap.** Concept channel surfaces `/simplifying-depression-a-serious-mental-health-issue/` for the depression query — qualitatively the right article — but it's not in Aditya's expected URL list. Would need ground truth update from Aditya before declaring this resolved.
3. **LLM citation filtering.** Cited recall systematically lags union recall (0.238 vs 0.367). The LLM filters retrieved sources to what it materially used; for questions with multiple valid expected URLs, this means cited recall is lower-bounded by union but is not the same metric.

### Phase 3 considerations (not committed, parked here)

- **Query expansion.** Rewrite user query before retrieval to include likely concept terms ("How do I improve my memory?" → "...Mnemonics, Method of Loci, memorization techniques..."). Would help canonical-name queries that the current embedding model misses.
- **Concept-to-chunk derivation.** When a concept matches, inject its source article's chunks into the candidate pool. Larger change but addresses the memory_002 class of failure directly.
- **Session-level context.** Aditya's third vector DB (chat session history) for multi-turn conversations.
- **WordPress taxonomy + summaries.** Document summaries and WP tags as additional retrieval signals.
- **Cross-encoder reranker.** Replace lexical-overlap rerank with `cross-encoder/ms-marco-MiniLM-L-6-v2` (or API-based).
- **Restore the `kind` field** if a future consumer needs concept-type filtering (recipe in `concept_extraction_service.py`).

### Step status — all Done

| Step | Description | Commit |
|---|---|---|
| 1 | Concept schema + migration | `1367a6a` |
| 2 | Extraction service + dry-run | `6f9af2f` |
| 3 | Concept repository | `9d76ac9` |
| 4 | Ingest integration | `eea7e95` |
| 5 | Admin backfill endpoint + corpus cleanup | `c972640`, `0717414` |
| 6a | Concept retrieval channel in RetrievalService | `799816a` |
| 6b.1 | Litmus runner with chunk/concept/union recall | `67bbcb1` |
| 6b.2a | Re-embed concepts with term+definition format | `2a8f938` |
| 6b.2b | Concepts in LLM answer prompt | `d46ded5` |
| 6b.2c | Cited recall metric in litmus runner | `c8a33a2` |

---

# Phase 3 — Session Context

## Goal

Add session-level conversation context to the RAG chatbot so multi-turn conversations work coherently. Then deploy to Railway for real-usage feedback.

## Design decisions (locked)

1. **TTL:** 60 minutes idle, refreshed on every chat message (via Redis SETEX)
2. **Session ID:** server-generated UUID, returned in every response JSON body, sent by client in subsequent requests. Frontend stores in sessionStorage.
3. **Reset:** dedicated `DELETE /api/chat/session/<id>` endpoint (Step 3.5)
4. **History pattern:** last 2 turn-pairs verbatim in prompt (RECENT CONVERSATION) + top 3 vector-retrieved older turns (RELEVANT EARLIER CONVERSATION). Query embedding from chunk retrieval is reused for history search.
5. **Turn embedding:** user query and assistant response embedded separately, asynchronously via RQ worker (Step 3.4, done). Turn written with `embedding=None`, `embedding_pending=True`; worker back-fills. Soft-skip on failure after retries exhaust — pending stays true.
6. **Session cap:** 40 turns per session, FIFO eviction.

## Step status

| Step | Description | Status |
|------|-------------|--------|
| 3.1 | SessionRepository — Redis-backed session storage | Done — commit `33fdb8a` |
| 3.2 | Session-aware chat endpoint via SessionService | Done — validated 2026-06-17; commit `b8862da` |
| 3.3a | QueryRewriteService for context-aware retrieval | Done — validated 2026-06-17; commit `d6f4b76` |
| 3.3b | Vector retrieval over session history | Done — validated 2026-06-18; commit `a689067` |
| 3.4 | Async embedding write-back via RQ worker | Done — validated 2026-07-07; commit `cf0e412` |
| 3.5 | Reset endpoint (`DELETE /api/chat/session/<id>`) | Done — validated 2026-07-07; commit `3f24f10` |
| 3.6a | Deploy pipeline fix (migrations on deploy) | Done — commit `4b0db0a`, validated 2026-07-08 |
| 3.6b | Concepts backfill | Done — validated 2026-07-10 (backfill drained 2026-07-08) |

## Step 3.1 — SessionRepository (commit `33fdb8a`)

Redis-backed session storage. Two keys per session: `session:<uuid>` (turn data) and `session:<uuid>:meta` (timestamps + count). 60-min TTL refreshed on writes. 40-turn FIFO cap. Validation script at `scripts/test_session_repo.py` (22 checks, all pass).

Turn shape:
```json
{
  "turn_id": "<uuid>",
  "role": "user" | "assistant",
  "content": "the text",
  "embedding": null | [3072 floats],
  "embedded_at": null | "iso timestamp",
  "embedding_pending": true | false
}
```

## Step 3.2 — Session-aware chat via SessionService (commit `b8862da`)

New `SessionService` (app/services/session_service.py) encapsulates session lifecycle, turn construction, synchronous embedding, and recent-pair extraction. Chat endpoint delegates to it — no inline orchestration.

Behavior:
- Chat endpoint accepts optional `session_id`, creates one on first message
- Returns `session_id` in every response (success + InsufficientContext paths)
- Last 2 turn-pairs injected into LLM prompt under RECENT CONVERSATION section (before ARTICLE PASSAGES and KEY CONCEPTS)
- Soft-skip on embedding failure: turn stored with `embedding=None`, `embedding_pending=True`
- Synchronous embedding adds ~600-800ms per chat response; Step 3.4 moves this to async

Validation via 3-message curl conversation (2026-06-17): Message 2 correctly resolved "it" to method of loci from message 1's RECENT CONVERSATION context. Discovered a follow-on issue that Step 3.3a addresses: ambiguous queries like "How do I actually start using it?" caused chunk retrieval to surface irrelevant articles because retrieval was context-blind.

## Step 3.3a — QueryRewriteService (commit `d6f4b76`)

New `QueryRewriteService` (app/services/query_rewrite_service.py) rewrites the user query using recent conversation before retrieval. Uses gpt-4.1-mini (same as answer model), plain-text output (not JSON), ~500-800ms added latency.

Critical: three separate query variables thread through chat.py:
- `query` (original) → session storage + LLM user prompt
- `retrieval_query` (rewritten) → chunk/concept retrieval
- The rewritten query is exposed in `debug.retrieval_query` for observability

Skips rewriting when recent_pairs is empty (first message) or OPENAI_API_KEY is missing. Soft-skip on any OpenAI error falls back to original query.

Validation results (2026-06-17):

| Message | Original query | Rewritten query | Chunks on-topic |
|---------|---------------|-----------------|-----------------|
| 1 | "What is the method of loci?" | (unchanged — first message) | 5/5 method-of-loci related |
| 2 | "How do I actually start using it?" | "How do I begin practicing and applying the method of loci technique to improve my memory?" | 4/5 (vs 0/5 before rewriting) |
| 3 | "Tell me more." | "Can you provide more detailed tips and examples for effectively using the method of loci (memory palace) technique?" | 5/5 including mnemonic-techniques-to-slay-at-memorizing-tutorial |

Notable Phase 2 crossover: message 3's chunk retrieval now surfaces `/mnemonic-techniques-to-slay-at-memorizing-tutorial/` — the article memory_002 litmus couldn't reach in Phase 2. Query rewriting incidentally addresses part of the Phase 2 canonical-name vs vocabulary-overlap embedding problem when conversation context clarifies the intent.

Response time: ~13 seconds for a message with rewriting (up from ~10s). Argues strongly for Step 3.4 (async embedding write-back) to claw back latency before deployment.

## Step 3.3b — Vector retrieval over session history (commit `a689067`)

Adds a third retrieval channel: cosine-similarity search over prior turn embeddings in the current session. Older turns judged relevant to the current query get injected as a new RELEVANT EARLIER CONVERSATION section, positioned between RECENT CONVERSATION and ARTICLE PASSAGES.

Six sub-decisions locked and implemented:
1. Search over all turn embeddings individually, but return pair-hydrated results (both user turn and its assistant response)
2. Exclude turns already in RECENT CONVERSATION (last 4 turns) + exclude turns where embedding_pending=true
3. Vector search implementation in SessionRepository (Python cosine similarity — up to 40 embeddings per session, negligible latency)
4. Top-K = 3, no similarity threshold for now (revisit if testing shows noise)
5. Prompt structure: current question → RECENT → RELEVANT EARLIER → ARTICLE → CONCEPTS
6. Prompt language for new rule added to `answer_prompt.txt`

Validated 2026-06-18 via diagnostic script and 5-message curl conversation.

- Diagnostic (10-turn synthetic session, `scripts/test_vector_history.py`): loci query hit the loci-pair at similarity 0.886; sleep-and-memory query hit the spaced-repetition pair, with the dreams pair correctly excluded via the recent-window exclusion.
- Live conversation: message 4 ("Going back to the first technique I asked about") surfaced the loci pair in `older_turns` (similarity 0.368) but the answer discussed spaced repetition due to the known rewrite limitation (see below).
- The pair-hydration + exclude-last-N + FIFO-with-embedding-pending-filter combination all work correctly.
- Session state at search time is the pre-write snapshot (`search_older_turns` runs before `write_user_turn`) so exclusion math is correct — the just-written turn doesn't shift the recent-window basis.

## Step 3.4 — Async embedding write-back via RQ worker (commit `cf0e412`)

Moves turn embedding off the chat request path. `SessionService._write_turn` now writes the turn dict synchronously with `embedding_pending=True`, then fire-and-forget enqueues `app.workers.session_jobs.embed_turn` on the existing `rag-jobs` queue. The worker job reads the turn by `(session_id, turn_id)`, embeds via `EmbeddingService`, and calls `SessionRepository.update_turn_embedding` to back-fill.

- Retry: `Retry(max=3, interval=[10, 30, 60])`, `job_timeout=60`. If all attempts fail, the turn stays `embedding_pending=True` — no user-visible failure. Vector search over session history already skips pending turns (Step 3.3b), so nothing breaks; the turn remains available for `recent_pairs` and can be re-embedded on a later message.
- Reuses the `rag-jobs` queue (no queue split) — same worker handles session embedding and ingestion jobs.
- `enqueue_embed_turn` catches `Exception` around the RQ enqueue call itself (Redis unreachable at the RQ layer) and logs a warning rather than raising — the turn is already durably written by that point.
- `create_app()` inside the job follows the same pattern as `ingest_jobs.py` / `concept_jobs.py`.

Validated 2026-07-07: live worker run processed 10 `embed_turn` jobs across two test sessions, all `Job OK`; Redis inspection confirmed every turn flipped `embedding_pending: false` with a populated `embedding` and `embedded_at` timestamp within ~1-6s of the chat response returning. Re-ran the Step 3.3a 3-message context-carrying conversation post-refactor with no regression (query rewriting and history retrieval unaffected).

Timing: reclaims ~2-3 seconds per chat response in practice (measured msg 1: ~14s → ~11.4s; msg 2: ~13s → ~10.8s) — larger than the original ~800ms estimate because synchronous embedding calls were actually costing ~1.5s each, not the estimated ~600ms.

## Step 3.5 — Session reset endpoint (commit `3f24f10`)

New route `DELETE /api/chat/session/<session_id>` wipes a session's conversation history, backing the frontend "New conversation" button. A pure `SessionRepository.delete_session` call — no new service needed.

Design decisions:
- Idempotent — returns 204 whether or not the session existed. End state is what the caller wanted either way.
- No auth for MVP — session_ids are UUID4 (128 bits of entropy), so guessing risk is zero at personal-testing scale.
- No format validation on `session_id` — non-UUID strings are treated as "session doesn't exist" and return 204, same as any other miss.

Validated 2026-07-07 via 6 curl tests, all passing: session created then deleted returns 204 and Redis `EXISTS` goes 1 → 0; a second DELETE on the same id still returns 204 (idempotent); DELETE with a malformed (non-UUID) session_id returns 204; both `session:<id>` and `session:<id>:meta` keys are cleaned up together.

## Known limitations for Phase 3+ follow-on

- **QueryRewriteService doesn't see `older_turns`.** For queries referencing history older than `RAG_HISTORY_RECENT_PAIRS` pairs, the rewritten query anchors to the wrong context. Fix: feed `older_turns` into the rewrite prompt. Requires flipping the compute order (older_turns before rewrite). Adds latency to the rewrite call. Defer until real usage shows this pattern is common.
- **Query embedding is computed twice per request** — once in chat.py for `older_turns` search, once inside `RetrievalService` for chunk/concept vector search. Minor redundancy. Fix: pass embedding as a parameter to `RetrievalService.retrieve()`. Defer as part of a broader Step 3 optimization pass, or after Step 3.4 which will drop other latency more meaningfully.
- ~~**Frontend doesn't thread `session_id` between requests.**~~ Resolved 2026-07-10 in frontend commit `6981a8b`. Frontend now stores session_id from responses, includes it in subsequent chat POSTs, and calls DELETE on New Conversation. Verified via DevTools request payload showing session_id present in follow-up requests, and via context-aware "tell me more" behavior in production browser.

## Step 3.6 — Railway deployment (production)

### Step 3.6a — Deploy pipeline fix (commit `4b0db0a`)

Production Postgres was missing all migrations after the initial schema because the Dockerfile CMD started gunicorn directly with no migration step. Every Phase 2 and Phase 3 push had deployed new code against a stale schema, causing chat requests to 500 on the missing concepts table.

Fix: added `entrypoint.sh` at repo root that runs `flask db upgrade` before starting gunicorn. Modified Dockerfile CMD to invoke the entrypoint. Uses `set -e` so migration failure aborts startup, keeping the previous deploy running until the issue is resolved.

Only affects the web service. Worker service uses a Railway Custom Start Command override (`"python worker.py"`) and is unchanged. Flask auto-discovers the app via `run.py` in `/app` — no `FLASK_APP` env var needed.

Validated 2026-07-08: Railway deploy log confirmed both Phase 2 migrations applied (`2a0bf3ccc1f5` add concepts table, `52bc90ba202a` add embedding_input column). Chat endpoint transitioned from 500 errors to functional responses, initially chunk-only since concepts table was empty.

### Corpus reconciliation (2026-07-08)

Production Postgres had 340 active documents vs local's 325. Audit via short-document query and URL pattern query revealed the same 15 non-article URLs Phase 2 had cleaned locally at commit `0717414` (login, membership-*, contact-us, subscribe, disclaimer, donate, psychology-myth-vs-fact-quiz, can-you-spot-these-cognitive-biases).

Applied the same soft-delete pattern:
- `UPDATE document_versions SET is_active = false` on the 15 matching document_ids
- `UPDATE documents SET active_version_id = NULL` on the same 15 rows

Result: 340 → 325 active documents (matches local exactly). Rollback SQL available if needed but not used.

### Step 3.6b — Concepts backfill (validated 2026-07-10)

Called `POST /api/admin/concepts/backfill` with `limit=400`. Endpoint enqueued 315 jobs (the `~exists()` query in concepts_backfill filters versions that already have concepts — 10 versions apparently had residual concepts from earlier partial work).

Worker drained 315 jobs between 2026-07-08 15:23:53 UTC and 16:50:24 UTC — ~87-minute window.

Verified 2026-07-10 with:
- Total concepts: 3951 (vs local's 3933 — small variance from LLM extraction non-determinism)
- All embedded (`with_embedding` = 3951, without_embedding = 0)
- All with `embedding_input` populated (Phase 2 Step 6b.2a format)
- Distribution matches local: min=7, max=15, avg=12.16 concepts per doc, 0 docs with zero/under-5/over-15

Also verified end-to-end chat via curl:
- Query "What is confirmation bias?" returned 8 concepts, all "Confirmation bias" variants
- Response had 4 citations split between 2 chunks and 2 concepts — both retrieval channels contributed
- Session continuity works: follow-up "tell me more about it" with `session_id` got query-rewritten to "Tell me more about confirmation bias" and returned an expanded 749-char answer

## Phase 3 status (2026-07-10)

Functionally shipped:
- All 6 steps (3.1 through 3.6) complete on production
- End-to-end chat works via curl with full context (query rewriting, session history, chunk + concept retrieval, citations)
- Frontend session_id threading resolved (2026-07-10). Multi-turn conversations, context-aware follow-ups, and session reset all working end-to-end in production browser.
- Steps 3.6c through 3.6f (further Railway hardening) not scoped in this phase

## Phase 3 architectural notes

- **Session data is transient** (Redis, 60-min idle TTL). Deliberately not migrated to Postgres — sessions are conversation-scoped, not corpus-scoped.
- **Query embedding is computed twice per request currently** — once in RetrievalService (chunks/concepts) and once in chat.py (for session history search, added in 3.3b). Duplicate cost; optimization deferred.
- **No frontend yet** — Phase 3 validation is via curl only. Real frontend comes with Railway deployment.

## Environment state (as of end-of-day 2026-06-17)

Postgres and Redis running via docker-compose. Corpus intact from Phase 2 close:
- 325 active documents
- 4179 active chunks
- 3933 active concepts (all embedded)
- 0 active versions missing concepts
