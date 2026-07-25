from __future__ import annotations
from app.db_utils import safe_connect
"""
Episodic Memory subsystem for CyanX AI.

Stores discrete events with temporal/causal structure. Unlike embedding-based
semantic memory (which stores facts), episodic memory stores *events*:
"2026年6月: 用户参加高考，上海，500分，之后讨论专业选择"

Each event has:
- id, user_id, title, description
- occurred_at (when it happened, user-mentioned or inferred)
- recorded_at (when AI recorded it)
- importance (0-100)
- tags (comma-separated keywords)
- related_entities (for linking to knowledge graph)
- emotional_valence (positive/negative/neutral)
- status (planned/ongoing/completed/abandoned)

Events can be linked causally: event A → led_to → event B

This enables queries like "高考后来怎么样了？" → find the 高考 event → traverse
its causal chain → return the whole story.

Self-contained module. main.py exposes /api/episodes/* endpoints.
"""
import json
import re
import sqlite3
import time
import hashlib
from typing import List, Dict, Optional
from pathlib import Path


EPISODIC_SCHEMA = """
CREATE TABLE IF NOT EXISTS episodes (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    occurred_at TEXT NOT NULL DEFAULT '',
    recorded_at INTEGER NOT NULL,
    importance INTEGER NOT NULL DEFAULT 50,
    tags TEXT NOT NULL DEFAULT '',
    related_entities TEXT NOT NULL DEFAULT '[]',
    emotional_valence TEXT NOT NULL DEFAULT 'neutral',
    status TEXT NOT NULL DEFAULT 'completed',
    source TEXT NOT NULL DEFAULT 'auto',
    decay_weight REAL NOT NULL DEFAULT 1.0,
    last_accessed INTEGER NOT NULL,
    access_count INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_episodes_user ON episodes(user_id, recorded_at);
CREATE INDEX IF NOT EXISTS idx_episodes_occurred ON episodes(user_id, occurred_at);
CREATE INDEX IF NOT EXISTS idx_episodes_importance ON episodes(user_id, importance);

CREATE TABLE IF NOT EXISTS episode_links (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    from_episode TEXT NOT NULL,
    to_episode TEXT NOT NULL,
    relation TEXT NOT NULL DEFAULT 'led_to',
    created_at INTEGER NOT NULL,
    UNIQUE(user_id, from_episode, to_episode, relation)
);
CREATE INDEX IF NOT EXISTS idx_episode_links_from ON episode_links(user_id, from_episode);
"""


def init_episodic_db(db_path: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = safe_connect(db_path)
    conn.executescript(EPISODIC_SCHEMA)
    conn.commit()
    conn.close()


def create_episode(db_path: Path, *, user_id: str = "default",
                   title: str, description: str = "",
                   occurred_at: str = "", importance: int = 50,
                   tags: str = "", related_entities: Optional[List[str]] = None,
                   emotional_valence: str = "neutral",
                   status: str = "completed",
                   source: str = "auto") -> Dict:
    """Create a new episodic memory entry."""
    eid = hashlib.sha1(f"{user_id}:{title}:{time.time()}".encode()).hexdigest()[:16]
    now = int(time.time())
    if related_entities is None:
        related_entities = []
    conn = safe_connect(db_path)
    conn.execute(
        "INSERT INTO episodes (id, user_id, title, description, occurred_at, recorded_at, "
        "importance, tags, related_entities, emotional_valence, status, source, last_accessed) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (eid, user_id, title, description, occurred_at, now,
         importance, tags, json.dumps(related_entities, ensure_ascii=False),
         emotional_valence, status, source, now)
    )
    conn.commit()
    conn.close()
    return {"id": eid, "title": title, "importance": importance, "occurred_at": occurred_at}


def link_episodes(db_path: Path, *, user_id: str = "default",
                  from_id: str, to_id: str, relation: str = "led_to") -> bool:
    """Create a causal/temporal link between two episodes."""
    lid = hashlib.sha1(f"{user_id}:{from_id}:{relation}:{to_id}".encode()).hexdigest()[:16]
    now = int(time.time())
    conn = safe_connect(db_path)
    try:
        conn.execute(
            "INSERT OR IGNORE INTO episode_links (id, user_id, from_episode, to_episode, relation, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (lid, user_id, from_id, to_id, relation, now)
        )
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def get_episode(db_path: Path, episode_id: str) -> Optional[Dict]:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM episodes WHERE id=?", (episode_id,)).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    try:
        d["related_entities"] = json.loads(d.get("related_entities", "[]"))
    except Exception:
        d["related_entities"] = []
    return d


