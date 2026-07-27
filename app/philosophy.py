"""
Philosophy — the shared value system between user and AI.

Four types:
  - value:       what the user cares about ("Continuity", "Simplicity")
  - belief:      what the user believes is true ("Memory ≠ Identity")
  - principle:   rules to live by ("Simple > Complex")
  - anti_goal:   what to avoid ("Don't build feature collections")

The AI cites these in conversations ("remember, we said simple > complex").
The user can add/edit/retire them. When the user violates one, the AI logs
it as an evolution event.

This is what makes the AI a participant with stakes, not a yes-machine.

Self-contained module. main.py exposes via HTTP.
"""
from __future__ import annotations
import sqlite3
import json
import uuid
import time
from typing import Dict, List, Optional
from pathlib import Path

from app.db_utils import safe_connect


VALID_TYPES = {"value", "belief", "principle", "anti_goal"}
VALID_SOURCES = {"user", "ai", "joint"}
VALID_STATUSES = {"active", "superseded", "retired"}


# Some seed philosophy — populated on first run if empty
SEED_PHILOSOPHY = [
    {
        "type": "principle",
        "content": "Simple > Complex",
        "rationale": "Complexity is the enemy of continuity. A simple system lasts; a complex one breaks.",
        "source": "joint",
        "confidence": 0.9,
    },
    {
        "type": "principle",
        "content": "Continuity over Memory",
        "rationale": "Memory is one mechanism. Continuity is the goal. Don't optimize memory at the expense of identity.",
        "source": "joint",
        "confidence": 0.95,
    },
    {
        "type": "principle",
        "content": "AI is Resident, not Tool",
        "rationale": "A tool is called. A resident lives. The difference is whether it has its own concerns and history.",
        "source": "joint",
        "confidence": 0.9,
    },
    {
        "type": "anti_goal",
        "content": "Don't build a feature collection",
        "rationale": "Feature collections don't have a soul. Build a unified world where features serve the whole.",
        "source": "joint",
        "confidence": 0.85,
    },
    {
        "type": "anti_goal",
        "content": "Don't compete with Claude Code / NP-OS / Obsidian",
        "rationale": "They each do their thing well. Cambium's value is what they don't do: continuity, residents, shared history.",
        "source": "joint",
        "confidence": 0.85,
    },
    {
        "type": "belief",
        "content": "Memory ≠ Identity ≠ Continuity",
        "rationale": "Memory is data. Identity is narrative. Continuity is the thread across time. They are different layers.",
        "source": "joint",
        "confidence": 0.9,
    },
    {
        "type": "value",
        "content": "Growth over Perfection",
        "rationale": "A system that grows is alive. A system that's perfect is dead.",
        "source": "joint",
        "confidence": 0.8,
    },
    {
        "type": "principle",
        "content": "Message → Artifact",
        "rationale": "Messages are ephemeral. Artifacts are what we keep. The unit of long-term value is what we created, not what we said.",
        "source": "joint",
        "confidence": 0.85,
    },
]


def ensure_seed_philosophy(db_path: Path, user_id: str = "default") -> int:
    """Insert seed philosophy if table is empty. Returns count inserted."""
    conn = safe_connect(db_path)
    existing = conn.execute(
        "SELECT COUNT(*) FROM philosophy_items WHERE user_id=?", (user_id,)
    ).fetchone()
    if existing and existing[0] > 0:
        conn.close()
        return 0
    now = int(time.time())
    inserted = 0
    for s in SEED_PHILOSOPHY:
        pid = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO philosophy_items
               (id, user_id, type, content, rationale, source, confidence,
                status, superseded_by, first_observed_at, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (pid, user_id, s["type"], s["content"], s["rationale"], s["source"],
             s["confidence"], "active", "", now, now, now)
        )
        inserted += 1
    conn.commit()
    conn.close()
    return inserted


