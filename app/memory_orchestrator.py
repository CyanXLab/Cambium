from __future__ import annotations
from app.llm_utils import extract_content as _extract_content
from app.db_utils import safe_connect


def _get_prompt(key, default):
    """Get prompt from settings (lazy import to avoid circular)."""
    try:
        from app.main import get_prompt
        return get_prompt(key, default)
    except Exception:
        return default
"""
Memory Orchestrator / Context Builder for CyanX AI.

This is the brain of the memory system. It:
1. Classifies memories into 4 layers by importance (working/short/long/permanent)
2. Applies decay (forgetting) based on time + importance
3. Retrieves from multiple sources (layers + chat vectors + KG + episodes + profile)
4. Builds an optimized context for the LLM, prioritizing by relevance + importance + recency

Layers:
- working:    current conversation messages (handled by chat_stream directly)
- short_term: last 24h, low importance, auto-expires
- long_term:  important facts learned over time, decays slowly
- permanent:  identity, core preferences, names — never decays

Importance scoring (0-100):
- 0-20:   discard (chit-chat, temp questions)
- 21-50:  short_term
- 51-80:  long_term
- 81-100: permanent

Multi-modal retrieval fusion:
  score = embedding_score * 0.35
        + keyword_score * 0.25
        + importance_bonus * 0.20
        + recency_bonus * 0.10
        + kg_relevance * 0.10

Self-contained module. main.py calls build_context() in chat_stream and
classify_and_store() after each conversation turn.
"""
import json
import re
import sqlite3
import time
import math
import hashlib
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from collections import defaultdict


ORCHESTRATOR_SCHEMA = """
CREATE TABLE IF NOT EXISTS memory_items (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    content TEXT NOT NULL,
    layer TEXT NOT NULL DEFAULT 'short_term',  -- working/short_term/long_term/permanent
    importance INTEGER NOT NULL DEFAULT 30,
    category TEXT NOT NULL DEFAULT 'other',  -- identity/preference/goal/skill/relationship/event/other
    keywords TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'auto',
    decay_weight REAL NOT NULL DEFAULT 1.0,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    last_accessed INTEGER NOT NULL,
    access_count INTEGER NOT NULL DEFAULT 0,
    conversation_id TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_memory_items_user_layer ON memory_items(user_id, layer);
CREATE INDEX IF NOT EXISTS idx_memory_items_importance ON memory_items(user_id, importance);
CREATE INDEX IF NOT EXISTS idx_memory_items_keywords ON memory_items(user_id, keywords);

CREATE TABLE IF NOT EXISTS reflections (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    trigger TEXT NOT NULL DEFAULT 'periodic',  -- periodic/threshold/manual
    summary TEXT NOT NULL,
    insights TEXT NOT NULL DEFAULT '',
    profile_updates TEXT NOT NULL DEFAULT '{}',
    new_memories TEXT NOT NULL DEFAULT '[]',
    created_at INTEGER NOT NULL,
    message_count_at_trigger INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_reflections_user ON reflections(user_id, created_at);

CREATE TABLE IF NOT EXISTS conversation_goals (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    conversation_id TEXT NOT NULL,
    goal TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',  -- active/completed/abandoned
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_goals_conv ON conversation_goals(conversation_id);

CREATE TABLE IF NOT EXISTS tool_memory (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    tool_name TEXT NOT NULL,
    context TEXT NOT NULL DEFAULT '',  -- when this tool was used
    use_count INTEGER NOT NULL DEFAULT 0,
    last_used INTEGER NOT NULL,
    success_count INTEGER NOT NULL DEFAULT 0,
    UNIQUE(user_id, tool_name, context)
);
CREATE INDEX IF NOT EXISTS idx_tool_memory_user ON tool_memory(user_id, tool_name);

CREATE TABLE IF NOT EXISTS world_state (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    project TEXT NOT NULL,
    component TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'unknown',  -- todo/in_progress/completed/blocked
    notes TEXT NOT NULL DEFAULT '',
    updated_at INTEGER NOT NULL,
    UNIQUE(user_id, project, component)
);
CREATE INDEX IF NOT EXISTS idx_world_state_user ON world_state(user_id, project);
"""


