from __future__ import annotations
from app.db_utils import safe_connect
"""
Knowledge Graph subsystem for CyanX AI.

Stores entity-relationship-entity triples extracted from conversation.
Enables graph-based retrieval: "用户喜欢什么创造游戏？" → traverse graph
instead of embedding search.

Schema:
- entities: id, name, type, weight, created_at, last_accessed, access_count
- relations: id, subject_id, predicate, object_id, weight, created_at, source

Triples look like: (zjq, likes, Minecraft), (Minecraft, is_a, sandbox_game)

Extraction is LLM-driven: a background task (or inline call) asks the LLM to
extract triples from recent conversation. Triples are merged by name (case-
insensitive), and weights increase with repeated mentions.

This module is self-contained. main.py wires it up to the Context Builder and
exposes /api/kg/* endpoints.
"""
import json
import re
import sqlite3
import time
import hashlib
from typing import List, Dict, Optional, Set, Tuple
from pathlib import Path


KG_SCHEMA = """
CREATE TABLE IF NOT EXISTS kg_entities (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    name TEXT NOT NULL,
    name_lower TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'thing',
    weight REAL NOT NULL DEFAULT 1.0,
    created_at INTEGER NOT NULL,
    last_accessed INTEGER NOT NULL,
    access_count INTEGER NOT NULL DEFAULT 0,
    UNIQUE(user_id, name_lower)
);
CREATE INDEX IF NOT EXISTS idx_kg_entities_user ON kg_entities(user_id, name_lower);

CREATE TABLE IF NOT EXISTS kg_relations (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    subject_id TEXT NOT NULL,
    predicate TEXT NOT NULL,
    object_id TEXT NOT NULL,
    weight REAL NOT NULL DEFAULT 1.0,
    source TEXT NOT NULL DEFAULT 'auto',
    created_at INTEGER NOT NULL,
    last_accessed INTEGER NOT NULL,
    access_count INTEGER NOT NULL DEFAULT 0,
    UNIQUE(user_id, subject_id, predicate, object_id)
);
CREATE INDEX IF NOT EXISTS idx_kg_rel_subject ON kg_relations(user_id, subject_id);
CREATE INDEX IF NOT EXISTS idx_kg_rel_object ON kg_relations(user_id, object_id);
CREATE INDEX IF NOT EXISTS idx_kg_rel_predicate ON kg_relations(user_id, predicate);
"""


