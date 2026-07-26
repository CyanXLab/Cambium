"""
Reflection Tree for Cambium — three-level reflection (Generative Agents).

Based on: Generative Agents (Park et al., 2023) — "Interactive Simulacra of Human Behavior"

Three levels of reflection:
  Level 0: Observations (raw memories from conversation)
  Level 1: Reflections (patterns/insights synthesized from observations)
  Level 2: Meta-reflections (insights about the reflection process itself)

Each reflection node:
  - Has a parent (the observations it was synthesized from)
  - Has children (if a higher-level reflection was built from it)
  - Has importance (higher for deeper reflections)
  - Can be superseded (if a newer reflection contradicts it)

Unlike flat reflection (Life Loop daily), the tree structure allows:
  - "Why do I think the user likes Python?" → trace back to observations
  - "Was that reflection correct?" → meta-reflection can challenge it
  - Progressive deepening: not just "what happened" but "what does it mean"

Called by Life Loop:
  - Daily: build Level 1 from Level 0 observations
  - Weekly: build Level 2 from Level 1 reflections (meta-reflection)
"""
from __future__ import annotations
import json
import time
import sqlite3
import hashlib
from typing import Dict, List, Optional
from pathlib import Path
from app.llm_utils import extract_content as _extract_content
from app.db_utils import safe_connect


def _get_prompt(key, default):
    try:
        from app.main import get_prompt
        return get_prompt(key, default)
    except Exception:
        return default


REFLECTION_SCHEMA = """
CREATE TABLE IF NOT EXISTS reflection_tree (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    level INTEGER NOT NULL DEFAULT 0,  -- 0=observation, 1=reflection, 2=meta-reflection
    content TEXT NOT NULL,
    importance INTEGER NOT NULL DEFAULT 50,
    parent_ids TEXT NOT NULL DEFAULT '[]',  -- JSON array of parent node IDs
    child_ids TEXT NOT NULL DEFAULT '[]',
    source TEXT NOT NULL DEFAULT 'auto',  -- conversation/reflection/meta
    status TEXT NOT NULL DEFAULT 'active',  -- active/superseded/archived
    superseded_by TEXT,
    evidence_count INTEGER NOT NULL DEFAULT 0,
    confidence REAL NOT NULL DEFAULT 0.5,
    created_at INTEGER NOT NULL,
    last_reinforced INTEGER NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_reflection_level ON reflection_tree(user_id, level, status);
CREATE INDEX IF NOT EXISTS idx_reflection_parent ON reflection_tree(user_id);
"""


def init_reflection_db(db_path: Path):
    conn = safe_connect(db_path)
    conn.executescript(REFLECTION_SCHEMA)
    conn.commit()
    conn.close()


def add_observation(db_path: Path, *, user_id: str = "default",
                    content: str, importance: int = 30,
                    source: str = "conversation") -> Dict:
    """Add a Level 0 observation (raw memory from conversation)."""
    nid = hashlib.sha1(f"{user_id}:L0:{content[:50]}:{time.time_ns()}".encode()).hexdigest()[:16]
    now = int(time.time())
    conn = safe_connect(db_path)
    conn.execute(
        "INSERT INTO reflection_tree (id, user_id, level, content, importance, source, status, "
        "evidence_count, confidence, created_at, last_reinforced) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (nid, user_id, 0, content, importance, source, "active", 1, 0.5, now, now)
    )
    conn.commit()
    conn.close()
    return {"id": nid, "level": 0}


def add_reflection(db_path: Path, *, user_id: str = "default",
                   level: int, content: str, importance: int = 60,
                   parent_ids: List[str], source: str = "reflection",
                   confidence: float = 0.6) -> Dict:
    """Add a Level 1 or Level 2 reflection. Links to parent nodes."""
    nid = hashlib.sha1(f"{user_id}:L{level}:{content[:50]}:{time.time_ns()}".encode()).hexdigest()[:16]
    now = int(time.time())
    parents = json.dumps(parent_ids, ensure_ascii=False)
    conn = safe_connect(db_path)
    conn.execute(
        "INSERT INTO reflection_tree (id, user_id, level, content, importance, parent_ids, source, "
        "status, evidence_count, confidence, created_at, last_reinforced) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (nid, user_id, level, content, importance, parents, source, "active",
         len(parent_ids), confidence, now, now)
    )
    # Update parents' child_ids
    for pid in parent_ids:
        row = conn.execute("SELECT child_ids FROM reflection_tree WHERE id=?", (pid,)).fetchone()
        if row:
            children = json.loads(row[0] or "[]")
            children.append(nid)
            conn.execute("UPDATE reflection_tree SET child_ids=? WHERE id=?",
                        (json.dumps(children, ensure_ascii=False), pid))
    conn.commit()
    conn.close()
    return {"id": nid, "level": level}