def list_episodes(db_path: Path, *, user_id: str = "default",
                  limit: int = 50, min_importance: int = 0,
                  order_by: str = "recorded_at") -> List[Dict]:
    """List episodes for a user. order_by: recorded_at | occurred_at | importance."""
    valid_orders = {"recorded_at", "occurred_at", "importance"}
    order = order_by if order_by in valid_orders else "recorded_at"
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        f"SELECT * FROM episodes WHERE user_id=? AND importance>=? ORDER BY {order} DESC LIMIT ?",
        (user_id, min_importance, limit)
    ).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["related_entities"] = json.loads(d.get("related_entities", "[]"))
        except Exception:
            d["related_entities"] = []
        out.append(d)
    return out


def search_episodes(db_path: Path, query: str, *, user_id: str = "default",
                    top_k: int = 5) -> List[Dict]:
    """Search episodes by title/description/tags (substring + keyword match)."""
    if not query:
        return []
    q_lower = query.lower()
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM episodes WHERE user_id=? ORDER BY importance DESC, recorded_at DESC LIMIT 100",
        (user_id,)
    ).fetchall()
    conn.close()
    scored = []
    for r in rows:
        d = dict(r)
        title_l = (d.get("title") or "").lower()
        desc_l = (d.get("description") or "").lower()
        tags_l = (d.get("tags") or "").lower()
        score = 0.0
        if q_lower in title_l:
            score += 3.0
        if q_lower in desc_l:
            score += 1.5
        if q_lower in tags_l:
            score += 2.0
        # Keyword overlap
        query_kws = set(re.findall(r"[\u4e00-\u9fff]+|[a-z]+", q_lower))
        if query_kws:
            text_l = title_l + " " + desc_l + " " + tags_l
            for kw in query_kws:
                if len(kw) >= 2 and kw in text_l:
                    score += 0.5
        # Importance + decay weight boost
        score *= (0.5 + d.get("importance", 50) / 100.0)
        score *= d.get("decay_weight", 1.0)
        if score > 0:
            scored.append((score, d))
    scored.sort(key=lambda x: -x[0])
    out = []
    for _, d in scored[:top_k]:
        try:
            d["related_entities"] = json.loads(d.get("related_entities", "[]"))
        except Exception:
            d["related_entities"] = []
        out.append(d)
    return out


def get_episode_chain(db_path: Path, episode_id: str, *, max_depth: int = 3) -> List[Dict]:
    """Get the causal chain starting from an episode (BFS via episode_links)."""
    visited = {episode_id}
    queue = [(episode_id, 0)]
    chain = []
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    while queue:
        eid, depth = queue.pop(0)
        if depth >= max_depth:
            continue
        links = conn.execute(
            "SELECT to_episode, relation FROM episode_links WHERE from_episode=?",
            (eid,)
        ).fetchall()
        for link in links:
            to_id = link["to_episode"]
            if to_id in visited:
                continue
            visited.add(to_id)
            ep_row = conn.execute("SELECT * FROM episodes WHERE id=?", (to_id,)).fetchone()
            if ep_row:
                d = dict(ep_row)
                try:
                    d["related_entities"] = json.loads(d.get("related_entities", "[]"))
                except Exception:
                    d["related_entities"] = []
                d["depth"] = depth + 1
                d["link_relation"] = link["relation"]
                chain.append(d)
                queue.append((to_id, depth + 1))
    conn.close()
    return chain


