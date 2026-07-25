from __future__ import annotations
"""
Chat vectorization subsystem for CyanX AI.

When enabled, each user/assistant message is split into chunks, embedded, and
stored in the chat_vectors table. This allows semantic search over past
conversations: "what did I ask about X last week?"

Key features:
- Vectorization happens on conversation save (server-side)
- Each chunk references message_id + conversation_id
- When a message is deleted, its vectors are deleted (cascade)
- When a conversation is deleted, all its vectors are deleted (cascade)
- Uses the same embedding provider as RAG (local TF-IDF by default, or API)
- Search returns chunks with conversation/message context

This module is self-contained. main.py wires it up to conversation save/delete
endpoints and exposes /api/chat-vectors/search.
"""
import json
from app.db_utils import safe_connect
import re
import sqlite3
import time
import hashlib
from typing import List, Dict, Optional
from pathlib import Path


CHAT_VECTORS_SCHEMA = """
CREATE TABLE IF NOT EXISTS chat_vectors (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    chunk_idx INTEGER NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    keywords TEXT NOT NULL DEFAULT '',
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chat_vectors_conv ON chat_vectors(conversation_id);
CREATE INDEX IF NOT EXISTS idx_chat_vectors_msg ON chat_vectors(message_id);
CREATE INDEX IF NOT EXISTS idx_chat_vectors_created ON chat_vectors(created_at);
"""


def init_chat_vectors_db(db_path: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = safe_connect(db_path)
    conn.executescript(CHAT_VECTORS_SCHEMA)
    conn.commit()
    conn.close()


# ============================================================
# Chunking (reuse RAG chunking logic, but smaller for chat)
# ============================================================

def _split_message_into_chunks(text: str, chunk_size: int = 400, overlap: int = 50) -> List[str]:
    """Split a single message into chunks. Smaller than RAG since chat messages
    are usually shorter and we want fine-grained retrieval."""
    if not text or not text.strip():
        return []
    # If message is short enough, return as single chunk
    if len(text) <= chunk_size:
        return [text.strip()]
    chunks = []
    i = 0
    n = len(text)
    while i < n:
        end = min(i + chunk_size, n)
        if end < n:
            for sep in ["\n\n", "\n", "。", ". ", "! ", "? "]:
                last = text.rfind(sep, i, end)
                if last > i + chunk_size // 2:
                    end = last + len(sep)
                    break
        chunk = text[i:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= n:
            break
        i = end - overlap
        if i < 0:
            i = 0
    return chunks


# ============================================================
# Keyword extraction (lightweight, no external deps)
# ============================================================

_STOPWORDS = set("""
的 了 在 是 我 有 和 就 不 人 都 一 一个 上 也 很 到 说 要 去 你 会 着 没有 看 好 自己 这 那
the a an and or but in on at to for of is are was were be been being have has had do does did
i you he she it we they me him her us them my your his its our their this that these those
""".split())

_ALNUM_RE = re.compile(r"[a-zA-Z0-9]+")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def _extract_keywords(text: str, top_k: int = 12) -> List[str]:
    """Extract keywords from text. Handles Chinese (bigrams) + English (words)."""
    if not text:
        return []
    text_lower = text.lower()
    kws = []
    for m in _ALNUM_RE.findall(text_lower):
        if len(m) >= 2 and m not in _STOPWORDS:
            kws.append(m)
    cjk_chars = _CJK_RE.findall(text_lower)
    for i in range(len(cjk_chars) - 1):
        bigram = cjk_chars[i] + cjk_chars[i + 1]
        if bigram not in _STOPWORDS:
            kws.append(bigram)
    if len(cjk_chars) < 4:
        for c in cjk_chars:
            if c not in _STOPWORDS:
                kws.append(c)
    from collections import Counter
    counter = Counter(kws)
    return [kw for kw, _ in counter.most_common(top_k)]


def _keyword_score(query_kws: List[str], chunk_kws: List[str]) -> float:
    """Simple weighted overlap score."""
    if not query_kws or not chunk_kws:
        return 0.0
    qset = set(query_kws)
    mset = set(chunk_kws)
    inter = qset & mset
    if not inter:
        return 0.0
    score = 0.0
    for i, kw in enumerate(query_kws):
        if kw in mset:
            score += 1.0 / (i + 1)
    return score / max(len(query_kws), 1)


# ============================================================
# Vectorization API
# ============================================================

def vectorize_message(db_path: Path, *, conversation_id: str, message_id: str,
                      role: str, content: str, created_at: Optional[int] = None):
    """Split a message into chunks, extract keywords, and store in chat_vectors.
    Also index into vector_store (ChromaDB or TF-IDF) for semantic search.
    If message_id already has vectors, they are replaced (idempotent)."""
    if not content or not content.strip():
        return 0
    # Delete existing vectors for this message (idempotent re-vectorization)
    delete_message_vectors(db_path, message_id)
    chunks = _split_message_into_chunks(content)
    if not chunks:
        return 0
    now = created_at or int(time.time())
    conn = safe_connect(db_path)
    chunk_ids = []
    for idx, chunk in enumerate(chunks):
        cid = hashlib.sha1(f"{message_id}:{idx}:{chunk[:50]}".encode()).hexdigest()[:16]
        kws = ",".join(_extract_keywords(chunk, top_k=15))
        conn.execute(
            "INSERT INTO chat_vectors (id, conversation_id, message_id, chunk_idx, role, content, keywords, created_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (cid, conversation_id, message_id, idx, role, chunk, kws, now)
        )
        chunk_ids.append(cid)
    conn.commit()
    conn.close()
    # Also index into vector_store for semantic search (ChromaDB or TF-IDF)
    try:
        from app.vector_store import get_vector_store
        vs = get_vector_store(db_path)
        collection = "chat_vectors"
        for idx, chunk in enumerate(chunks):
            cid = chunk_ids[idx]
            vs.add(collection, id=cid, text=chunk,
                   metadata={"conversation_id": conversation_id, "message_id": message_id,
                             "role": role, "created_at": now})
    except Exception as e:
        print(f"[chat_vectors] vector_store sync failed: {e}")
    return len(chunks)


def vectorize_conversation(db_path: Path, *, conversation_id: str, messages: List[Dict]) -> int:
    """Vectorize all messages in a conversation. Returns total chunks created.
    messages: [{id, role, content, created_at}, ...]"""
    total = 0
    for m in messages:
        if not m.get("content"):
            continue
        # Generate message_id if not provided
        mid = m.get("id") or hashlib.sha1(
            f"{conversation_id}:{m.get('role','user')}:{m.get('content','')[:50]}".encode()
        ).hexdigest()[:16]
        total += vectorize_message(
            db_path,
            conversation_id=conversation_id,
            message_id=mid,
            role=m.get("role", "user"),
            content=m["content"],
            created_at=m.get("created_at"),
        )
    return total


def delete_message_vectors(db_path: Path, message_id: str) -> int:
    """Delete all vectors for a specific message. Returns count deleted.
    Also removes from vector_store (ChromaDB or TF-IDF)."""
    # First get chunk IDs so we can delete from vector_store
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id FROM chat_vectors WHERE message_id=?", (message_id,)
    ).fetchall()
    chunk_ids = [r["id"] for r in rows]
    cur = conn.execute("DELETE FROM chat_vectors WHERE message_id=?", (message_id,))
    conn.commit()
    conn.close()
    # Delete from vector_store
    if chunk_ids:
        try:
            from app.vector_store import get_vector_store
            vs = get_vector_store(db_path)
            for cid in chunk_ids:
                vs.delete("chat_vectors", id=cid)
        except Exception as e:
            print(f"[chat_vectors] vector_store delete failed: {e}")
    return cur.rowcount


def delete_conversation_vectors(db_path: Path, conversation_id: str) -> int:
    """Delete all vectors for an entire conversation. Returns count deleted.
    Also removes from vector_store (ChromaDB or TF-IDF)."""
    # First get chunk IDs so we can delete from vector_store
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id FROM chat_vectors WHERE conversation_id=?", (conversation_id,)
    ).fetchall()
    chunk_ids = [r["id"] for r in rows]
    cur = conn.execute("DELETE FROM chat_vectors WHERE conversation_id=?", (conversation_id,))
    conn.commit()
    conn.close()
    # Delete from vector_store
    if chunk_ids:
        try:
            from app.vector_store import get_vector_store
            vs = get_vector_store(db_path)
            for cid in chunk_ids:
                vs.delete("chat_vectors", id=cid)
        except Exception as e:
            print(f"[chat_vectors] vector_store delete failed: {e}")
    return cur.rowcount


