# Project conventions for Claude Code

## Commits
- Never add Co-Authored-By trailers or AI attribution.
- Plain `git commit -m` syntax; no heredoc cat tricks.

## Schema patterns
- All primary keys use String, not UUID(as_uuid=True), to maintain SQLite compatibility for local testing.
- JSONB is used for new metadata columns when GIN-indexable queries may be needed; existing tables use plain JSON.

## Litmus testing
- Baseline (post-cleanup): mean recall@5 = 0.331, recall@10 = 0.460 at git tag baseline-post-cleanup.
- 4-label scoring: MISS / HIT / PARTIAL / FULL.
- MAX_CHUNKS_PER_DOCUMENT = 1 is an experiment; revert if Phase 2 doesn't justify the second-chunk loss.

## Vector indexing
- pgvector 0.8.2 caps both ivfflat and HNSW at 2000 dims.
- chunks.embedding and concepts.embedding both run sequential scan.
- Revisit at ~50k+ rows (see README production hardening).

## Diagnostic discipline
- When the spec deviates from an existing project pattern, flag it before coding.
- Storage/indexing details (JSON vs JSONB, index type): treat spec as authoritative when explicit.
- FK types, naming, anything cross-table: always ask before proceeding.
- When user asks for a specific diagnostic output, run it and SHOW the output before making decisions on it.