def init_orchestrator_db(db_path: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = safe_connect(db_path)
    conn.executescript(ORCHESTRATOR_SCHEMA)
    conn.commit()
    conn.close()


# ============================================================
# Keyword extraction (shared)
# ============================================================

_STOPWORDS = set("""
的 了 在 是 我 有 和 就 不 人 都 一 一个 上 也 很 到 说 要 去 你 会 着 没有 看 好 自己 这 那
the a an and or but in on at to for of is are was were be been being have has had
i you he she it we they me him her us them my your his its our their
""".split())

_ALNUM_RE = re.compile(r"[a-zA-Z0-9]+")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def _extract_keywords(text: str, top_k: int = 15) -> List[str]:
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
    return [kw for kw, _ in Counter(kws).most_common(top_k)]


def _keyword_score(query_kws: List[str], mem_kws: List[str]) -> float:
    if not query_kws or not mem_kws:
        return 0.0
    mset = set(mem_kws)
    inter = set(query_kws) & mset
    if not inter:
        return 0.0
    score = 0.0
    for i, kw in enumerate(query_kws):
        if kw in mset:
            score += 1.0 / (i + 1)
    return score / max(len(query_kws), 1)


# ============================================================
# Memory CRUD
# ============================================================

def _layer_for_importance(importance: int) -> str:
    if importance >= 81:
        return "permanent"
    if importance >= 51:
        return "long_term"
    if importance >= 21:
        return "short_term"
    return "working"  # will be discarded


def add_memory(db_path: Path, *, user_id: str = "default", content: str,
               importance: int = 30, category: str = "other",
               source: str = "auto", conversation_id: Optional[str] = None,
               metadata: Optional[Dict] = None) -> Dict:
    """Add a memory item. Importance determines its layer.
    Includes semantic deduplication (Jaccard similarity on keywords)."""
    content = content.strip()
    if not content:
        return {"action": "noop", "reason": "empty"}
    layer = _layer_for_importance(importance)
    if layer == "working":
        return {"action": "discard", "reason": "importance too low"}
    kws = _extract_keywords(content)
    mid = hashlib.sha1(f"{user_id}:{content[:100]}:{time.time_ns()}".encode()).hexdigest()[:16]
    now = int(time.time())
    meta = json.dumps(metadata or {}, ensure_ascii=False)
    conn = safe_connect(db_path)
    try:
        # 1. Check for exact duplicates
        existing = conn.execute(
            "SELECT id, keywords, importance, layer FROM memory_items WHERE user_id=? AND content=?",
            (user_id, content)
        ).fetchone()
        if existing:
            new_imp = max(existing[2], importance)
            new_layer = _layer_for_importance(new_imp)
            conn.execute(
                "UPDATE memory_items SET importance=?, layer=?, updated_at=?, last_accessed=?, "
                "decay_weight=MAX(decay_weight, 1.0) WHERE id=?",
                (new_imp, new_layer, now, now, existing[0])
            )
            return {"action": "update", "id": existing[0], "layer": new_layer}
        # 2. Semantic dedup (Jaccard similarity on keywords) — Mem0 style
        new_kw_set = set(kws)
        if new_kw_set:
            candidates = conn.execute(
                "SELECT id, content, keywords, importance FROM memory_items "
                "WHERE user_id=? AND layer IN ('long_term', 'permanent') "
                "ORDER BY importance DESC LIMIT 100",
                (user_id,)
            ).fetchall()
            for c in candidates:
                existing_kws = set(c[2].split(",")) if c[2] else set()
                if not existing_kws:
                    continue
                intersection = len(new_kw_set & existing_kws)
                union = len(new_kw_set | existing_kws)
                jaccard = intersection / max(union, 1)
                if jaccard >= 0.7:
                    # Merge: bump importance, refresh
                    new_imp = min(100, max(c[3], importance) + 5)
                    new_layer = _layer_for_importance(new_imp)
                    conn.execute(
                        "UPDATE memory_items SET importance=?, layer=?, updated_at=?, last_accessed=?, "
                        "decay_weight=1.0, access_count=access_count+1 WHERE id=?",
                        (new_imp, new_layer, now, now, c[0])
                    )
                    return {"action": "merged", "id": c[0], "layer": new_layer,
                            "importance": new_imp, "jaccard": round(jaccard, 3)}
        # 3. Add new
        conn.execute(
            "INSERT INTO memory_items (id, user_id, content, layer, importance, category, keywords, "
            "source, decay_weight, created_at, updated_at, last_accessed, conversation_id, metadata_json) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (mid, user_id, content, layer, importance, category, ",".join(kws),
             source, 1.0, now, now, now, conversation_id, meta)
        )
        result = {"action": "add", "id": mid, "layer": layer, "importance": importance}
        # Sync to vector store (ChromaDB or TF-IDF)
        try:
            from app.vector_store import get_vector_store
            vs = get_vector_store(db_path)
            vs.add(f"memories_{user_id}", id=mid, text=content,
                   metadata={"importance": importance, "layer": layer, "category": category})
        except Exception as e:
            print(f"[memory] vector store sync failed: {e}")
        # Low-confidence memories go to governance quarantine for validation
        # High-confidence memories go directly to main store (already done above)
        # This is the SSGM Framework: Quarantine → Validate → Promote
        if importance < 50 and source == "auto":
            try:
                from app import memory_governance
                memory_governance.quarantine(
                    db_path,
                    user_id=user_id,
                    content=content,
                    source=source,
                    importance=importance,
                    category=category,
                )
            except Exception as e:
                print(f"[memory] governance quarantine failed: {e}")
        # Publish event for event bus subscribers
        try:
            import asyncio
            from app import event_bus
            event_data = {"memory_id": mid, "user_id": user_id, "content": content[:200],
                          "importance": importance, "layer": layer, "category": category}
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(event_bus.publish("memory.added", event_data))
                else:
                    loop.run_until_complete(event_bus.publish("memory.added", event_data))
            except RuntimeError:
                pass  # no event loop
        except Exception:
            pass
        return result
    finally:
        conn.commit()
        conn.close()