def search_chat_vectors(db_path: Path, query: str, *, user_id: str = "default",
                         top_k: int = 5, days_back: int = 0) -> List[Dict]:
    """Semantic search over past chat messages. Returns matching chunks with
    conversation/message context.

    Uses vector_store (ChromaDB if available, TF-IDF fallback) for semantic
    similarity, then enriches with keyword + recency scoring.

    days_back: 0 = no limit, otherwise only search messages from last N days."""
    if not query or not query.strip():
        return []

    # 1. Vector search (semantic, ChromaDB or TF-IDF)
    vector_results: Dict[str, float] = {}  # chunk_id -> score
    try:
        from app.vector_store import get_vector_store
        vs = get_vector_store(db_path)
        results = vs.query("chat_vectors", text=query, top_k=min(top_k * 4, 40))
        for r in results:
            vector_results[r["id"]] = r.get("score", 0)
    except Exception as e:
        print(f"[chat_vectors] vector search failed: {e}")

    # 2. Keyword search (always works, even if vector_store fails)
    qkws = _extract_keywords(query, top_k=15)
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    if days_back > 0:
        cutoff = int(time.time()) - days_back * 86400
        rows = conn.execute(
            "SELECT * FROM chat_vectors WHERE created_at >= ? ORDER BY created_at DESC LIMIT 500",
            (cutoff,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM chat_vectors ORDER BY created_at DESC LIMIT 500"
        ).fetchall()
    conn.close()
    if not rows:
        return []

    # 3. Fused scoring: vector (0.6) + keyword (0.3) + recency (0.1)
    now = int(time.time())
    scored = []
    for row in rows:
        d = dict(row)
        vec_score = vector_results.get(d["id"], 0)
        mkws = d["keywords"].split(",") if d["keywords"] else []
        kw_score = _keyword_score(qkws, mkws)
        age_days = (now - d["created_at"]) / 86400 if d["created_at"] else 999
        recency_score = 1.0 / (1.0 + age_days / 30.0)
        fused = vec_score * 0.6 + kw_score * 0.3 + recency_score * 0.1
        if fused > 0.02:
            scored.append((fused, d))
    scored.sort(key=lambda x: -x[0])
    return [r for _, r in scored[:top_k]]


def get_stats(db_path: Path) -> Dict:
    """Get statistics about the chat vectors store."""
    conn = safe_connect(db_path)
    total = conn.execute("SELECT COUNT(*) FROM chat_vectors").fetchone()[0]
    convs = conn.execute("SELECT COUNT(DISTINCT conversation_id) FROM chat_vectors").fetchone()[0]
    latest = conn.execute("SELECT MAX(created_at) FROM chat_vectors").fetchone()[0]
    conn.close()
    return {
        "total_chunks": total,
        "conversations": convs,
        "latest_vectorized": latest,
    }
