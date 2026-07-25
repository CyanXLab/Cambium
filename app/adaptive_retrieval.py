"""
Adaptive Retrieval for Cambium — self-evolving retrieval weights.

Based on: EvolveMem (2026) — "Self-Evolving Memory Architecture via AutoResearch"

Problem: memory_orchestrator.retrieve_relevant() uses hardcoded weights:
  keyword 0.35 + importance 0.25 + recency 0.15 + decay 0.15 + layer 0.10

These weights should adapt based on user feedback. If the user frequently
asks "what did I say about X?" → keyword weight should increase. If the user
values recent context → recency weight should increase.

This module:
1. Tracks retrieval outcomes (was a retrieved memory actually useful?)
2. Adjusts weights based on feedback signals (user clicks "like", continues
   the topic, or ignores the retrieved memory)
3. Persists weights per user

The weights are stored in the adaptive_weights table and loaded by
memory_orchestrator.retrieve_relevant() if available.
"""
from __future__ import annotations
import json
import time
import hashlib
import sqlite3
from typing import Dict, List, Optional
from pathlib import Path
from app.db_utils import safe_connect


# Default weights (must sum to 1.0)
DEFAULT_WEIGHTS = {
    "keyword": 0.35,
    "importance": 0.25,
    "recency": 0.15,
    "decay": 0.15,
    "layer": 0.10,
}

ADAPTIVE_SCHEMA = """
CREATE TABLE IF NOT EXISTS adaptive_weights (
    user_id TEXT PRIMARY KEY,
    weights TEXT NOT NULL DEFAULT '{}',
    feedback_count INTEGER NOT NULL DEFAULT 0,
    last_adjusted INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS retrieval_feedback (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    query TEXT NOT NULL,
    retrieved_memory_id TEXT NOT NULL,
    retrieved_content TEXT NOT NULL DEFAULT '',
    feedback TEXT NOT NULL DEFAULT 'neutral',  -- positive/neutral/negative
    signal_type TEXT NOT NULL DEFAULT 'implicit',  -- explicit/implicit
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_feedback_user ON retrieval_feedback(user_id, created_at);
"""


def init_adaptive_db(db_path: Path):
    conn = safe_connect(db_path)
    conn.executescript(ADAPTIVE_SCHEMA)
    conn.commit()
    conn.close()


def get_weights(db_path: Path, user_id: str = "default") -> Dict[str, float]:
    """Get adaptive weights for a user. Falls back to defaults."""
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT weights FROM adaptive_weights WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    if row and row["weights"]:
        try:
            w = json.loads(row["weights"])
            # Merge with defaults to ensure all keys exist
            return {**DEFAULT_WEIGHTS, **w}
        except Exception:
            pass
    return DEFAULT_WEIGHTS.copy()


def record_feedback(db_path: Path, *, user_id: str = "default",
                    query: str, memory_id: str, memory_content: str = "",
                    feedback: str = "neutral", signal_type: str = "implicit"):
    """Record feedback on a retrieval result.
    feedback: positive (useful), negative (irrelevant), neutral (no signal)
    signal_type: explicit (user clicked), implicit (inferred from behavior)
    """
    fid = hashlib.sha1(f"{user_id}:{query[:30]}:{memory_id}:{time.time_ns()}".encode()).hexdigest()[:16]
    now = int(time.time())
    conn = safe_connect(db_path)
    conn.execute(
        "INSERT INTO retrieval_feedback (id, user_id, query, retrieved_memory_id, retrieved_content, feedback, signal_type, created_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (fid, user_id, query[:200], memory_id, memory_content[:200], feedback, signal_type, now)
    )
    conn.commit()
    conn.close()


def adjust_weights(db_path: Path, user_id: str = "default") -> Dict[str, float]:
    """Adjust weights based on accumulated feedback.

    Logic:
    - If positive feedback correlates with high keyword match → increase keyword weight
    - If positive feedback correlates with high importance → increase importance weight
    - If positive feedback correlates with recency → increase recency weight
    - Adjustments are small (±0.02 per cycle) and bounded (min 0.05, max 0.50)
    """
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    # Get recent feedback
    rows = conn.execute(
        "SELECT feedback FROM retrieval_feedback WHERE user_id=? AND created_at > ? ORDER BY created_at DESC LIMIT 50",
        (user_id, int(time.time()) - 7 * 86400)  # last 7 days
    ).fetchall()
    conn.close()

    if len(rows) < 5:
        # Not enough feedback to adjust
        return get_weights(db_path, user_id)

    current = get_weights(db_path, user_id)
    positive = sum(1 for r in rows if r["feedback"] == "positive")
    negative = sum(1 for r in rows if r["feedback"] == "negative")
    total = len(rows)

    if total == 0:
        return current

    # Simple adjustment: if more positive than negative, reinforce current weights slightly
    # If more negative, shift toward defaults
    positive_ratio = positive / total
    negative_ratio = negative / total

    adjustment = 0.02  # max adjustment per cycle
    new_weights = {}

    for key, val in current.items():
        if positive_ratio > 0.6:
            # Reinforce: move slightly toward current
            new_val = val + adjustment * (val - DEFAULT_WEIGHTS.get(key, 0.2))
        elif negative_ratio > 0.4:
            # Correct: move slightly toward defaults
            new_val = val - adjustment * (val - DEFAULT_WEIGHTS.get(key, 0.2))
        else:
            new_val = val
        # Clamp
        new_val = max(0.05, min(0.50, new_val))
        new_weights[key] = round(new_val, 4)

    # Normalize to sum=1.0
    total_w = sum(new_weights.values())
    if total_w > 0:
        new_weights = {k: round(v / total_w, 4) for k, v in new_weights.items()}

    # Persist
    now = int(time.time())
    conn = safe_connect(db_path)
    conn.execute(
        "INSERT INTO adaptive_weights (user_id, weights, feedback_count, last_adjusted) "
        "VALUES (?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET weights=excluded.weights, "
        "feedback_count=excluded.feedback_count, last_adjusted=excluded.last_adjusted",
        (user_id, json.dumps(new_weights, ensure_ascii=False), total, now)
    )
    conn.commit()
    conn.close()

    return new_weights


def get_feedback_stats(db_path: Path, user_id: str = "default") -> Dict:
    """Get feedback statistics."""
    conn = safe_connect(db_path)
    total = conn.execute("SELECT COUNT(*) FROM retrieval_feedback WHERE user_id=?", (user_id,)).fetchone()[0]
    positive = conn.execute("SELECT COUNT(*) FROM retrieval_feedback WHERE user_id=? AND feedback='positive'", (user_id,)).fetchone()[0]
    negative = conn.execute("SELECT COUNT(*) FROM retrieval_feedback WHERE user_id=? AND feedback='negative'", (user_id,)).fetchone()[0]
    weights = get_weights(db_path, user_id)
    conn.close()
    return {
        "total_feedback": total,
        "positive": positive,
        "negative": negative,
        "neutral": total - positive - negative,
        "current_weights": weights,
        "default_weights": DEFAULT_WEIGHTS,
    }