def list_memories(db_path: Path, *, user_id: str = "default",
                  layer: Optional[str] = None, category: Optional[str] = None,
                  limit: int = 100, min_importance: int = 0) -> List[Dict]:
    """List memories, optionally filtered by layer/category."""
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    sql = "SELECT * FROM memory_items WHERE user_id=? AND importance>=?"
    params = [user_id, min_importance]
    if layer:
        sql += " AND layer=?"
        params.append(layer)
    if category:
        sql += " AND category=?"
        params.append(category)
    sql += " ORDER BY importance DESC, updated_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_memory(db_path: Path, memory_id: str) -> bool:
    conn = safe_connect(db_path)
    cur = conn.execute("DELETE FROM memory_items WHERE id=?", (memory_id,))
    conn.commit()
    conn.close()
    return cur.rowcount > 0


def promote_memory(db_path: Path, memory_id: str, new_importance: int) -> bool:
    """Promote/demote a memory by changing its importance (and thus layer)."""
    new_layer = _layer_for_importance(new_importance)
    now = int(time.time())
    conn = safe_connect(db_path)
    cur = conn.execute(
        "UPDATE memory_items SET importance=?, layer=?, updated_at=?, last_accessed=? WHERE id=?",
        (new_importance, new_layer, now, now, memory_id)
    )
    conn.commit()
    conn.close()
    return cur.rowcount > 0


# ============================================================
# Decay (forgetting)
# ============================================================

def apply_decay(db_path: Path, *, user_id: str = "default",
                days_elapsed: float = 1.0) -> Dict:
    """Apply time-based decay to all memories. Called periodically.
    - permanent layer: no decay
    - long_term: slow decay (0.99/day)
    - short_term: faster decay (0.95/day)
    - working: fastest (auto-deleted after 1 day unused)
    Memories with high importance decay slower.
    Returns stats about what was decayed/deleted."""
    now = int(time.time())
    conn = safe_connect(db_path)
    rows = conn.execute(
        "SELECT id, layer, importance, decay_weight, last_accessed FROM memory_items WHERE user_id=?",
        (user_id,)
    ).fetchall()
    decayed = 0
    deleted = 0
    for row in rows:
        mid, layer, imp, weight, last_acc = row
        if layer == "permanent":
            continue
        age_days = (now - last_acc) / 86400
        if age_days < days_elapsed:
            continue
        # Layer-specific decay rate
        if layer == "long_term":
            base_rate = 0.99
        elif layer == "short_term":
            base_rate = 0.95
        else:  # working
            base_rate = 0.80
        # Importance protects: importance 100 → factor 0.5 (half decay rate)
        imp_factor = 1.0 - (imp / 100.0) * 0.5
        effective_decay = base_rate ** (age_days * imp_factor)
        new_weight = weight * effective_decay
        if new_weight < 0.15 and layer != "long_term":
            # Delete forgotten memories (but preserve long_term even if low weight)
            conn.execute("DELETE FROM memory_items WHERE id=?", (mid,))
            deleted += 1
        elif abs(new_weight - weight) > 0.001:
            conn.execute("UPDATE memory_items SET decay_weight=? WHERE id=?", (new_weight, mid))
            decayed += 1
    conn.commit()
    conn.close()
    return {"decayed": decayed, "deleted": deleted}


# ============================================================
# Multi-modal retrieval
# ============================================================

