"""
Co-experience — the differentiator.

This module manages "shared moments" between the user and Cambium. Not
just memories (factual recall), but *narrative* memories of things we
went through together: "the day we debated Continuity vs Memory for the
README", "the night you fixed 7 bugs in a row", "when you first started
learning Rust".

Sources of moments:
  - High-importance timeline events (importance >= 0.7)
  - Reflections with high emotional weight
  - Manually created by AI during deep reflection
  - Manually created by user ("remember this")

Usage by AI:
  - When chatting, surface 0-1 relevant moments ("I remember when we...")
  - On daily briefing, surface one moment from history
  - Never surface the same moment more than once per week

This is what makes Cambium feel like a companion, not a tool.
"""
from __future__ import annotations
import sqlite3
import json
import uuid
import time
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path

from app.db_utils import safe_connect


VALID_TYPES = {"shared", "milestone", "first", "turning_point"}


def create_moment(
    db_path: Path,
    user_id: str,
    title: str,
    story: str,
    moment_type: str = "shared",
    occurred_at: Optional[int] = None,
    emotional_weight: float = 0.5,
    context_ref: Optional[Dict] = None,
) -> Dict:
    if moment_type not in VALID_TYPES:
        raise ValueError(f"invalid moment_type: {moment_type}")
    mid = str(uuid.uuid4())
    now = int(time.time())
    occurred_at = occurred_at or now
    row = {
        "id": mid,
        "user_id": user_id,
        "moment_type": moment_type,
        "title": title,
        "story": story,
        "context_ref": json.dumps(context_ref or {}, ensure_ascii=False),
        "occurred_at": occurred_at,
        "emotional_weight": max(0.0, min(1.0, emotional_weight)),
        "surfaced_count": 0,
        "last_surfaced_at": None,
        "created_at": now,
        "updated_at": now,
    }
    conn = safe_connect(db_path)
    conn.execute(
        """INSERT INTO co_experience_moments
           (id, user_id, moment_type, title, story, context_ref,
            occurred_at, emotional_weight, surfaced_count, last_surfaced_at,
            created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (row["id"], row["user_id"], row["moment_type"], row["title"],
         row["story"], row["context_ref"], row["occurred_at"],
         row["emotional_weight"], row["surfaced_count"], row["last_surfaced_at"],
         row["created_at"], row["updated_at"])
    )
    conn.commit()
    conn.close()
    row["context_ref"] = context_ref or {}
    return row


def get_moment(db_path: Path, moment_id: str) -> Optional[Dict]:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    r = conn.execute(
        "SELECT * FROM co_experience_moments WHERE id=?", (moment_id,)
    ).fetchone()
    conn.close()
    if not r:
        return None
    d = dict(r)
    try:
        d["context_ref"] = json.loads(d.get("context_ref") or "{}")
    except Exception:
        d["context_ref"] = {}
    return d


def list_moments(
    db_path: Path,
    user_id: str,
    moment_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict]:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    if moment_type and moment_type in VALID_TYPES:
        rows = conn.execute(
            """SELECT * FROM co_experience_moments
               WHERE user_id=? AND moment_type=?
               ORDER BY occurred_at DESC LIMIT ? OFFSET ?""",
            (user_id, moment_type, limit, offset)
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT * FROM co_experience_moments
               WHERE user_id=?
               ORDER BY occurred_at DESC LIMIT ? OFFSET ?""",
            (user_id, limit, offset)
        ).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["context_ref"] = json.loads(d.get("context_ref") or "{}")
        except Exception:
            d["context_ref"] = {}
        out.append(d)
    return out


def surface_for_today(db_path: Path, user_id: str) -> Optional[Dict]:
    """Pick a moment to surface today. Avoids re-surfacing within 7 days.
    Prefers higher emotional_weight, with some randomness."""
    week_ago = int(time.time()) - 7 * 86400
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    # Candidates not surfaced in the past week
    rows = conn.execute(
        """SELECT * FROM co_experience_moments
           WHERE user_id=? AND (last_surfaced_at IS NULL OR last_surfaced_at < ?)
           ORDER BY emotional_weight DESC, occurred_at DESC LIMIT 30""",
        (user_id, week_ago)
    ).fetchall()
    conn.close()
    if not rows:
        return None
    # Weighted random from top 30
    candidates = [dict(r) for r in rows]
    # Weight = emotional_weight * 10 + 1
    weights = [max(0.1, c["emotional_weight"]) * 10 + 1 for c in candidates]
    pick = random.choices(candidates, weights=weights, k=1)[0]
    # Mark surfaced
    mark_surfaced(db_path, pick["id"])
    try:
        pick["context_ref"] = json.loads(pick.get("context_ref") or "{}")
    except Exception:
        pick["context_ref"] = {}
    return pick