def init_kg_db(db_path: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = safe_connect(db_path)
    conn.executescript(KG_SCHEMA)
    conn.commit()
    conn.close()


def _entity_id(user_id: str, name: str) -> str:
    return hashlib.sha1(f"{user_id}:{name.lower()}".encode()).hexdigest()[:16]


def _relation_id(user_id: str, subj_id: str, pred: str, obj_id: str) -> str:
    return hashlib.sha1(f"{user_id}:{subj_id}:{pred}:{obj_id}".encode()).hexdigest()[:16]


def upsert_entity(db_path: Path, *, user_id: str = "default", name: str,
                  entity_type: str = "thing", weight_boost: float = 0.0) -> str:
    """Insert or update an entity. Returns entity id."""
    name = name.strip()
    if not name:
        return ""
    name_lower = name.lower()
    eid = _entity_id(user_id, name)
    now = int(time.time())
    conn = safe_connect(db_path)
    try:
        cur = conn.execute(
            "SELECT id, weight FROM kg_entities WHERE user_id=? AND name_lower=?",
            (user_id, name_lower)
        ).fetchone()
        if cur:
            new_weight = cur[1] + 0.3 + weight_boost
            conn.execute(
                "UPDATE kg_entities SET weight=?, last_accessed=? WHERE id=?",
                (new_weight, now, cur[0])
            )
            eid = cur[0]
        else:
            conn.execute(
                "INSERT INTO kg_entities (id, user_id, name, name_lower, type, weight, created_at, last_accessed) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (eid, user_id, name, name_lower, entity_type, 1.0 + weight_boost, now, now)
            )
        conn.commit()
    finally:
        conn.close()
    return eid


def upsert_relation(db_path: Path, *, user_id: str = "default",
                    subject: str, predicate: str, obj: str,
                    source: str = "auto") -> Optional[str]:
    """Insert or update a triple. Subject and object are entity names (will be upserted).
    predicate is a short relation like 'likes', 'is_a', 'uses', 'works_at'."""
    subject = subject.strip()
    obj = obj.strip()
    predicate = predicate.strip().lower().replace(" ", "_")
    if not subject or not obj or not predicate:
        return None
    subj_id = upsert_entity(db_path, user_id=user_id, name=subject)
    obj_id = upsert_entity(db_path, user_id=user_id, name=obj)
    if not subj_id or not obj_id:
        return None
    rid = _relation_id(user_id, subj_id, predicate, obj_id)
    now = int(time.time())
    conn = safe_connect(db_path)
    try:
        cur = conn.execute(
            "SELECT id, weight FROM kg_relations WHERE user_id=? AND subject_id=? AND predicate=? AND object_id=?",
            (user_id, subj_id, predicate, obj_id)
        ).fetchone()
        if cur:
            conn.execute(
                "UPDATE kg_relations SET weight=weight+0.3, last_accessed=? WHERE id=?",
                (now, cur[0])
            )
            rid = cur[0]
        else:
            conn.execute(
                "INSERT INTO kg_relations (id, user_id, subject_id, predicate, object_id, weight, source, created_at, last_accessed) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (rid, user_id, subj_id, predicate, obj_id, 1.0, source, now, now)
            )
        conn.commit()
    finally:
        conn.close()
    return rid


def add_triples(db_path: Path, *, user_id: str = "default",
                triples: List[Dict], source: str = "auto") -> int:
    """Add multiple triples. Each: {subject, predicate, object}. Returns count added."""
    count = 0
    for t in triples:
        rid = upsert_relation(
            db_path, user_id=user_id,
            subject=t.get("subject", ""), predicate=t.get("predicate", ""),
            obj=t.get("object", ""), source=source,
        )
        if rid:
            count += 1
    return count


def get_entity(db_path: Path, *, user_id: str = "default", name: str) -> Optional[Dict]:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM kg_entities WHERE user_id=? AND name_lower=?",
        (user_id, name.lower())
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_entity_relations(db_path: Path, *, user_id: str = "default",
                         entity_name: str, direction: str = "both") -> List[Dict]:
    """Get all relations involving an entity. direction: 'out' (subject), 'in' (object), 'both'."""
    ent = get_entity(db_path, user_id=user_id, name=entity_name)
    if not ent:
        return []
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    results = []
    if direction in ("out", "both"):
        rows = conn.execute(
            "SELECT r.predicate, r.weight, e2.name AS object_name, e2.type AS object_type "
            "FROM kg_relations r JOIN kg_entities e2 ON r.object_id=e2.id "
            "WHERE r.user_id=? AND r.subject_id=? ORDER BY r.weight DESC",
            (user_id, ent["id"])
        ).fetchall()
        for r in rows:
            results.append({"direction": "out", "predicate": r["predicate"],
                          "object": r["object_name"], "object_type": r["object_type"],
                          "weight": r["weight"]})
    if direction in ("in", "both"):
        rows = conn.execute(
            "SELECT r.predicate, r.weight, e1.name AS subject_name, e1.type AS subject_type "
            "FROM kg_relations r JOIN kg_entities e1 ON r.subject_id=e1.id "
            "WHERE r.user_id=? AND r.object_id=? ORDER BY r.weight DESC",
            (user_id, ent["id"])
        ).fetchall()
        for r in rows:
            results.append({"direction": "in", "predicate": r["predicate"],
                          "subject": r["subject_name"], "subject_type": r["subject_type"],
                          "weight": r["weight"]})
    conn.close()
    return results


def search_entities(db_path: Path, *, user_id: str = "default",
                    query: str, top_k: int = 5) -> List[Dict]:
    """Search entities by name (substring match). Returns top-k matches with relations."""
    if not query:
        return []
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    # Substring match on name (case-insensitive)
    rows = conn.execute(
        "SELECT * FROM kg_entities WHERE user_id=? AND name_lower LIKE ? ORDER BY weight DESC LIMIT ?",
        (user_id, f"%{query.lower()}%", top_k)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def traverse(db_path: Path, *, user_id: str = "default",
             start_entity: str, max_hops: int = 2, max_results: int = 10) -> List[Dict]:
    """BFS traverse from a start entity. Returns paths as triples.
    Useful for 'what does the user like?' → traverse from 'user' via 'likes'."""
    visited: Set[str] = set()
    queue: List[Tuple[str, int, List[Dict]]] = []
    start_ent = get_entity(db_path, user_id=user_id, name=start_entity)
    if not start_ent:
        return []
    queue.append((start_ent["id"], 0, []))
    visited.add(start_ent["id"])
    results = []
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    while queue and len(results) < max_results:
        eid, hops, path = queue.pop(0)
        if hops >= max_hops:
            continue
        # Out relations
        rows = conn.execute(
            "SELECT r.predicate, r.object_id, e.name AS object_name "
            "FROM kg_relations r JOIN kg_entities e ON r.object_id=e.id "
            "WHERE r.user_id=? AND r.subject_id=? AND r.weight > 0.3 ORDER BY r.weight DESC LIMIT 5",
            (user_id, eid)
        ).fetchall()
        for r in rows:
            triple = {"subject": start_entity if hops == 0 else None,
                     "predicate": r["predicate"], "object": r["object_name"], "hops": hops + 1}
            new_path = path + [triple]
            results.append({"path": new_path, "hops": hops + 1})
            if r["object_id"] not in visited:
                visited.add(r["object_id"])
                queue.append((r["object_id"], hops + 1, new_path))
    conn.close()
    return results[:max_results]


def get_all_triples(db_path: Path, *, user_id: str = "default",
                    limit: int = 200) -> List[Dict]:
    """Get all triples for visualization. Returns list of {subject, predicate, object, weight}."""
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT e1.name AS subject, r.predicate, e2.name AS object, r.weight, r.last_accessed "
        "FROM kg_relations r "
        "JOIN kg_entities e1 ON r.subject_id=e1.id "
        "JOIN kg_entities e2 ON r.object_id=e2.id "
        "WHERE r.user_id=? ORDER BY r.weight DESC LIMIT ?",
        (user_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_stats(db_path: Path, *, user_id: str = "default") -> Dict:
    conn = safe_connect(db_path)
    ent_count = conn.execute("SELECT COUNT(*) FROM kg_entities WHERE user_id=?", (user_id,)).fetchone()[0]
    rel_count = conn.execute("SELECT COUNT(*) FROM kg_relations WHERE user_id=?", (user_id,)).fetchone()[0]
    conn.row_factory = sqlite3.Row
    top_entities = conn.execute(
        "SELECT name, type, weight FROM kg_entities WHERE user_id=? ORDER BY weight DESC LIMIT 5",
        (user_id,)
    ).fetchall()
    conn.close()
    return {
        "entities": ent_count,
        "relations": rel_count,
        "top_entities": [dict(r) for r in top_entities] if top_entities else [],
    }


def delete_entity(db_path: Path, *, user_id: str = "default", name: str) -> int:
    """Delete an entity and all its relations."""
    ent = get_entity(db_path, user_id=user_id, name=name)
    if not ent:
        return 0
    conn = safe_connect(db_path)
    cur1 = conn.execute("DELETE FROM kg_relations WHERE user_id=? AND (subject_id=? OR object_id=?)",
                       (user_id, ent["id"], ent["id"]))
    cur2 = conn.execute("DELETE FROM kg_entities WHERE id=?", (ent["id"],))
    conn.commit()
    conn.close()
    return cur1.rowcount + cur2.rowcount


# ============================================================
# LLM-driven triple extraction
# ============================================================

EXTRACT_TRIPLES_PROMPT = """你是一个知识图谱构建器。从下面的对话中提取实体-关系-实体三元组。

【对话】
{conversation}

【任务】
提取值得长期记住的事实，形成 (主体, 谓词, 客体) 三元组。规则：
1. 主体和客体是名词性实体（人、物、概念、地点、项目等）
2. 谓词用英文小写下划线，如：likes, dislikes, is_a, uses, works_at, learned, wants_to, made, plays, studies
3. 只提取持久事实，不要提取临时对话内容
4. 实体名用中文或英文原名，保持简洁（如 "Minecraft"、"Python"、"zjq"、"上海"）
5. 不要提取超过 8 个三元组，只保留最重要的

输出 JSON 数组格式：
```json
[
  {"subject": "zjq", "predicate": "likes", "object": "Minecraft"},
  {"subject": "zjq", "predicate": "uses", "object": "Python"},
  {"subject": "Minecraft", "predicate": "is_a", "object": "sandbox_game"}
]
```

如果没有可提取的三元组，输出：[]
"""


async def extract_triples_via_llm(conversation: str, http_client, api_cfg: Dict) -> List[Dict]:
    """Ask the LLM to extract knowledge graph triples from a conversation snippet."""
    if len(conversation) < 50:
        return []
    try:
        payload = {
            "model": api_cfg["api_model"],
            "messages": [{"role": "user", "content": EXTRACT_TRIPLES_PROMPT.format(conversation=conversation[:2500])}],
            "temperature": 0.2,
            "max_tokens": 600,
            "stream": False,
            "enable_thinking": False,
        }
        resp = await http_client.post(
            f"{api_cfg['api_base_url']}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {api_cfg['api_key']}", "Content-Type": "application/json"},
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"].strip()
        # Extract JSON array
        m = re.search(r"\[.*\]", text, re.DOTALL)
        if not m:
            return []
        try:
            triples = json.loads(m.group(0))
            if isinstance(triples, list):
                return [t for t in triples if isinstance(t, dict) and t.get("subject") and t.get("object")]
        except json.JSONDecodeError:
            return []
        return []
    except Exception as e:
        print(f"[kg] extract triples failed: {e}")
        return []