def retrieve_relevant(db_path: Path, query: str, *, user_id: str = "default",
                      top_k: int = 8) -> List[Dict]:
    """Retrieve relevant memories using multi-modal fusion:
    vector search (ChromaDB or TF-IDF) + keyword + importance + recency + decay.
    Returns top-k memories sorted by fused score."""
    qkws = _extract_keywords(query, top_k=15)
    if not qkws:
        # Fallback: return most important recent memories
        return list_memories(db_path, user_id=user_id, limit=top_k, min_importance=40)
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    # Get all non-working memories
    rows = conn.execute(
        "SELECT * FROM memory_items WHERE user_id=? AND layer!='working' ORDER BY importance DESC, updated_at DESC LIMIT 300",
        (user_id,)
    ).fetchall()
    conn.close()
    if not rows:
        return []

    # Vector search for semantic similarity (ChromaDB or TF-IDF)
    vector_scores: Dict[str, float] = {}
    try:
        from app.vector_store import get_vector_store
        vs = get_vector_store(db_path)
        # Ensure memories are indexed (lazy index if not yet)
        collection = f"memories_{user_id}"
        if vs.count(collection) == 0:
            # Lazy index all existing memories
            for row in rows:
                d = dict(row)
                try:
                    vs.add(collection, id=d["id"], text=d["content"],
                           metadata={"importance": d["importance"], "layer": d["layer"]})
                except Exception:
                    pass
        # Query
        results = vs.query(collection, text=query, top_k=min(top_k * 3, 30))
        for r in results:
            vector_scores[r["id"]] = r.get("score", 0)
    except Exception as e:
        print(f"[memory] vector search failed: {e}")

    now = int(time.time())

    # Load adaptive weights (EvolveMem — weights self-adjust based on feedback)
    weights = {
        "vector": 0.40, "keyword": 0.20, "importance": 0.20,
        "recency": 0.10, "decay": 0.05, "layer": 0.05,
    }
    try:
        from app import adaptive_retrieval
        adaptive_w = adaptive_retrieval.get_weights(db_path, user_id)
        # Map adaptive weights (keyword/importance/recency/decay/layer) onto our fused score
        # adaptive_w has: keyword, importance, recency, decay, layer
        # We add vector on top
        if adaptive_w:
            total_existing = sum(adaptive_w.values())
            if total_existing > 0:
                # Scale adaptive weights to fit alongside vector (vector keeps 0.40)
                scale = 0.60 / total_existing  # remaining 60% for the 5 adaptive factors
                weights = {
                    "vector": 0.40,
                    "keyword": adaptive_w.get("keyword", 0.35) * scale,
                    "importance": adaptive_w.get("importance", 0.25) * scale,
                    "recency": adaptive_w.get("recency", 0.15) * scale,
                    "decay": adaptive_w.get("decay", 0.15) * scale,
                    "layer": adaptive_w.get("layer", 0.10) * scale,
                }
    except Exception as e:
        print(f"[memory] adaptive weights load failed: {e}")

    scored = []
    for row in rows:
        d = dict(row)
        mkws = d["keywords"].split(",") if d["keywords"] else []
        # 1. Vector similarity (semantic, ChromaDB or TF-IDF)
        vec_score = vector_scores.get(d["id"], 0)
        # 2. Keyword overlap (fallback/proxy)
        kw_score = _keyword_score(qkws, mkws)
        # 3. Importance bonus (0-1)
        imp_score = d["importance"] / 100.0
        # 4. Recency bonus (exponential decay over 30 days)
        age_days = (now - d["updated_at"]) / 86400
        recency_score = math.exp(-age_days / 30.0)
        # 5. Decay weight (forgetting)
        decay = d.get("decay_weight", 1.0)
        # 6. Layer boost (permanent > long_term > short_term)
        layer_boost = {"permanent": 1.5, "long_term": 1.2, "short_term": 1.0}.get(d["layer"], 1.0)
        # Fused score — uses adaptive weights
        fused = (
            vec_score * weights["vector"] +
            kw_score * weights["keyword"] +
            imp_score * weights["importance"] +
            recency_score * weights["recency"] +
            decay * weights["decay"] +
            (layer_boost - 1.0) * weights["layer"]
        )
        if fused > 0.03:
            scored.append((fused, d))
    scored.sort(key=lambda x: -x[0])
    # Update access stats for retrieved memories
    retrieved_ids = [d["id"] for _, d in scored[:top_k]]
    if retrieved_ids:
        conn = safe_connect(db_path)
        for mid in retrieved_ids:
            conn.execute(
                "UPDATE memory_items SET last_accessed=?, access_count=access_count+1 WHERE id=?",
                (now, mid)
            )
        conn.commit()
        conn.close()
    return [d for _, d in scored[:top_k]]


# ============================================================
# Context Builder — the brain
# ============================================================

