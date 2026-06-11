#!/usr/bin/env python3
"""
Litmus test runner for the cognition RAG system.

Usage:
    python tests/litmus/run_litmus.py [--base-url URL] [--questions PATH] [--timeout SECS]

Outputs (in tests/litmus/results/<timestamp>/):
    raw.json     full API responses + per-question scores
    report.md    summary + per-question table + failure analysis
    config.json  git SHA, timestamp, RAG settings snapshot
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml


LITMUS_DIR = Path(__file__).parent
PROJECT_ROOT = LITMUS_DIR.parent.parent
RESULTS_DIR = LITMUS_DIR / "results"


# ---------------------------------------------------------------------------
# URL canonicalization
# ---------------------------------------------------------------------------

def canonicalize_url(url: str) -> str:
    """Lowercase, strip protocol/query/fragment/trailing-slash."""
    url = url.strip()
    for prefix in ("https://", "http://"):
        if url.lower().startswith(prefix):
            url = url[len(prefix):]
            break
    url = url.lower()
    if "#" in url:
        url = url[: url.index("#")]
    if "?" in url:
        url = url[: url.index("?")]
    return url.rstrip("/")


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _recall_at_k(expected_canonical: set[str], retrieved_urls: list[str], k: int) -> float:
    if not expected_canonical:
        return 0.0
    top_k = {canonicalize_url(u) for u in retrieved_urls[:k]}
    return sum(1 for u in expected_canonical if u in top_k) / len(expected_canonical)


def score_question(question: dict, response_data: dict) -> dict:
    expected_canonical = {canonicalize_url(u) for u in question["expected_urls"]}
    n_expected = len(expected_canonical)

    # reranked_chunks: full reranker output (up to RAG_RERANK_TOP_K = 15).
    # This is the authoritative source for chunk recall metrics.
    reranked = response_data.get("debug", {}).get("reranked_chunks", [])
    reranked_urls = [c["url"] for c in reranked if isinstance(c, dict) and "url" in c]

    chunk_recall_at_5 = _recall_at_k(expected_canonical, reranked_urls, 5)
    chunk_recall_at_10 = _recall_at_k(expected_canonical, reranked_urls, 10)

    top5_canonical = {canonicalize_url(u) for u in reranked_urls[:5]}
    top10_canonical = {canonicalize_url(u) for u in reranked_urls[:10]}
    n_hit_5 = sum(1 for u in expected_canonical if u in top5_canonical)

    hit = n_hit_5 >= 1
    partial = (n_hit_5 / n_expected >= 0.5) if n_expected else False
    full = n_hit_5 == n_expected

    missing_from_top5 = [
        u for u in question["expected_urls"]
        if canonicalize_url(u) not in top5_canonical
    ]

    # debug.concepts: up to RAG_CONCEPT_TOP_K concepts ordered by RRF-style
    # rank. De-dupe to source-article URLs, preserving rank order, since
    # several concepts can come from the same article.
    raw_concepts = response_data.get("debug", {}).get("concepts", [])
    concept_urls: list[str] = []
    seen_concept_urls: set[str] = set()
    for c in raw_concepts:
        if not isinstance(c, dict) or "url" not in c:
            continue
        canonical = canonicalize_url(c["url"])
        if canonical not in seen_concept_urls:
            seen_concept_urls.add(canonical)
            concept_urls.append(c["url"])

    concept_recall_at_5 = _recall_at_k(expected_canonical, concept_urls, 5)
    concept_recall_at_8 = _recall_at_k(expected_canonical, concept_urls, 8)

    # Union: an expected URL counts as retrieved if it's in the chunk top-K
    # OR anywhere in the (de-duped) concept URLs — this is the headline
    # Phase 2 metric.
    concept_canonical = {canonicalize_url(u) for u in concept_urls}
    union5_canonical = top5_canonical | concept_canonical
    union10_canonical = top10_canonical | concept_canonical
    union_recall_at_5 = (
        sum(1 for u in expected_canonical if u in union5_canonical) / n_expected
        if n_expected else 0.0
    )
    union_recall_at_10 = (
        sum(1 for u in expected_canonical if u in union10_canonical) / n_expected
        if n_expected else 0.0
    )

    # citations = LLM-filtered sources; recorded for answer-quality audit only.
    citation_urls = [
        c.get("url", "") for c in response_data.get("citations", [])
        if isinstance(c, dict)
    ]

    return {
        "id": question["id"],
        "category": question.get("category", ""),
        "question": question["question"],
        "status": "ok",
        "hit": hit,
        "partial": partial,
        "full": full,
        "chunk_recall_at_5": chunk_recall_at_5,
        "chunk_recall_at_10": chunk_recall_at_10,
        "concept_recall_at_5": concept_recall_at_5,
        "concept_recall_at_8": concept_recall_at_8,
        "union_recall_at_5": union_recall_at_5,
        "union_recall_at_10": union_recall_at_10,
        "expected_urls": question["expected_urls"],
        "reranked_urls": reranked_urls,
        "concept_urls": concept_urls,
        "citation_urls": citation_urls,
        "missing_from_top5": missing_from_top5,
        "available_reranked": len(reranked_urls),
        "answer": response_data.get("answer", ""),
        "confidence": response_data.get("confidence", ""),
        "grounded": response_data.get("grounded", False),
        "notes": question.get("notes", ""),
    }


# ---------------------------------------------------------------------------
# API call
# ---------------------------------------------------------------------------

def call_api(base_url: str, question: dict, timeout: int) -> dict:
    endpoint = f"{base_url.rstrip('/')}/api/chat"
    print(f"  [{question['id']}] {question['question'][:80]}")
    try:
        resp = requests.post(
            endpoint,
            json={"query": question["question"]},
            timeout=timeout,
        )
        resp.raise_for_status()
        return {"status": "ok", "data": resp.json()}
    except requests.exceptions.Timeout:
        msg = f"timeout after {timeout}s"
        print(f"           ERROR: {msg}")
        return {"status": "error", "error": msg}
    except requests.exceptions.HTTPError as exc:
        msg = f"HTTP {exc.response.status_code}: {exc.response.text[:200]}"
        print(f"           ERROR: {msg}")
        return {"status": "error", "error": msg}
    except Exception as exc:
        msg = str(exc)
        print(f"           ERROR: {msg}")
        return {"status": "error", "error": msg}


# ---------------------------------------------------------------------------
# Config snapshot (mirrors app/config.py, loaded from env/.env)
# ---------------------------------------------------------------------------

def _load_env_config() -> dict:
    env: dict = {}
    try:
        from dotenv import dotenv_values
        env = dotenv_values(PROJECT_ROOT / ".env") or {}
    except Exception:
        pass

    def _get(key: str, default: str) -> str:
        return os.environ.get(key) or env.get(key) or default

    return {
        "RAG_VECTOR_TOP_K": int(_get("RAG_VECTOR_TOP_K", "30")),
        "RAG_LEXICAL_TOP_K": int(_get("RAG_LEXICAL_TOP_K", "20")),
        "RAG_RERANK_TOP_K": int(_get("RAG_RERANK_TOP_K", "15")),
        "RAG_FINAL_CONTEXT_K": int(_get("RAG_FINAL_CONTEXT_K", "5")),
        "RAG_SCORE_THRESHOLD": float(_get("RAG_SCORE_THRESHOLD", "0.015")),
        "RAG_CONCEPT_TOP_K": int(_get("RAG_CONCEPT_TOP_K", "8")),
        "OPENAI_CHAT_MODEL": _get("OPENAI_CHAT_MODEL", "gpt-4.1-mini"),
        "OPENAI_EMBEDDING_MODEL": _get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large"),
        "BLOG_SITEMAP_URL": _get("BLOG_SITEMAP_URL", ""),
    }


def build_config_json(base_url: str, git_sha: str, timestamp: str) -> dict:
    cfg = _load_env_config()
    return {
        "timestamp": timestamp,
        "git_sha": git_sha,
        "base_url": base_url,
        "rag_settings": {
            "RAG_VECTOR_TOP_K": cfg["RAG_VECTOR_TOP_K"],
            "RAG_LEXICAL_TOP_K": cfg["RAG_LEXICAL_TOP_K"],
            "RAG_RERANK_TOP_K": cfg["RAG_RERANK_TOP_K"],
            "RAG_FINAL_CONTEXT_K": cfg["RAG_FINAL_CONTEXT_K"],
            "RAG_SCORE_THRESHOLD": cfg["RAG_SCORE_THRESHOLD"],
            "RAG_CONCEPT_TOP_K": cfg["RAG_CONCEPT_TOP_K"],
        },
        "model_settings": {
            "OPENAI_CHAT_MODEL": cfg["OPENAI_CHAT_MODEL"],
            "OPENAI_EMBEDDING_MODEL": cfg["OPENAI_EMBEDDING_MODEL"],
        },
        "blog_settings": {
            "BLOG_SITEMAP_URL": cfg["BLOG_SITEMAP_URL"],
        },
        "recall_source": (
            "Chunk recall: debug.reranked_chunks — full reranker output before "
            "RAG_FINAL_CONTEXT_K slice. recall@5 uses top-5, recall@10 uses top-10 "
            "from this list. Concept recall: debug.concepts — up to RAG_CONCEPT_TOP_K "
            "concepts, de-duped to source-article URLs, ordered by RRF-style rank. "
            "Union recall: chunk top-K OR concept URLs."
        ),
    }


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def _pct(n: int, d: int) -> str:
    return f"{n / d:.1%} ({n}/{d})" if d else "n/a"


def build_report(results: list[dict], timestamp: str, git_sha: str) -> str:
    scored = [r for r in results if r.get("status") == "ok" and "hit" in r]
    errors = [r for r in results if r.get("status") == "error"]
    n_total = len(results)
    n_scored = len(scored)

    n_hit = sum(1 for r in scored if r["hit"])
    n_partial = sum(1 for r in scored if r["partial"])
    n_full = sum(1 for r in scored if r["full"])
    mean_chunk_r5 = sum(r["chunk_recall_at_5"] for r in scored) / n_scored if n_scored else 0.0
    mean_chunk_r10 = sum(r["chunk_recall_at_10"] for r in scored) / n_scored if n_scored else 0.0
    mean_concept_r5 = sum(r["concept_recall_at_5"] for r in scored) / n_scored if n_scored else 0.0
    mean_union_r5 = sum(r["union_recall_at_5"] for r in scored) / n_scored if n_scored else 0.0

    lines: list[str] = []

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    lines += [
        "# Summary",
        "",
        f"- **Run timestamp**: {timestamp}",
        f"- **Git SHA**: `{git_sha}`",
        f"- **Total questions**: {n_total}"
        + (f" ({n_total - n_scored} errors)" if errors else ""),
        f"- **Hit rate** (≥1 expected URL in top 5): {_pct(n_hit, n_scored)}",
        f"- **Partial rate** (≥50% expected URLs in top 5): {_pct(n_partial, n_scored)}",
        f"- **Full rate** (all expected URLs in top 5): {_pct(n_full, n_scored)}",
        f"- **Mean recall@5**: {mean_chunk_r5:.3f}",
        f"- **Mean recall@10**: {mean_chunk_r10:.3f}",
        f"- **Mean concept recall@5**: {mean_concept_r5:.3f}",
        f"- **Mean union recall@5**: {mean_union_r5:.3f}",
        "",
        "> Chunk recall is computed from `debug.reranked_chunks` (full reranker output,",
        "> up to `RAG_RERANK_TOP_K = 15`). recall@5 = top-5 of that list; recall@10 = top-10.",
        ">",
        "> Concept recall is computed from `debug.concepts` (up to `RAG_CONCEPT_TOP_K = 8`,",
        "> de-duped to source-article URLs, ordered by RRF-style rank).",
        ">",
        "> Union recall counts an expected URL as retrieved if it appears in the chunk",
        "> top-K OR anywhere in the concept URLs — the headline Phase 2 retrieval metric.",
    ]

    # ------------------------------------------------------------------
    # Per-question table
    # ------------------------------------------------------------------
    lines += [
        "",
        "---",
        "",
        "# Per Question Results",
        "",
        "| Question ID | Category | Hit | Partial | Full | Recall@5 | Recall@10 | Concept@5 | Union@5 | Union@10 | Reranked |",
        "|-------------|----------|:---:|:-------:|:----:|:--------:|:---------:|:---------:|:-------:|:--------:|:--------:|",
    ]

    for r in results:
        if r.get("status") == "ok" and "hit" in r:
            h = "✓" if r["hit"] else "✗"
            p = "✓" if r["partial"] else "✗"
            f = "✓" if r["full"] else "✗"
            lines.append(
                f"| `{r['id']}` | {r['category']} | {h} | {p} | {f}"
                f" | {r['chunk_recall_at_5']:.2f} | {r['chunk_recall_at_10']:.2f}"
                f" | {r['concept_recall_at_5']:.2f} | {r['union_recall_at_5']:.2f}"
                f" | {r['union_recall_at_10']:.2f} | {r['available_reranked']} |"
            )
        else:
            err = r.get("error", "unknown error")[:50]
            lines.append(
                f"| `{r['id']}` | {r.get('category', '')} | — | — | —"
                f" | — | — | — | — | — | ERROR: {err} |"
            )

    # ------------------------------------------------------------------
    # Failure analysis
    # ------------------------------------------------------------------
    lines += ["", "---", "", "# Failure Analysis", ""]

    failures = [r for r in scored if not r["full"]]

    if not failures and not errors:
        lines.append("All questions retrieved all expected URLs in top 5. No failures.")
    else:
        for r in failures:
            if not r["hit"]:
                label = "MISS"
            elif not r["partial"]:
                label = "HIT"
            else:
                label = "PARTIAL"
            expected_c = {canonicalize_url(u) for u in r["expected_urls"]}

            lines += [
                f"## `{r['id']}` — {label}",
                "",
                f"**Question**: {r['question']}",
            ]
            if r.get("notes"):
                lines.append(f"**Notes**: {r['notes']}")
            lines += ["", "**Expected URLs**:"]
            for u in r["expected_urls"]:
                lines.append(f"- `{u}`")

            lines += ["", "**Top-5 reranked URLs**:"]
            if r["reranked_urls"]:
                for i, u in enumerate(r["reranked_urls"][:5], 1):
                    found = " ✓" if canonicalize_url(u) in expected_c else ""
                    lines.append(f"- [{i}] `{u}`{found}")
            else:
                lines.append("- *(none retrieved)*")

            lines += ["", "**Concept-derived URLs**:"]
            if r["concept_urls"]:
                for i, u in enumerate(r["concept_urls"], 1):
                    found = " ✓" if canonicalize_url(u) in expected_c else ""
                    lines.append(f"- [{i}] `{u}`{found}")
            else:
                lines.append("- *(none retrieved)*")

            if r["missing_from_top5"]:
                lines += ["", "**Missing from top 5**:"]
                for u in r["missing_from_top5"]:
                    in_top10 = canonicalize_url(u) in {
                        canonicalize_url(x) for x in r["reranked_urls"][:10]
                    }
                    suffix = " *(present in top 10)*" if in_top10 else ""
                    lines.append(f"- `{u}`{suffix}")

            lines.append("")

        for r in errors:
            lines += [
                f"## `{r['id']}` — API ERROR",
                "",
                f"**Question**: {r['question']}",
                f"**Error**: `{r.get('error', 'unknown')}`",
                "",
            ]

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def _git_sha() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True, cwd=PROJECT_ROOT,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Litmus test runner for the cognition RAG API.")
    parser.add_argument(
        "--base-url", default="http://127.0.0.1:8000",
        help="Base URL of the API server (default: http://127.0.0.1:8000)",
    )
    parser.add_argument(
        "--questions", default=str(LITMUS_DIR / "questions.yaml"),
        help="Path to questions YAML or JSON file",
    )
    parser.add_argument(
        "--timeout", type=int, default=60,
        help="Per-request timeout in seconds (default: 60)",
    )
    args = parser.parse_args()

    questions_path = Path(args.questions)
    if not questions_path.exists():
        print(f"ERROR: questions file not found: {questions_path}", file=sys.stderr)
        sys.exit(1)

    with open(questions_path) as f:
        data = yaml.safe_load(f) if questions_path.suffix in (".yaml", ".yml") else json.load(f)
    questions = data["questions"]

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    git_sha = _git_sha()
    results_dir = RESULTS_DIR / timestamp
    results_dir.mkdir(parents=True, exist_ok=True)

    print("=== Cognition RAG Litmus Test ===")
    print(f"Timestamp : {timestamp}")
    print(f"Git SHA   : {git_sha}")
    print(f"Base URL  : {args.base_url}")
    print(f"Questions : {len(questions)} (from {questions_path.name})")
    print(f"Timeout   : {args.timeout}s per request")
    print(f"Results   : {results_dir}")
    print()

    all_results: list[dict] = []

    for q in questions:
        api_result = call_api(args.base_url, q, args.timeout)
        if api_result["status"] == "ok":
            scored = score_question(q, api_result["data"])
            scored["raw_response"] = api_result["data"]
            r5, r10 = scored["chunk_recall_at_5"], scored["chunk_recall_at_10"]
            c5, u5 = scored["concept_recall_at_5"], scored["union_recall_at_5"]
            label = "HIT " if scored["hit"] else "MISS"
            print(
                f"           {label} | recall@5={r5:.2f}"
                f" | recall@10={r10:.2f}"
                f" | concept@5={c5:.2f}"
                f" | union@5={u5:.2f}"
                f" | reranked={scored['available_reranked']}"
            )
        else:
            scored = {
                "id": q["id"],
                "category": q.get("category", ""),
                "question": q["question"],
                "status": "error",
                "error": api_result.get("error", "unknown"),
                "raw_response": {},
                "notes": q.get("notes", ""),
            }
        all_results.append(scored)
        print()

    print("Writing results...")

    raw_payload = {
        "timestamp": timestamp,
        "git_sha": git_sha,
        "base_url": args.base_url,
        "questions_file": str(questions_path),
        "results": all_results,
    }
    (results_dir / "raw.json").write_text(json.dumps(raw_payload, indent=2, default=str))

    config_data = build_config_json(args.base_url, git_sha, timestamp)
    (results_dir / "config.json").write_text(json.dumps(config_data, indent=2))

    report = build_report(all_results, timestamp, git_sha)
    (results_dir / "report.md").write_text(report)

    print(f"  raw.json    -> {results_dir / 'raw.json'}")
    print(f"  config.json -> {results_dir / 'config.json'}")
    print(f"  report.md   -> {results_dir / 'report.md'}")
    print()

    scored = [r for r in all_results if "hit" in r]
    if scored:
        hit_rate = sum(1 for r in scored if r["hit"]) / len(scored)
        mean_r5 = sum(r["chunk_recall_at_5"] for r in scored) / len(scored)
        mean_union_r5 = sum(r["union_recall_at_5"] for r in scored) / len(scored)
        print("=== Summary ===")
        print(f"Scored   : {len(scored)}/{len(all_results)}")
        print(f"Hit rate : {hit_rate:.1%}")
        print(f"Mean R@5 : {mean_r5:.3f}")
        print(f"Mean Union@5 : {mean_union_r5:.3f}")


if __name__ == "__main__":
    main()
