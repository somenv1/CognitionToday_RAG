# One-off validation for Step 3.1. Safe to delete after Phase 3 ships.

import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from redis import Redis
from app.repositories.session_repo import SessionRepository, SessionNotFoundError

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis = Redis.from_url(REDIS_URL)
repo = SessionRepository(redis)


def _is_uuid(s: str) -> bool:
    try:
        uuid.UUID(s)
        return True
    except ValueError:
        return False


def _make_turn(role: str, content: str) -> dict:
    return {
        "turn_id": str(uuid.uuid4()),
        "role": role,
        "content": content,
        "embedding": None,
        "embedded_at": None,
        "embedding_pending": True,
    }


def check(label: str, condition: bool) -> None:
    mark = "✓" if condition else "✗"
    print(f"  [{mark}] {label}")
    if not condition:
        raise AssertionError(f"FAILED: {label}")


print("\n=== Step 3.1 SessionRepository validation ===\n")

# ------------------------------------------------------------------
# 1. Create a session; assert both Redis keys exist
# ------------------------------------------------------------------
print("1. Create session")
session_id, blob = repo.create_session()
check("returned session_id is a UUID string", _is_uuid(session_id))
check("blob has session_id", blob.get("session_id") == session_id)
check("blob has empty turns", blob.get("turns") == [])
check("data key exists in Redis", redis.exists(f"session:{session_id}") == 1)
check("meta key exists in Redis", redis.exists(f"session:{session_id}:meta") == 1)

# ------------------------------------------------------------------
# 2. Append 3 turns; get_session returns them in order
# ------------------------------------------------------------------
print("\n2. Append turns and read back in order")
t1 = _make_turn("user", "Hello, how are you?")
t2 = _make_turn("assistant", "I am doing well, thanks!")
t3 = _make_turn("user", "What is the brain default mode network?")
repo.append_turn(session_id, t1)
repo.append_turn(session_id, t2)
repo.append_turn(session_id, t3)

session = repo.get_session(session_id)
check("get_session returns 3 turns", len(session["turns"]) == 3)
check("turns in insertion order", session["turns"][0]["turn_id"] == t1["turn_id"])
check("third turn matches", session["turns"][2]["turn_id"] == t3["turn_id"])

# ------------------------------------------------------------------
# 3. Update an embedding; confirm pending flag flips
# ------------------------------------------------------------------
print("\n3. Update embedding on a turn")
fake_embedding = [0.1] * 3072
result = repo.update_turn_embedding(session_id, t2["turn_id"], fake_embedding)
check("update returns updated blob", result is not None)
updated_turn = next(t for t in result["turns"] if t["turn_id"] == t2["turn_id"])
check("embedding stored", updated_turn["embedding"] == fake_embedding)
check("embedding_pending is False", updated_turn["embedding_pending"] is False)
check("embedded_at is set", updated_turn["embedded_at"] is not None)
check("other turn embedding_pending still True",
      next(t for t in result["turns"] if t["turn_id"] == t1["turn_id"])["embedding_pending"] is True)

pending = repo.get_pending_embeddings(session_id)
check("get_pending_embeddings returns 2 (t1, t3)", len(pending) == 2)

# ------------------------------------------------------------------
# 4. Append 40+ turns; confirm eviction keeps len at 40
# ------------------------------------------------------------------
print("\n4. Eviction at 40-turn cap")
# Already have 3 turns; add 38 more to hit 41 total
for i in range(38):
    repo.append_turn(session_id, _make_turn("user", f"turn {i}"))

session = repo.get_session(session_id)
check("40 turns after exceeding cap", len(session["turns"]) == 40)
check("oldest turn evicted (t1 gone)",
      not any(t["turn_id"] == t1["turn_id"] for t in session["turns"]))
check("t2 still present (second oldest)",
      any(t["turn_id"] == t2["turn_id"] for t in session["turns"]))

# ------------------------------------------------------------------
# 5. Delete session; get_session returns None
# ------------------------------------------------------------------
print("\n5. Delete session")
deleted = repo.delete_session(session_id)
check("delete returns True", deleted is True)
check("get_session returns None after delete", repo.get_session(session_id) is None)
check("data key gone", redis.exists(f"session:{session_id}") == 0)
check("meta key gone", redis.exists(f"session:{session_id}:meta") == 0)
deleted_again = repo.delete_session(session_id)
check("second delete returns False", deleted_again is False)

# ------------------------------------------------------------------
# 6. SessionNotFoundError on append to missing session
# ------------------------------------------------------------------
print("\n6. SessionNotFoundError for missing session")
fake_id = str(uuid.uuid4())
raised = False
try:
    repo.append_turn(fake_id, _make_turn("user", "this should fail"))
except SessionNotFoundError:
    raised = True
check("SessionNotFoundError raised for non-existent session_id", raised)

# update_turn_embedding on expired session returns None (no error)
result = repo.update_turn_embedding(fake_id, str(uuid.uuid4()), [0.0] * 3072)
check("update_turn_embedding on missing session returns None", result is None)

print("\n=== All checks passed ===\n")
