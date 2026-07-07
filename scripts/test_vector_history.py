# Diagnostic for Step 3.3b. Populates a synthetic session, runs vector
# search, prints top matches. Safe to delete after Phase 3 ships.

import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from redis import Redis
from app.repositories.session_repo import SessionRepository
from app.services.embedding_service import EmbeddingService

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis = Redis.from_url(REDIS_URL)
repo = SessionRepository(redis)

# Build a config just for the embedding service.
config = {
    "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
    "OPENAI_EMBEDDING_MODEL": os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large"),
}
embedder = EmbeddingService(config)

# Synthetic 10-turn conversation across three topics.
turns_data = [
    ("user", "What is the method of loci?"),
    ("assistant", "The method of loci is a mnemonic technique using visualized locations to remember information..."),
    ("user", "What about the peg system?"),
    ("assistant", "The peg system associates numbers with rhyming words or visual pegs..."),
    ("user", "Can you explain spaced repetition?"),
    ("assistant", "Spaced repetition schedules review at increasing intervals to strengthen memory..."),
    ("user", "How does forgetting work?"),
    ("assistant", "Forgetting is governed by decay and interference in memory traces..."),
    ("user", "What's the science of dreams?"),
    ("assistant", "Dreams occur mostly in REM sleep and are thought to consolidate memories..."),
]

print(f"\nPopulating synthetic session with {len(turns_data)} turns...")
session_id, _ = repo.create_session()

for role, content in turns_data:
    embedding = embedder.embed_texts([content])[0]
    turn = {
        "turn_id": str(uuid.uuid4()),
        "role": role,
        "content": content,
        "embedding": embedding,
        "embedded_at": "2026-06-17T00:00:00Z",
        "embedding_pending": False,
    }
    repo.append_turn(session_id, turn)

print(f"Session {session_id} populated.\n")

# Test: query about method of loci should match turns 0-1 even though
# they're excluded from RECENT CONVERSATION (last 4 turns).
test_queries = [
    "How do I use the method of loci?",
    "Tell me more about mnemonics",
    "What was the first technique we discussed?",
    "Explain sleep and memory",
]

for q in test_queries:
    print(f"Query: {q!r}")
    query_embedding = embedder.embed_texts([q])[0]
    results = repo.vector_search_turns(
        session_id=session_id,
        query_embedding=query_embedding,
        top_k=3,
        exclude_last_n=4,  # simulate exclusion of RECENT CONVERSATION (last 2 pairs)
    )
    if not results:
        print("  (no results)\n")
        continue
    for i, r in enumerate(results, 1):
        print(f"  [{i}] similarity={r['similarity']:.4f}")
        print(f"      user: {r['user'][:80]}")
        print(f"      assistant: {r['assistant'][:80]}")
    print()

# Cleanup
repo.delete_session(session_id)
print("Deleted test session.\n")