def build_context(db_path: Path, *, user_id: str = "default",
                  query: str, conversation_id: Optional[str] = None,
                  emotion_state: Optional[Dict] = None,
                  user_profile: Optional[Dict] = None,
                  max_chars: int = 4000) -> Dict:
    """Build an optimized context section for the LLM.

    Combines (in priority order):
    1. Permanent memories (always included, truncated)
    2. Current conversation goal (if any)
    3. Retrieved long/short-term memories (relevance-ranked)
    4. Relevant knowledge graph triples
    5. Relevant episodic memories
    6. User profile summary
    7. Current emotional state
    8. Recent reflections

    Returns {sections: {section_name: text}, total_chars, parts: [str]}
    """
    sections = {}
    parts = []
    total = 0

    # 1. Permanent memories (identity, core preferences) — always included
    permanent = list_memories(db_path, user_id=user_id, layer="permanent", limit=20)
    if permanent:
        text = "\n".join(f"- {m['content']}" for m in permanent)
        sections["permanent"] = f"【核心记忆（永久）】\n{text}"
        parts.append(sections["permanent"])
        total += len(text)

    # 2. Current conversation goal
    if conversation_id:
        goal = get_active_goal(db_path, conversation_id)
        if goal:
            sections["goal"] = f"【当前对话目标】{goal['goal']}"
            parts.append(sections["goal"])
            total += len(goal["goal"])

    # 3. Retrieved relevant memories (multi-modal)
    remaining = max_chars - total - 1000  # reserve space for other sections
    if remaining > 200 and query:
        retrieved = retrieve_relevant(db_path, query, user_id=user_id, top_k=10)
        if retrieved:
            items = []
            for m in retrieved:
                layer_tag = {"permanent": "永久", "long_term": "长期", "short_term": "短期"}.get(m["layer"], "")
                items.append(f"- [{layer_tag}|重要度{m['importance']}] {m['content']}")
                if total + sum(len(i) for i in items) > max_chars * 0.6:
                    break
            text = "\n".join(items[:8])
            sections["retrieved"] = f"【相关记忆】（按相关性+重要度+时间融合排序）\n{text}"
            parts.append(sections["retrieved"])
            total += len(text)

    # 4. User profile (if provided externally)
    if user_profile and user_profile.get("auto_summary"):
        text = user_profile["auto_summary"]
        if len(text) > 300:
            text = text[:300] + "..."
        sections["profile"] = f"【用户画像】{text}"
        parts.append(sections["profile"])
        total += len(text)

    # 5. Emotional state (if provided)
    if emotion_state and emotion_state.get("current_emotion") != "neutral":
        emotion_zh = {"joy": "愉悦", "excitement": "兴奋", "anxiety": "焦虑",
                     "sadness": "低落", "anger": "愤怒", "frustration": "挫败",
                     "sarcasm": "讽刺", "gratitude": "感激", "curiosity": "好奇"}
        cur = emotion_zh.get(emotion_state["current_emotion"], emotion_state["current_emotion"])
        intensity = int(emotion_state.get("emotion_intensity", 0) * 100)
        sections["emotion"] = f"【用户当前情绪】{cur}（强度 {intensity}%）"
        parts.append(sections["emotion"])
        total += len(sections["emotion"])

    # 6. Recent reflection (if any)
    recent_reflection = get_latest_reflection(db_path, user_id=user_id)
    if recent_reflection and recent_reflection.get("summary"):
        text = recent_reflection["summary"]
        if len(text) > 400:
            text = text[:400] + "..."
        sections["reflection"] = f"【最近反思】{text}"
        parts.append(sections["reflection"])
        total += len(text)

    return {
        "sections": sections,
        "parts": parts,
        "total_chars": total,
        "combined": "\n\n".join(parts) if parts else "",
    }


# ============================================================
# Conversation goals
# ============================================================

def set_goal(db_path: Path, *, user_id: str = "default", conversation_id: str,
             goal: str) -> Dict:
    gid = hashlib.sha1(f"{user_id}:{conversation_id}:{goal}".encode()).hexdigest()[:16]
    now = int(time.time())
    conn = safe_connect(db_path)
    # Deactivate old active goals for this conversation
    conn.execute(
        "UPDATE conversation_goals SET status='abandoned', updated_at=? WHERE conversation_id=? AND status='active'",
        (now, conversation_id)
    )
    conn.execute(
        "INSERT OR REPLACE INTO conversation_goals (id, user_id, conversation_id, goal, status, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (gid, user_id, conversation_id, goal, "active", now, now)
    )
    conn.commit()
    conn.close()
    return {"id": gid, "goal": goal, "status": "active"}