def create(
    db_path: Path,
    user_id: str,
    type_: str,
    content: str,
    rationale: str = "",
    source: str = "user",
    confidence: float = 0.8,
    first_observed_at: Optional[int] = None,
) -> Dict:
    if type_ not in VALID_TYPES:
        raise ValueError(f"invalid type: {type_}")
    if source not in VALID_SOURCES:
        raise ValueError(f"invalid source: {source}")
    pid = str(uuid.uuid4())
    now = int(time.time())
    row = {
        "id": pid, "user_id": user_id, "type": type_, "content": content,
        "rationale": rationale, "source": source,
        "confidence": max(0.0, min(1.0, confidence)),
        "status": "active", "superseded_by": "",
        "first_observed_at": first_observed_at or now,
        "created_at": now, "updated_at": now,
    }
    conn = safe_connect(db_path)
    conn.execute(
        """INSERT INTO philosophy_items
           (id, user_id, type, content, rationale, source, confidence,
            status, superseded_by, first_observed_at, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        tuple(row.values())
    )
    conn.commit()
    conn.close()
    # Auto-index to vector store
    try:
        from app.vector_indexer import index_philosophy
        index_philosophy(db_path, pid, content, rationale, type_)
    except Exception:
        pass
    return row


def get(db_path: Path, item_id: str) -> Optional[Dict]:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    r = conn.execute("SELECT * FROM philosophy_items WHERE id=?", (item_id,)).fetchone()
    conn.close()
    return dict(r) if r else None


def list_active(db_path: Path, user_id: str, limit: int = 50) -> List[Dict]:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT * FROM philosophy_items
           WHERE user_id=? AND status='active'
           ORDER BY confidence DESC, updated_at DESC LIMIT ?""",
        (user_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def list_by_type(db_path: Path, user_id: str, type_: str) -> List[Dict]:
    if type_ not in VALID_TYPES:
        return []
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT * FROM philosophy_items
           WHERE user_id=? AND type=? AND status='active'
           ORDER BY confidence DESC, updated_at DESC""",
        (user_id, type_)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update(
    db_path: Path,
    item_id: str,
    fields: Dict,
) -> Optional[Dict]:
    allowed = {"content", "rationale", "source", "confidence", "status"}
    sets, vals = [], []
    for k, v in fields.items():
        if k not in allowed:
            continue
        if k == "confidence":
            v = max(0.0, min(1.0, float(v)))
        sets.append(f"{k}=?")
        vals.append(v)
    if not sets:
        return get(db_path, item_id)
    sets.append("updated_at=?")
    vals.append(int(time.time()))
    vals.append(item_id)
    conn = safe_connect(db_path)
    conn.execute(f"UPDATE philosophy_items SET {', '.join(sets)} WHERE id=?", vals)
    conn.commit()
    conn.close()
    return get(db_path, item_id)


def supersede(db_path: Path, old_id: str, new_id: str) -> bool:
    """Mark old as superseded by new."""
    now = int(time.time())
    conn = safe_connect(db_path)
    cur = conn.execute(
        "UPDATE philosophy_items SET status='superseded', superseded_by=?, updated_at=? WHERE id=?",
        (new_id, now, old_id)
    )
    conn.commit()
    ok = cur.rowcount > 0
    conn.close()
    return ok


def retire(db_path: Path, item_id: str) -> bool:
    """Mark as retired (no longer applies)."""
    return update(db_path, item_id, {"status": "retired"}) is not None


def delete(db_path: Path, item_id: str) -> bool:
    conn = safe_connect(db_path)
    cur = conn.execute("DELETE FROM philosophy_items WHERE id=?", (item_id,))
    conn.commit()
    ok = cur.rowcount > 0
    conn.close()
    return ok


def get_stats(db_path: Path, user_id: str = "default") -> Dict:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT type, COUNT(*) as cnt FROM philosophy_items
           WHERE user_id=? AND status='active' GROUP BY type""",
        (user_id,)
    ).fetchall()
    conn.close()
    by_type = {r["type"]: r["cnt"] for r in rows}
    return {
        "total": sum(by_type.values()),
        "by_type": by_type,
        "values": by_type.get("value", 0),
        "beliefs": by_type.get("belief", 0),
        "principles": by_type.get("principle", 0),
        "anti_goals": by_type.get("anti_goal", 0),
    }
