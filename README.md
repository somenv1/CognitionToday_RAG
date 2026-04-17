# Cognition Today RAG Assistant

Production-oriented Flask scaffold for a blog RAG chatbot deployed on Railway.

## Architecture

### Retrieval path

1. `POST /api/chat` receives the user query.
2. `RetrievalService` normalizes the query.
3. Candidate generation runs through:
   - vector search in Postgres + pgvector
   - lexical fallback search
4. `RerankService` reorders the candidate set.
5. `AnswerService` builds a grounded prompt and calls the LLM.
6. The API returns the answer, citations, and retrieval debug payload.

### Ingestion path

1. Admin or cron enqueues a sitemap sync or single-URL ingest job.
2. `IngestService` fetches article HTML.
3. `CleanService` extracts article body markdown.
4. `ChunkService` creates structure-aware chunks.
5. `EmbeddingService` creates vectors.
6. Chunks are stored in Postgres with metadata and embeddings.

## Project structure

```text
app/
  api/                 HTTP blueprints
  models/              SQLAlchemy schema
  prompts/             Grounding prompts
  repositories/        DB access helpers
  services/            Ingestion, retrieval, answer orchestration
  workers/             RQ job entry points
run.py                 Flask web entry
worker.py              Queue worker entry
```

## Data model

- `documents`: canonical article identity
- `document_versions`: versioned cleaned article content
- `chunks`: chunk text, metadata, and vector
- `ingestion_jobs`: ingestion job state
- `query_logs`: retrieval traces and answer telemetry

## Why this design matters

- Versioned documents prevent silent stale-index bugs.
- Chunk metadata preserves citation quality.
- Retrieval is isolated from Flask routing, which keeps the request path testable.
- Worker separation prevents indexing spikes from affecting chat latency.

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
docker compose -f docker-compose.local.yml up -d
flask --app run.py db init
flask --app run.py db migrate -m "initial schema"
flask --app run.py db upgrade
python run.py
```

Start the worker separately:

```bash
python worker.py
```

If you prefer shortcuts:

```bash
make setup
make up
make init-db
make run
```

## Postman smoke test

Base URL:

```text
http://127.0.0.1:8000
```

1. Health check

```http
GET /healthz
```

Expected response:

```json
{"status":"ok"}
```

2. Ingest one article

```http
POST /api/admin/ingest
Content-Type: application/json

{
  "url": "https://cognitiontoday.com/ai-forked-us/"
}
```

Expected response:

```json
{
  "status": "queued",
  "job_id": "...",
  "url": "https://cognitiontoday.com/ai-forked-us/"
}
```

3. Check queue length

```http
GET /api/admin/queue
```

4. Ask a question

```http
POST /api/chat
Content-Type: application/json

{
  "query": "What is the article AI Forked Us about?"
}
```

If `OPENAI_API_KEY` is not set, the API will still return retrieval debug data and citations, but answer generation will stay in safe fallback mode.

Local infrastructure ports:

- Postgres: `localhost:5433`
- Redis: `localhost:6379`

## Railway deployment

Create separate Railway services:

1. `web`
   - Start command: `gunicorn run:app`
2. `worker`
   - Start command: `python worker.py`
3. `redis`
4. `postgres-pgvector`
5. optional scheduled service or Railway cron to call `/api/admin/ingest`

Recommended Railway environment variables:

- `DATABASE_URL`
- `REDIS_URL`
- `OPENAI_API_KEY`
- `OPENAI_CHAT_MODEL=gpt-4.1-mini`
- `OPENAI_EMBEDDING_MODEL=text-embedding-3-large`
- `BLOG_SITEMAP_URL`

## Production hardening checklist

- Replace `ILIKE` lexical search with PostgreSQL full-text search or BM25
- Add a real reranker model instead of lexical-overlap reranking
- Add auth on admin endpoints
- Add retry policy and dead-letter queue for ingestion failures
- Add eval suite with labeled blog questions
- Add caching for repeated queries
- Add observability for retrieval scores, latency, and token spend

## Example chunking behavior

Input:

```markdown
# What Is Confirmation Bias?

## Definition
Confirmation bias is the tendency to seek evidence that supports an existing belief.

## Examples in Daily Life
People may notice stories that confirm their views and ignore counterexamples.
```

Output chunks:

1. `[What Is Confirmation Bias? > Definition]`
2. `[What Is Confirmation Bias? > Examples in Daily Life]`

Target chunk size:

- `400-450` target tokens
- `600` token hard max before paragraph splitting
- `50-80` token overlap

Chunk metadata stored with each row:

- `heading_path`
- `token_count`
- `word_count`
- `paragraph_count`
- `prev_chunk_id`
- `next_chunk_id`
- `embedding_text`

Embedding text is contextualized with the heading path, for example:

```text
Section: What Is Confirmation Bias? > Examples in Daily Life

People may notice stories that confirm their views and ignore counterexamples.
```

This improves retrieval for queries that match section intent more than paragraph wording.

## Immediate next implementation steps

1. Add a proper migration set and create the tables.
2. Wire full-text search with `tsvector`.
3. Add an evaluation script with gold questions.
4. Replace placeholder reranking with a stronger cross-encoder or API reranker.