def update_episode(db_path: Path, episode_id: str, **fields) -> bool:
    if not fields:
        return False
    allowed = {"title", "description", "occurred_at", "importance", "tags",
               "emotional_valence", "status", "decay_weight"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return False
    if "related_entities" in fields and isinstance(fields["related_entities"], list):
        updates["related_entities"] = json.dumps(fields["related_entities"], ensure_ascii=False)
    sets = ", ".join(f"{k}=?" for k in updates)
    vals = list(updates.values()) + [episode_id]
    conn = safe_connect(db_path)
    cur = conn.execute(f"UPDATE episodes SET {sets} WHERE id=?", vals)
    conn.commit()
    conn.close()
    return cur.rowcount > 0


def delete_episode(db_path: Path, episode_id: str) -> bool:
    conn = safe_connect(db_path)
    cur = conn.execute("DELETE FROM episodes WHERE id=?", (episode_id,))
    conn.execute("DELETE FROM episode_links WHERE from_episode=? OR to_episode=?", (episode_id, episode_id))
    conn.commit()
    conn.close()
    return cur.rowcount > 0


def apply_decay(db_path: Path, *, user_id: str = "default",
                decay_factor: float = 0.98, min_weight: float = 0.3) -> int:
    """Apply decay to all episodes. Called periodically by background scheduler.
    Episodes not accessed recently lose weight, but never below min_weight."""
    now = int(time.time())
    conn = safe_connect(db_path)
    rows = conn.execute(
        "SELECT id, decay_weight, last_accessed, importance FROM episodes WHERE user_id=?",
        (user_id,)
    ).fetchall()
    updated = 0
    for row in rows:
        eid, weight, last_acc, imp = row
        # Decay faster for low-importance episodes
        age_days = (now - last_acc) / 86400
        if age_days < 1:
            continue  # don't decay recently accessed
        # Importance protects against decay
        imp_factor = 1.0 - (imp / 100.0) * 0.5  # importance 100 → factor 0.5 (slower decay)
        effective_decay = decay_factor ** (age_days * (1 - imp_factor))
        new_weight = max(min_weight, weight * effective_decay)
        if abs(new_weight - weight) > 0.001:
            conn.execute("UPDATE episodes SET decay_weight=? WHERE id=?", (new_weight, eid))
            updated += 1
    conn.commit()
    conn.close()
    return updated


def get_stats(db_path: Path, *, user_id: str = "default") -> Dict:
    conn = safe_connect(db_path)
    total = conn.execute("SELECT COUNT(*) FROM episodes WHERE user_id=?", (user_id,)).fetchone()[0]
    by_status = {}
    for r in conn.execute(
        "SELECT status, COUNT(*) AS c FROM episodes WHERE user_id=? GROUP BY status",
        (user_id,)
    ).fetchall():
        by_status[r[0]] = r[1]
    by_importance = {"high": 0, "mid": 0, "low": 0}
    for r in conn.execute(
        "SELECT importance FROM episodes WHERE user_id=?", (user_id,)
    ).fetchall():
        if r[0] >= 75:
            by_importance["high"] += 1
        elif r[0] >= 40:
            by_importance["mid"] += 1
        else:
            by_importance["low"] += 1
    conn.row_factory = sqlite3.Row
    recent = conn.execute(
        "SELECT title, occurred_at, importance, status FROM episodes WHERE user_id=? ORDER BY recorded_at DESC LIMIT 5",
        (user_id,)
    ).fetchall()
    conn.close()
    return {
        "total": total,
        "by_status": by_status,
        "by_importance": by_importance,
        "recent": [dict(r) for r in recent] if recent else [],
    }


# ============================================================
# LLM-driven episode extraction
# ============================================================

EXTRACT_EPISODE_PROMPT = """你是一个事件记忆提取器。从对话中识别值得长期记住的【事件】（不是事实）。

事件示例：
- "我下周要参加面试" → 事件：参加面试（status: planned）
- "今天高考出分了，500分" → 事件：高考出分（occurred_at: 2026-06, importance: 95）
- "我开始学 Rust 了" → 事件：开始学 Rust（importance: 60）
- "我项目 NOVA 完成了记忆系统" → 事件：NOVA 记忆系统完成（importance: 70）

【对话】
{conversation}

【任务】
提取对话中提到的【事件】。规则：
1. 事件是具体的、有时空上下文的发生的事，不是静态事实（"我喜欢 Python" 是事实，不是事件）
2. occurred_at: 用户提到的时间（如 "2026-06"、"上周"、"今天"），无法判断则留空
3. importance: 0-100，对用户人生/项目有重大影响的给高分（高考=95，日常吃饭=10）
4. tags: 关键词，逗号分隔
5. emotional_valence: positive/negative/neutral
6. status: planned/ongoing/completed/abandoned
7. 最多提取 3 个最重要的事件

输出 JSON 数组：
```json
[
  {
    "title": "高考出分",
    "description": "上海高考500分",
    "occurred_at": "2026-06",
    "importance": 95,
    "tags": "高考,上海,500分",
    "emotional_valence": "neutral",
    "status": "completed"
  }
]
```

如果没有事件可提取，输出：[]
"""


async def extract_episodes_via_llm(conversation: str, http_client, api_cfg: Dict) -> List[Dict]:
    if len(conversation) < 50:
        return []
    try:
        payload = {
            "model": api_cfg["api_model"],
            "messages": [{"role": "user", "content": EXTRACT_EPISODE_PROMPT.format(conversation=conversation[:2500])}],
            "temperature": 0.2,
            "max_tokens": 800,
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
        m = re.search(r"\[.*\]", text, re.DOTALL)
        if not m:
            return []
        try:
            episodes = json.loads(m.group(0))
            if isinstance(episodes, list):
                return [e for e in episodes if isinstance(e, dict) and e.get("title")]
        except json.JSONDecodeError:
            return []
        return []
    except Exception as e:
        print(f"[episodes] extract failed: {e}")
        return []