def get_active_goal(db_path: Path, conversation_id: str) -> Optional[Dict]:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM conversation_goals WHERE conversation_id=? AND status='active' ORDER BY updated_at DESC LIMIT 1",
        (conversation_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def complete_goal(db_path: Path, conversation_id: str) -> bool:
    now = int(time.time())
    conn = safe_connect(db_path)
    cur = conn.execute(
        "UPDATE conversation_goals SET status='completed', updated_at=? WHERE conversation_id=? AND status='active'",
        (now, conversation_id)
    )
    conn.commit()
    conn.close()
    return cur.rowcount > 0


# ============================================================
# Tool memory — track which tools the user frequently uses
# ============================================================

def record_tool_use(db_path: Path, *, user_id: str = "default",
                    tool_name: str, context: str = "", success: bool = True) -> Dict:
    """Record that a tool was used. Used for tool memory (auto-suggest tools)."""
    tid = hashlib.sha1(f"{user_id}:{tool_name}:{context}".encode()).hexdigest()[:16]
    now = int(time.time())
    conn = safe_connect(db_path)
    try:
        cur = conn.execute(
            "SELECT id, use_count, success_count FROM tool_memory WHERE user_id=? AND tool_name=? AND context=?",
            (user_id, tool_name, context)
        ).fetchone()
        if cur:
            new_use = cur[1] + 1
            new_success = cur[2] + (1 if success else 0)
            conn.execute(
                "UPDATE tool_memory SET use_count=?, success_count=?, last_used=? WHERE id=?",
                (new_use, new_success, now, cur[0])
            )
        else:
            conn.execute(
                "INSERT INTO tool_memory (id, user_id, tool_name, context, use_count, last_used, success_count) "
                "VALUES (?,?,?,?,?,?,?)",
                (tid, user_id, tool_name, context, 1, now, 1 if success else 0)
            )
        conn.commit()
    finally:
        conn.close()
    return {"tool": tool_name, "context": context, "success": success}


def get_frequent_tools(db_path: Path, *, user_id: str = "default",
                       top_k: int = 5) -> List[Dict]:
    """Get the most frequently used tools for a user."""
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT tool_name, context, use_count, success_count, last_used "
        "FROM tool_memory WHERE user_id=? ORDER BY use_count DESC LIMIT ?",
        (user_id, top_k)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ============================================================
# World state — track user's projects and their components
# ============================================================

def update_world_state(db_path: Path, *, user_id: str = "default",
                       project: str, component: str = "",
                       status: str = "unknown", notes: str = "") -> bool:
    """Update the status of a project component."""
    wid = hashlib.sha1(f"{user_id}:{project}:{component}".encode()).hexdigest()[:16]
    now = int(time.time())
    conn = safe_connect(db_path)
    conn.execute(
        "INSERT INTO world_state (id, user_id, project, component, status, notes, updated_at) "
        "VALUES (?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET status=excluded.status, notes=excluded.notes, updated_at=excluded.updated_at",
        (wid, user_id, project, component, status, notes, now)
    )
    conn.commit()
    conn.close()
    return True


def get_world_state(db_path: Path, *, user_id: str = "default",
                    project: Optional[str] = None) -> List[Dict]:
    """Get world state for a user, optionally filtered by project."""
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    if project:
        rows = conn.execute(
            "SELECT * FROM world_state WHERE user_id=? AND project=? ORDER BY component",
            (user_id, project)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM world_state WHERE user_id=? ORDER BY project, component",
            (user_id,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ============================================================
# Reflections
# ============================================================

def save_reflection(db_path: Path, *, user_id: str = "default",
                    trigger: str = "periodic", summary: str,
                    insights: str = "", profile_updates: Optional[Dict] = None,
                    new_memories: Optional[List[Dict]] = None,
                    message_count: int = 0) -> Dict:
    rid = hashlib.sha1(f"{user_id}:{trigger}:{time.time()}".encode()).hexdigest()[:16]
    now = int(time.time())
    conn = safe_connect(db_path)
    conn.execute(
        "INSERT INTO reflections (id, user_id, trigger, summary, insights, profile_updates, new_memories, created_at, message_count_at_trigger) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (rid, user_id, trigger, summary, insights,
         json.dumps(profile_updates or {}, ensure_ascii=False),
         json.dumps(new_memories or [], ensure_ascii=False),
         now, message_count)
    )
    conn.commit()
    conn.close()
    return {"id": rid, "summary": summary}


def get_latest_reflection(db_path: Path, *, user_id: str = "default") -> Optional[Dict]:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM reflections WHERE user_id=? ORDER BY created_at DESC LIMIT 1",
        (user_id,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    try:
        d["profile_updates"] = json.loads(d.get("profile_updates", "{}"))
        d["new_memories"] = json.loads(d.get("new_memories", "[]"))
    except Exception:
        pass
    return d


def list_reflections(db_path: Path, *, user_id: str = "default",
                     limit: int = 20) -> List[Dict]:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM reflections WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit)
    ).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["profile_updates"] = json.loads(d.get("profile_updates", "{}"))
            d["new_memories"] = json.loads(d.get("new_memories", "[]"))
        except Exception:
            pass
        out.append(d)
    return out


# ============================================================
# Importance classification (LLM-driven)
# ============================================================

CLASSIFY_IMPORTANCE_PROMPT_DEFAULT = """你是一个记忆重要度评估器。评估下面这条记忆对用户的长期价值。

【记忆内容】
{content}

【对话上下文】
{context}

【评分标准（0-100）】
- 0-20: 临时信息（今天吃了什么、当前时间、寒暄），不值得记住
- 21-50: 短期有用（最近在忙的事、临时偏好），记 1-7 天
- 51-80: 长期价值（持久偏好、技能、项目信息、人际关系），长期保留
- 81-100: 永久核心（身份信息：名字/职业/学校、核心价值观、人生事件），永不遗忘

【类别】
- identity: 身份（名字/职业/学校/年龄/所在地）
- preference: 偏好（喜欢/讨厌什么）
- goal: 目标/计划/项目
- skill: 技能/经验
- relationship: 人际关系
- event: 事件
- other: 其他

输出 JSON：
```json
{{"importance": 85, "category": "identity", "reason": "用户的永久身份信息"}}
```

只输出 JSON，不要其他文字。"""


async def classify_importance_via_llm(content: str, context: str,
                                       http_client, api_cfg: Dict) -> Optional[Dict]:
    """Ask the LLM to classify the importance of a memory."""
    try:
        payload = {
            "model": api_cfg["api_model"],
            "messages": [{"role": "user", "content": _get_prompt("prompt_classify_importance", CLASSIFY_IMPORTANCE_PROMPT_DEFAULT).format(
                content=content[:500], context=context[:1000]
            )}],
            "temperature": 0.1,
            "max_tokens": 200,
            "stream": False,
            "enable_thinking": False,
        }
        resp = await http_client.post(
            f"{api_cfg['api_base_url']}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {api_cfg['api_key']}", "Content-Type": "application/json"},
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()
        text = _extract_content(data)
        m = re.search(r"\{[^{}]*\}", text, re.DOTALL)
        if not m:
            return None
        try:
            result = json.loads(m.group(0))
            if isinstance(result, dict) and "importance" in result:
                return result
        except json.JSONDecodeError:
            pass
        return None
    except Exception as e:
        print(f"[orchestrator] classify failed: {e}")
        return None


# ============================================================
# Background reflection (periodic deep summary)
# ============================================================

REFLECTION_PROMPT = """你是 CyanX AI 的反思系统。基于最近的对话和已有记忆，进行深度反思。

【已有用户画像】
{profile}

【最近对话（{msg_count} 条）】
{recent_conversation}

【已有长期记忆（前 20 条）】
{existing_memories}

【任务】
进行整体性反思（不是逐条分析），输出：

1. summary: 一段话总结最近的对话模式和、用户状态变化、值得注意的信号
2. insights: 2-3 条洞察（如"用户最近对系统设计类游戏的兴趣明显上升"、"用户开始关注性能优化"）
3. profile_updates: 用户画像字段的更新（JSON 对象，只包含需要更新的字段）
4. new_memories: 应该新增到长期/永久记忆的关键事实（数组，每项 {{content, importance, category}}）

规则：
- 反思是整体理解，不是逐条总结
- 识别趋势和变化，不要重复已有记忆
- new_memories 只包含真正重要的持久事实，不要包含临时对话内容
- importance 用 0-100，遵循分层规则（81+=永久，51-80=长期，21-50=短期）

输出 JSON：
```json
{{
  "summary": "最近用户...",
  "insights": ["洞察1", "洞察2"],
  "profile_updates": {{"interests": "更新的兴趣", "emotional_patterns": "..."}},
  "new_memories": [
    {{"content": "用户...", "importance": 85, "category": "identity"}}
  ]
}}
```"""


async def run_reflection(db_path: Path, *, user_id: str = "default",
                          recent_conversation: str, message_count: int,
                          http_client, api_cfg: Dict) -> Dict:
    """Run a background reflection: summarize recent conversation, update profile,
    extract new long-term memories. Saves result to reflections table."""
    try:
        # Get existing profile + memories
        from app.advanced_memory import get_user_profile
        from app.main import memory_list
        profile = get_user_profile(db_path, user_id)
        profile_summary = "\n".join(
            f"- {k}: {profile[k]}" for k in
            ["personality", "interests", "preferences", "emotional_patterns", "auto_summary"]
            if profile.get(k)
        ) or "(空)"
        existing = list_memories(db_path, user_id=user_id, limit=20, min_importance=50)
        existing_text = "\n".join(f"- [{m['layer']}] {m['content']}" for m in existing) or "(空)"

        payload = {
            "model": api_cfg["api_model"],
            "messages": [{"role": "user", "content": REFLECTION_PROMPT.format(
                profile=profile_summary,
                msg_count=message_count,
                recent_conversation=recent_conversation[:4000],
                existing_memories=existing_text,
            )}],
            "temperature": 0.4,
            "max_tokens": 1500,
            "stream": False,
            "enable_thinking": False,
        }
        resp = await http_client.post(
            f"{api_cfg['api_base_url']}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {api_cfg['api_key']}", "Content-Type": "application/json"},
            timeout=60.0,
        )
        resp.raise_for_status()
        data = resp.json()
        text = _extract_content(data)
        # Extract JSON
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            return {"success": False, "error": "no JSON in response"}
        try:
            result = json.loads(m.group(0))
        except json.JSONDecodeError as e:
            return {"success": False, "error": f"invalid JSON: {e}"}

        # Save reflection — safely handle non-standard LLM responses
        try:
            reflection = save_reflection(
                db_path, user_id=user_id, trigger="periodic",
                summary=str(result.get("summary", "")),
                insights="\n".join(str(i) for i in (result.get("insights", []) if isinstance(result.get("insights"), list) else [])),
                profile_updates=result.get("profile_updates", {}) if isinstance(result.get("profile_updates"), dict) else {},
                new_memories=result.get("new_memories", []) if isinstance(result.get("new_memories"), list) else [],
                message_count=message_count,
            )
        except Exception as e:
            print(f"[reflection] save failed: {e}")
            reflection = {"id": "error", "summary": str(result.get("summary", ""))}

        # Apply profile updates — safely
        if result.get("profile_updates"):
            try:
                from app.advanced_memory import update_user_profile
                pu = result["profile_updates"]
                if isinstance(pu, dict):
                    # Convert all values to strings (DB expects TEXT)
                    safe_pu = {}
                    for k, v in pu.items():
                        if v is None or v == "":
                            continue
                        if isinstance(v, (list, dict)):
                            safe_pu[k] = json.dumps(v, ensure_ascii=False)
                        else:
                            safe_pu[k] = str(v)
                    if safe_pu:
                        update_user_profile(db_path, user_id, **safe_pu)
            except Exception as e:
                print(f"[reflection] profile update failed: {e}")

        # Add new memories — safely handle any format
        added = []
        new_mems = result.get("new_memories", [])
        if not isinstance(new_mems, list):
            new_mems = []
        for nm in new_mems:
            try:
                if isinstance(nm, dict) and nm.get("content"):
                    r = add_memory(
                        db_path, user_id=user_id,
                        content=str(nm["content"]),
                        importance=int(nm.get("importance", 50) or 50),
                        category=str(nm.get("category", "other") or "other"),
                        source="reflection",
                    )
                    if r.get("action") in ("add", "update"):
                        added.append(r)
                elif isinstance(nm, str) and len(nm) > 5:
                    r = add_memory(db_path, user_id=user_id, content=nm, importance=50, category="other", source="reflection")
                    if r.get("action") in ("add", "update"):
                        added.append(r)
            except Exception as e:
                print(f"[reflection] memory add failed: {e}")

        return {
            "success": True,
            "reflection_id": reflection["id"],
            "summary": result.get("summary", ""),
            "insights": result.get("insights", []),
            "profile_updates": result.get("profile_updates", {}),
            "new_memories_added": len(added),
        }
    except Exception as e:
        print(f"[reflection] failed: {e}")
        return {"success": False, "error": str(e)}