def mark_surfaced(db_path: Path, moment_id: str) -> bool:
    now = int(time.time())
    conn = safe_connect(db_path)
    cur = conn.execute(
        """UPDATE co_experience_moments
           SET surfaced_count = surfaced_count + 1, last_surfaced_at = ?, updated_at=?
           WHERE id=?""",
        (now, now, moment_id)
    )
    conn.commit()
    ok = cur.rowcount > 0
    conn.close()
    return ok


def update_moment(
    db_path: Path,
    moment_id: str,
    title: Optional[str] = None,
    story: Optional[str] = None,
    moment_type: Optional[str] = None,
    emotional_weight: Optional[float] = None,
) -> Optional[Dict]:
    conn = safe_connect(db_path)
    sets, vals = [], []
    if title is not None:
        sets.append("title=?"); vals.append(title)
    if story is not None:
        sets.append("story=?"); vals.append(story)
    if moment_type is not None and moment_type in VALID_TYPES:
        sets.append("moment_type=?"); vals.append(moment_type)
    if emotional_weight is not None:
        sets.append("emotional_weight=?"); vals.append(max(0.0, min(1.0, emotional_weight)))
    if not sets:
        conn.close()
        return get_moment(db_path, moment_id)
    sets.append("updated_at=?"); vals.append(int(time.time()))
    vals.append(moment_id)
    conn.execute(
        f"UPDATE co_experience_moments SET {', '.join(sets)} WHERE id=?", vals
    )
    conn.commit()
    conn.close()
    return get_moment(db_path, moment_id)


def delete_moment(db_path: Path, moment_id: str) -> bool:
    conn = safe_connect(db_path)
    cur = conn.execute("DELETE FROM co_experience_moments WHERE id=?", (moment_id,))
    conn.commit()
    ok = cur.rowcount > 0
    conn.close()
    return ok


def get_stats(db_path: Path, user_id: str) -> Dict:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT moment_type, COUNT(*) as cnt, AVG(emotional_weight) as avg_w
           FROM co_experience_moments WHERE user_id=?
           GROUP BY moment_type""",
        (user_id,)
    ).fetchall()
    conn.close()
    by_type = {r["moment_type"]: {"count": r["cnt"], "avg_weight": r["avg_w"] or 0} for r in rows}
    total = sum(v["count"] for v in by_type.values())
    return {
        "total": total,
        "by_type": by_type,
    }


def harvest_from_timeline(
    db_path: Path,
    user_id: str,
    importance_threshold: float = 0.7,
    limit: int = 20,
) -> int:
    """Harvest high-importance timeline events into co-experience moments.
    Returns the count of new moments created. Idempotent: skips events that
    already have a corresponding moment (tracked via context_ref.timeline_id).

    timeline_events columns: significance (0-100 int), importance_weight (real),
    emotional_valence (text). We treat importance_weight >= threshold OR
    significance/100 >= threshold as "high importance".
    """
    if not _table_exists(db_path, "timeline_events"):
        return 0
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT id, title, description, significance, importance_weight,
                  emotional_valence, occurred_ts, created_at
           FROM timeline_events
           WHERE user_id=? AND (
               importance_weight >= ? OR (significance / 100.0) >= ?
           )
           ORDER BY created_at DESC LIMIT ?""",
        (user_id, importance_threshold, importance_threshold, limit * 2)
    ).fetchall()
    # existing harvested IDs
    existing = conn.execute(
        """SELECT context_ref FROM co_experience_moments
           WHERE user_id=? AND context_ref LIKE '%timeline_id%'""",
        (user_id,)
    ).fetchall()
    conn.close()
    seen_ids = set()
    for r in existing:
        try:
            ref = json.loads(r["context_ref"] or "{}")
            tid = ref.get("timeline_id")
            if tid:
                seen_ids.add(tid)
        except Exception:
            pass
    created = 0
    for r in rows:
        if r["id"] in seen_ids:
            continue
        # Compute importance weight: prefer importance_weight, else significance/100
        if r["importance_weight"] is not None:
            weight = float(r["importance_weight"])
        else:
            weight = (r["significance"] or 50) / 100.0
        weight = max(0.0, min(1.0, weight))
        # Use title or description for the moment text
        title = r["title"] or (r["description"][:80] if r["description"] else "(timeline event)")
        story = r["description"] or r["title"] or ""
        occurred = r["occurred_ts"] or r["created_at"] or int(time.time())
        create_moment(
            db_path, user_id,
            title=title[:120],
            story=story,
            moment_type="turning_point" if weight >= 0.85 else "shared",
            occurred_at=occurred,
            emotional_weight=weight,
            context_ref={
                "timeline_id": r["id"],
                "emotional_tone": r["emotional_valence"] or "",
            }
        )
        created += 1
        if created >= limit:
            break
    return created


def _table_exists(db_path: Path, name: str) -> bool:
    conn = safe_connect(db_path)
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
    )
    ok = cur.fetchone() is not None
    conn.close()
    return ok
