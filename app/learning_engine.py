"""
Learning Engine for Cambium — from "remembering" to "learning".

Memory stores what happened. Learning extracts *patterns* from what happened
and forms *stable capabilities* that shape future behavior.

Three types of learning:
1. Style Learning    — code style, writing style, response format preferences
2. Preference Learning — tool preferences, model preferences, workflow habits
3. Strategy Learning  — decision patterns, problem-solving approaches

Each learned pattern has:
- confidence (0-1): how well-established this pattern is
- evidence_count: how many times it was observed
- superseded_by: if a newer pattern replaced this one
- status: forming → validated → integrated → superseded

Learning happens via:
1. Explicit corrections (user says "don't do X, do Y instead")
2. Implicit observations (user consistently modifies AI output in the same way)
3. Reflection (Life Loop weekly review identifies patterns)

Usage:
    from app.learning_engine import record_observation, get_learned_patterns
    record_observation(db, user_id="default", pattern_type="style",
                       key="python_naming", value="snake_case",
                       evidence_type="correction")
"""
from __future__ import annotations
import json
import time
import hashlib
import sqlite3
from typing import Dict, List, Optional
from pathlib import Path
from app.db_utils import safe_connect


LEARNING_SCHEMA = """
CREATE TABLE IF NOT EXISTS learned_patterns (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    pattern_type TEXT NOT NULL,  -- style/preference/strategy
    key TEXT NOT NULL,           -- e.g., "python_naming", "response_length"
    value TEXT NOT NULL,         -- e.g., "snake_case", "concise"
    description TEXT NOT NULL DEFAULT '',
    confidence REAL NOT NULL DEFAULT 0.3,
    evidence_count INTEGER NOT NULL DEFAULT 0,
    evidence_types TEXT NOT NULL DEFAULT '[]',  -- JSON: ["correction","observation","reflection"]
    status TEXT NOT NULL DEFAULT 'forming',  -- forming/validated/integrated/superseded
    superseded_by TEXT,
    first_observed INTEGER NOT NULL,
    last_reinforced INTEGER NOT NULL,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    UNIQUE(user_id, pattern_type, key)
);
CREATE INDEX IF NOT EXISTS idx_learned_user ON learned_patterns(user_id, status);
CREATE INDEX IF NOT EXISTS idx_learned_type ON learned_patterns(user_id, pattern_type);

CREATE TABLE IF NOT EXISTS learning_observations (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    pattern_type TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    evidence_type TEXT NOT NULL,  -- correction/observation/reflection
    context TEXT NOT NULL DEFAULT '',  -- what was happening
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_obs_user ON learning_observations(user_id, created_at);
"""


def init_learning_db(db_path: Path):
    conn = safe_connect(db_path)
    conn.executescript(LEARNING_SCHEMA)
    conn.commit()
    conn.close()


def record_observation(db_path: Path, *, user_id: str = "default",
                       pattern_type: str, key: str, value: str,
                       evidence_type: str = "observation",
                       description: str = "", context: str = "") -> Dict:
    """Record a learning observation. If the pattern already exists, reinforce it.
    If a contradictory pattern exists, handle the conflict.

    pattern_type: style/preference/strategy
    key: what aspect (e.g., "python_naming")
    value: what the user prefers (e.g., "snake_case")
    evidence_type: correction/observation/reflection
    """
    now = int(time.time())
    import os, random
    oid = hashlib.sha1(f"{user_id}:{pattern_type}:{key}:{value}:{time.time_ns()}:{os.getpid()}:{random.random()}".encode()).hexdigest()[:16]

    conn = safe_connect(db_path)
    # Log the observation
    conn.execute(
        "INSERT INTO learning_observations (id, user_id, pattern_type, key, value, evidence_type, context, created_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (oid, user_id, pattern_type, key, value, evidence_type, context, now)
    )

    # Check if pattern exists
    conn.row_factory = sqlite3.Row
    existing = conn.execute(
        "SELECT * FROM learned_patterns WHERE user_id=? AND pattern_type=? AND key=? AND status!='superseded'",
        (user_id, pattern_type, key)
    ).fetchone()

    if existing:
        d = dict(existing)
        if d["value"] == value:
            # Same pattern → reinforce
            new_confidence = min(1.0, d["confidence"] + 0.15)
            new_status = "validated" if new_confidence >= 0.7 else d["status"]
            evidence_types = json.loads(d.get("evidence_types", "[]"))
            if evidence_type not in evidence_types:
                evidence_types.append(evidence_type)
            conn.execute(
                "UPDATE learned_patterns SET confidence=?, evidence_count=evidence_count+1, "
                "evidence_types=?, last_reinforced=?, status=?, updated_at=? WHERE id=?",
                (new_confidence, json.dumps(evidence_types), now, new_status, now, d["id"])
            )
            conn.commit()
            conn.close()
            return {"action": "reinforced", "id": d["id"], "confidence": new_confidence}
        else:
            # Contradictory pattern → supersede old, create new
            import os, random
            new_id = hashlib.sha1(f"{user_id}:{pattern_type}:{key}:{value}:{time.time_ns()}:{os.getpid()}:{random.random()}".encode()).hexdigest()[:16]
            # Mark old as superseded (keep for audit, but remove UNIQUE conflict by updating key)
            old_key = d["key"]
            conn.execute(
                "UPDATE learned_patterns SET status='superseded', superseded_by=?, updated_at=?, key=key||'__old_'||? WHERE id=?",
                (new_id, now, str(now), d["id"])
            )
            # Create new with original key
            conn.execute(
                "INSERT INTO learned_patterns (id, user_id, pattern_type, key, value, description, "
                "confidence, evidence_count, evidence_types, status, first_observed, last_reinforced, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (new_id, user_id, pattern_type, old_key, value, description,
                 0.5, 1, json.dumps([evidence_type]), "forming", now, now, now, now)
            )
            conn.commit()
            conn.close()
            return {"action": "superseded", "old_id": d["id"], "new_id": new_id}
    else:
        # New pattern
        pid = hashlib.sha1(f"{user_id}:{pattern_type}:{key}:{value}".encode()).hexdigest()[:16]
        conn.execute(
            "INSERT INTO learned_patterns (id, user_id, pattern_type, key, value, description, "
            "confidence, evidence_count, evidence_types, status, first_observed, last_reinforced, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (pid, user_id, pattern_type, key, value, description,
             0.3, 1, json.dumps([evidence_type]), "forming", now, now, now, now)
        )
        conn.commit()
        conn.close()
        return {"action": "created", "id": pid}