# ============================================================
# Stats / dashboard
# ============================================================

def get_dashboard_stats(db_path: Path, *, user_id: str = "default") -> Dict:
    """Get comprehensive stats for the Memory Dashboard."""
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    # Memory by layer
    by_layer = {}
    for r in conn.execute(
        "SELECT layer, COUNT(*) AS c, AVG(importance) AS avg_imp FROM memory_items WHERE user_id=? GROUP BY layer",
        (user_id,)
    ).fetchall():
        by_layer[r["layer"]] = {"count": r["c"], "avg_importance": round(r["avg_imp"] or 0, 1)}
    # Memory by category
    by_category = {}
    for r in conn.execute(
        "SELECT category, COUNT(*) AS c FROM memory_items WHERE user_id=? GROUP BY category",
        (user_id,)
    ).fetchall():
        by_category[r["category"]] = r["c"]
    # Total
    total = conn.execute("SELECT COUNT(*) FROM memory_items WHERE user_id=?", (user_id,)).fetchone()[0]
    # Reflections
    reflections_count = conn.execute("SELECT COUNT(*) FROM reflections WHERE user_id=?", (user_id,)).fetchone()[0]
    # Goals
    active_goals = conn.execute(
        "SELECT COUNT(*) FROM conversation_goals WHERE user_id=? AND status='active'",
        (user_id,)
    ).fetchone()[0]
    # Tool memory
    tool_count = conn.execute("SELECT COUNT(*) FROM tool_memory WHERE user_id=?", (user_id,)).fetchone()[0]
    # World state
    ws_count = conn.execute("SELECT COUNT(*) FROM world_state WHERE user_id=?", (user_id,)).fetchone()[0]
    conn.close()
    return {
        "total_memories": total,
        "by_layer": by_layer,
        "by_category": by_category,
        "reflections_count": reflections_count,
        "active_goals": active_goals,
        "tool_memory_count": tool_count,
        "world_state_count": ws_count,
    }