def get_nodes(db_path: Path, *, user_id: str = "default",
              level: int = 0, status: str = "active",
              min_importance: int = 0, limit: int = 50) -> List[Dict]:
    """Get reflection tree nodes, filtered by level."""
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM reflection_tree WHERE user_id=? AND level=? AND status=? AND importance>=? "
        "ORDER BY created_at DESC LIMIT ?",
        (user_id, level, status, min_importance, limit)
    ).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["parent_ids"] = json.loads(d.get("parent_ids", "[]"))
        d["child_ids"] = json.loads(d.get("child_ids", "[]"))
        d["metadata"] = json.loads(d.get("metadata", "{}"))
        out.append(d)
    return out


def get_nodes_for_reflection(db_path: Path, *, user_id: str = "default",
                              level: int = 0, min_importance: int = 30,
                              limit: int = 20) -> List[Dict]:
    """Get Level 0 nodes that haven't been reflected on yet (no children)."""
    nodes = get_nodes(db_path, user_id=user_id, level=level, min_importance=min_importance, limit=limit)
    return [n for n in nodes if not n["child_ids"]]


def supersede_node(db_path: Path, node_id: str, new_node_id: str):
    """Mark a node as superseded by a newer reflection."""
    now = int(time.time())
    conn = safe_connect(db_path)
    conn.execute(
        "UPDATE reflection_tree SET status='superseded', superseded_by=? WHERE id=?",
        (new_node_id, node_id)
    )
    conn.commit()
    conn.close()


def get_tree_stats(db_path: Path, user_id: str = "default") -> Dict:
    """Get statistics about the reflection tree."""
    conn = safe_connect(db_path)
    stats = {}
    for level in range(3):
        count = conn.execute(
            "SELECT COUNT(*) FROM reflection_tree WHERE user_id=? AND level=? AND status='active'",
            (user_id, level)
        ).fetchone()[0]
        stats[f"level_{level}"] = count
    stats["superseded"] = conn.execute(
        "SELECT COUNT(*) FROM reflection_tree WHERE user_id=? AND status='superseded'",
        (user_id,)
    ).fetchone()[0]
    conn.close()
    return stats


# LLM prompt for building reflections from observations
REFLECTION_PROMPT_DEFAULT = """你是 Cambium 的反思系统。请从以下观察中提炼高层洞察。

【最近的观察（Level 0）】
{observations}

【已有反思（Level 1，不要重复）】
{existing_reflections}

【任务】
从观察中提炼 2-3 条高层洞察。规则：
1. 不是逐条总结，是识别模式
2. 每条洞察应该整合多条观察
3. 标注重要度（0-100）和置信度（0-1）
4. 如果新洞察与已有反思矛盾，标记为 supersede

输出 JSON：
```json
[
  {{"content": "用户最近对系统设计类游戏的兴趣明显上升", "importance": 70, "confidence": 0.7, "supersedes": []}}
]
```
只输出 JSON。"""


async def build_reflection_level(db_path: Path, *, user_id: str = "default",
                                  source_level: int = 0, target_level: int = 1,
                                  http_client, api_cfg: Dict) -> Dict:
    """Build reflections from lower-level nodes using LLM."""
    import re
    # Get unreflected nodes
    nodes = get_nodes_for_reflection(db_path, user_id=user_id, level=source_level, min_importance=30)
    if len(nodes) < 3:
        return {"built": 0, "reason": "not enough observations"}

    # Get existing reflections to avoid duplicates
    existing = get_nodes(db_path, user_id=user_id, level=target_level, limit=10)
    existing_text = "\n".join(f"- {n['content']}" for n in existing) or "(无)"

    # Build observations text
    obs_text = "\n".join(f"- [{n['importance']}] {n['content']}" for n in nodes[:20])

    try:
        payload = {
            "model": api_cfg["api_model"],
            "messages": [{"role": "user", "content": _get_prompt("prompt_reflection_tree", REFLECTION_PROMPT_DEFAULT).format(
                observations=obs_text,
                existing_reflections=existing_text,
            )}],
            "temperature": 0.4,
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
        text = _extract_content(data)
        m = re.search(r"\[.*\]", text, re.DOTALL)
        if not m:
            return {"built": 0, "reason": "no JSON"}
        reflections = json.loads(m.group(0))
        if not isinstance(reflections, list):
            return {"built": 0}

        parent_ids = [n["id"] for n in nodes[:20]]
        built = 0
        for r in reflections:
            if isinstance(r, dict) and r.get("content"):
                result = add_reflection(db_path, user_id=user_id,
                    level=target_level, content=r["content"],
                    importance=int(r.get("importance", 60)),
                    parent_ids=parent_ids, source="reflection",
                    confidence=float(r.get("confidence", 0.6)))
                built += 1
                # Handle supersessions
                for sid in r.get("supersedes", []):
                    pass  # Could mark existing reflections as superseded
        return {"built": built}
    except Exception as e:
        print(f"[reflection_tree] build failed: {e}")
        return {"built": 0, "error": str(e)}
