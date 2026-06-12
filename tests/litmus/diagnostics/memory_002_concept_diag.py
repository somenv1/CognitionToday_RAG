import os

import psycopg
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv("/home/somen/cognition-rag/.env")

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large")

DB_DSN = "postgresql://postgres:postgres@localhost:5433/rag_blog"

QUERY = "How do I improve my memory?"

EXPECTED_URLS = [
    "https://cognitiontoday.com/mnemonic-techniques-to-slay-at-memorizing-tutorial/",
    "https://cognitiontoday.com/sciency-guide-to-expert-level-memory-skills/",
    "https://cognitiontoday.com/boost-memory-delay-cognitive-decline-memory-loss/",
    "https://cognitiontoday.com/memorization-techniques-to-improve-memory-for-facts/",
]


def embed(text: str) -> list[float]:
    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.embeddings.create(model=OPENAI_EMBEDDING_MODEL, input=[text])
    return response.data[0].embedding


def vector_literal(embedding: list[float]) -> str:
    return "[" + ",".join(repr(x) for x in embedding) + "]"


def main() -> None:
    query_embedding = embed(QUERY)
    qvec = vector_literal(query_embedding)

    conn = psycopg.connect(DB_DSN)
    cur = conn.cursor()

    # (b) + (c): concepts from the 4 expected URLs, ranked by similarity
    cur.execute(
        """
        SELECT
            d.canonical_url,
            c.term,
            c.definition,
            1 - (c.embedding <=> %s::vector) AS cosine_similarity
        FROM concepts c
        JOIN document_versions dv ON dv.id = c.document_version_id
        JOIN documents d ON d.id = dv.document_id
        WHERE dv.is_active = true
          AND c.embedding IS NOT NULL
          AND d.canonical_url = ANY(%s)
        ORDER BY cosine_similarity DESC
        LIMIT 20
        """,
        (qvec, EXPECTED_URLS),
    )
    expected_rows = cur.fetchall()

    print("=" * 100)
    print(f"Top {len(expected_rows)} concepts from the 4 expected memory_002 URLs, by similarity to:")
    print(f'  "{QUERY}"')
    print("=" * 100)
    for url, term, definition, sim in expected_rows:
        short_url = url.replace("https://cognitiontoday.com", "")
        def_preview = (definition[:80] + "...") if len(definition) > 80 else definition
        print(f"{sim:.4f}  {short_url:60s}  {term!r}")
        print(f"          {def_preview}")

    # (d): top 8 concepts from the entire DB
    cur.execute(
        """
        SELECT
            d.canonical_url,
            c.term,
            c.definition,
            1 - (c.embedding <=> %s::vector) AS cosine_similarity
        FROM concepts c
        JOIN document_versions dv ON dv.id = c.document_version_id
        JOIN documents d ON d.id = dv.document_id
        WHERE dv.is_active = true
          AND c.embedding IS NOT NULL
        ORDER BY cosine_similarity DESC
        LIMIT 8
        """,
        (qvec,),
    )
    top_rows = cur.fetchall()

    print()
    print("=" * 100)
    print("Top 8 concepts from the ENTIRE DB, by similarity to the same query")
    print("=" * 100)
    for url, term, definition, sim in top_rows:
        short_url = url.replace("https://cognitiontoday.com", "")
        def_preview = (definition[:80] + "...") if len(definition) > 80 else definition
        print(f"{sim:.4f}  {short_url:60s}  {term!r}")
        print(f"          {def_preview}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