def get_learned_patterns(db_path: Path, *, user_id: str = "default",
                         pattern_type: Optional[str] = None,
                         min_confidence: float = 0.0,
                         status: Optional[str] = None) -> List[Dict]:
    """Get learned patterns, optionally filtered."""
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    sql = "SELECT * FROM learned_patterns WHERE user_id=? AND status!='superseded' AND confidence>=?"
    params = [user_id, min_confidence]
    if pattern_type:
        sql += " AND pattern_type=?"
        params.append(pattern_type)
    if status:
        sql += " AND status=?"
        params.append(status)
    sql += " ORDER BY confidence DESC, last_reinforced DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["evidence_types"] = json.loads(d.get("evidence_types", "[]"))
        out.append(d)
    return out


def get_pattern(db_path: Path, *, user_id: str = "default",
                pattern_type: str, key: str) -> Optional[Dict]:
    """Get a specific learned pattern."""
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM learned_patterns WHERE user_id=? AND pattern_type=? AND key=? AND status!='superseded'",
        (user_id, pattern_type, key)
    ).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["evidence_types"] = json.loads(d.get("evidence_types", "[]"))
    return d


def get_observations(db_path: Path, *, user_id: str = "default",
                     pattern_type: Optional[str] = None, limit: int = 50) -> List[Dict]:
    """Get learning observations (raw evidence)."""
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    if pattern_type:
        rows = conn.execute(
            "SELECT * FROM learning_observations WHERE user_id=? AND pattern_type=? ORDER BY created_at DESC LIMIT ?",
            (user_id, pattern_type, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM learning_observations WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def build_learning_context(db_path: Path, *, user_id: str = "default",
                           max_chars: int = 500) -> str:
    """Build a context section from learned patterns for the LLM.
    Only includes validated or integrated patterns."""
    patterns = get_learned_patterns(db_path, user_id=user_id, min_confidence=0.5)
    if not patterns:
        return ""
    lines = []
    by_type = {"style": [], "preference": [], "strategy": []}
    for p in patterns:
        if p["pattern_type"] in by_type:
            by_type[p["pattern_type"]].append(p)
    type_names = {"style": "已学到的风格", "preference": "已学到的偏好", "strategy": "已学到的策略"}
    for ptype, items in by_type.items():
        if not items:
            continue
        lines.append(f"■ {type_names[ptype]}")
        for item in items[:5]:  # top 5 per type
            conf_pct = int(item["confidence"] * 100)
            lines.append(f"  - {item['key']}: {item['value']} (置信度 {conf_pct}%)")
    text = "\n".join(lines)
    if len(text) > max_chars:
        text = text[:max_chars] + "..."
    if text:
        return f"【我学到的（持续学习）】\n{text}"
    return ""


def get_stats(db_path: Path, user_id: str = "default") -> Dict:
    conn = safe_connect(db_path)
    stats = {}
    stats["total_patterns"] = conn.execute(
        "SELECT COUNT(*) FROM learned_patterns WHERE user_id=? AND status!='superseded'",
        (user_id,)
    ).fetchone()[0]
    stats["validated"] = conn.execute(
        "SELECT COUNT(*) FROM learned_patterns WHERE user_id=? AND status='validated'",
        (user_id,)
    ).fetchone()[0]
    stats["total_observations"] = conn.execute(
        "SELECT COUNT(*) FROM learning_observations WHERE user_id=?",
        (user_id,)
    ).fetchone()[0]
    by_type = {}
    for r in conn.execute(
        "SELECT pattern_type, COUNT(*) AS c FROM learned_patterns WHERE user_id=? AND status!='superseded' GROUP BY pattern_type",
        (user_id,)
    ).fetchall():
        by_type[r[0]] = r[1]
    stats["by_type"] = by_type
    conn.close()
    return stats
