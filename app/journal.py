"""
Journal — AI-assisted daily journal for Cambium.

Every day, Cambium quietly gathers what happened: conversations, runtime
tasks completed, inbox items captured, reflections generated. At the end
of the day (or on demand), it drafts a journal entry that the user can
edit, reject, or accept. The journal becomes the spine of the user's
"shared history" with the AI.

This is NOT a chat log. It's a curated, narrative account of the day,
with emotional tone, highlights, growth notes, and failures. The user
owns it; the AI assists.

Self-contained module. main.py exposes it via HTTP endpoints.
"""
from __future__ import annotations
import sqlite3
import json
import uuid
import time
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional
from pathlib import Path

from app.db_utils import safe_connect


def _today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _date_to_str(d) -> str:
    if isinstance(d, str):
        return d
    if isinstance(d, date):
        return d.strftime("%Y-%m-%d")
    raise ValueError(f"invalid date: {d}")


def get_or_create(
    db_path: Path,
    user_id: str,
    date_str: Optional[str] = None,
) -> Dict:
    """Get today's (or a specific day's) journal, creating an empty one if missing."""
    date_str = date_str or _today_str()
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM journals WHERE user_id=? AND date=?",
        (user_id, date_str)
    ).fetchone()
    if row:
        d = dict(row)
        conn.close()
        _normalize(d)
        return d
    # create empty
    now = int(time.time())
    jid = str(uuid.uuid4())
    conn.execute(
        """INSERT INTO journals
           (id, user_id, date, content, ai_draft, ai_summary,
            emotional_tone, highlights, growth_notes, failures, gratitude,
            is_auto_generated, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (jid, user_id, date_str, "", "", "", "", "[]", "", "", "", 0, now, now)
    )
    conn.commit()
    conn.close()
    return get_or_create(db_path, user_id, date_str)


def get(db_path: Path, user_id: str, date_str: str) -> Optional[Dict]:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM journals WHERE user_id=? AND date=?",
        (user_id, date_str)
    ).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    _normalize(d)
    return d


def list_range(
    db_path: Path,
    user_id: str,
    days: int = 30,
) -> List[Dict]:
    """List journals from the last N days."""
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = conn.execute(
        """SELECT * FROM journals
           WHERE user_id=? AND date >= ?
           ORDER BY date DESC""",
        (user_id, cutoff_date)
    ).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        _normalize(d)
        out.append(d)
    return out


def update_content(
    db_path: Path,
    user_id: str,
    date_str: str,
    content: str,
) -> Dict:
    """User-edits the journal body. Marks is_auto_generated=0 once touched."""
    j = get_or_create(db_path, user_id, date_str)
    now = int(time.time())
    conn = safe_connect(db_path)
    conn.execute(
        """UPDATE journals SET content=?, is_auto_generated=0, updated_at=?
           WHERE id=?""",
        (content, now, j["id"])
    )
    conn.commit()
    conn.close()
    return get(db_path, user_id, date_str)


def update_fields(
    db_path: Path,
    user_id: str,
    date_str: str,
    fields: Dict,
) -> Dict:
    """Update specific fields (highlights, growth_notes, failures, gratitude, emotional_tone)."""
    j = get_or_create(db_path, user_id, date_str)
    now = int(time.time())
    allowed = {"highlights", "growth_notes", "failures", "gratitude",
               "emotional_tone", "ai_summary", "ai_draft"}
    sets = []
    vals = []
    for k, v in fields.items():
        if k not in allowed:
            continue
        if k == "highlights":
            v = json.dumps(v if isinstance(v, list) else [v], ensure_ascii=False)
        sets.append(f"{k}=?")
        vals.append(v)
    if not sets:
        return get(db_path, user_id, date_str)
    sets.append("updated_at=?")
    vals.append(now)
    vals.append(j["id"])
    conn = safe_connect(db_path)
    conn.execute(f"UPDATE journals SET {', '.join(sets)} WHERE id=?", vals)
    conn.commit()
    conn.close()
    return get(db_path, user_id, date_str)


def set_ai_draft(
    db_path: Path,
    user_id: str,
    date_str: str,
    draft: str,
    summary: str = "",
    emotional_tone: str = "",
    highlights: Optional[List[str]] = None,
) -> Dict:
    """AI populates the draft fields. Does not overwrite user content."""
    j = get_or_create(db_path, user_id, date_str)
    now = int(time.time())
    conn = safe_connect(db_path)
    conn.execute(
        """UPDATE journals
           SET ai_draft=?, ai_summary=?, emotional_tone=?,
               highlights=?, is_auto_generated=1, updated_at=?
           WHERE id=?""",
        (draft, summary, emotional_tone,
         json.dumps(highlights or [], ensure_ascii=False),
         now, j["id"])
    )
    conn.commit()
    conn.close()
    return get(db_path, user_id, date_str)


def delete_journal(db_path: Path, user_id: str, date_str: str) -> bool:
    conn = safe_connect(db_path)
    cur = conn.execute(
        "DELETE FROM journals WHERE user_id=? AND date=?",
        (user_id, date_str)
    )
    conn.commit()
    ok = cur.rowcount > 0
    conn.close()
    return ok


def get_streak(db_path: Path, user_id: str) -> Dict:
    """Compute journaling streak (consecutive days with non-empty content)."""
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT date, content FROM journals
           WHERE user_id=? AND content != ''
           ORDER BY date DESC LIMIT 400""",
        (user_id,)
    ).fetchall()
    conn.close()
    if not rows:
        return {"current_streak": 0, "longest_streak": 0, "total_entries": 0}
    date_set = {r["date"] for r in rows}
    today = datetime.now().date()
    # current streak: walk back from today (or yesterday if today not yet written)
    current = 0
    cursor = today
    if today.strftime("%Y-%m-%d") not in date_set:
        cursor = today - timedelta(days=1)
    while cursor.strftime("%Y-%m-%d") in date_set:
        current += 1
        cursor -= timedelta(days=1)
    # longest streak: walk all dates
    sorted_dates = sorted([datetime.strptime(d, "%Y-%m-%d").date() for d in date_set])
    longest = 1
    run = 1
    for i in range(1, len(sorted_dates)):
        if (sorted_dates[i] - sorted_dates[i-1]).days == 1:
            run += 1
            longest = max(longest, run)
        else:
            run = 1
    return {
        "current_streak": current,
        "longest_streak": longest,
        "total_entries": len(date_set),
    }


def gather_day_activity(db_path: Path, user_id: str, date_str: str) -> Dict:
    """Gather everything that happened on a given day, for AI to draft from.

    Sources:
    - conversations (count, titles, last message preview)
    - runtime tasks completed
    - inbox items captured
    - reflections generated
    - cognitive updates (identity, timeline, narratives)
    """
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
    except Exception:
        return {}
    start_ts = int(datetime(d.year, d.month, d.day).timestamp())
    end_ts = start_ts + 86400

    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row

    # Conversations updated that day
    convs = conn.execute(
        """SELECT id, title, updated_at FROM conversations
           WHERE user_id=? AND updated_at >= ? AND updated_at < ?
           ORDER BY updated_at DESC LIMIT 20""",
        (user_id, start_ts, end_ts)
    ).fetchall() if _table_exists(conn, "conversations") else []

    # Runtime tasks completed that day
    tasks = conn.execute(
        """SELECT id, title, status, completed_at FROM runtime_tasks
           WHERE user_id=? AND completed_at >= ? AND completed_at < ?
           ORDER BY completed_at DESC LIMIT 20""",
        (user_id, start_ts, end_ts)
    ).fetchall() if _table_exists(conn, "runtime_tasks") else []

    # Inbox items captured that day
    inbox_items = conn.execute(
        """SELECT id, type, title FROM inbox_items
           WHERE user_id=? AND created_at >= ? AND created_at < ?
           ORDER BY created_at DESC LIMIT 20""",
        (user_id, start_ts, end_ts)
    ).fetchall() if _table_exists(conn, "inbox_items") else []

    # Reflections (table may not exist or columns may differ)
    if _table_exists(conn, "reflection_tree_nodes"):
        try:
            reflections = conn.execute(
                """SELECT id, observation, insight FROM reflection_tree_nodes
                   WHERE created_at >= ? AND created_at < ?
                   ORDER BY created_at DESC LIMIT 10""",
                (start_ts, end_ts)
            ).fetchall()
        except Exception:
            reflections = []
    else:
        reflections = []

    # Cognitive timeline events
    if _table_exists(conn, "timeline_events"):
        try:
            tl_events = conn.execute(
                """SELECT title, description, significance, importance_weight
                   FROM timeline_events
                   WHERE user_id=? AND created_at >= ? AND created_at < ?
                   ORDER BY created_at DESC LIMIT 10""",
                (user_id, start_ts, end_ts)
            ).fetchall()
        except Exception:
            tl_events = []
    else:
        tl_events = []

    conn.close()

    return {
        "date": date_str,
        "conversations": [dict(r) for r in convs],
        "tasks_completed": [dict(r) for r in tasks],
        "inbox_captures": [dict(r) for r in inbox_items],
        "reflections": [dict(r) for r in reflections],
        "timeline_events": [dict(r) for r in tl_events],
        "stats": {
            "conversations": len(convs),
            "tasks_completed": len(tasks),
            "inbox_captures": len(inbox_items),
            "reflections": len(reflections),
            "timeline_events": len(tl_events),
        },
    }


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
    )
    return cur.fetchone() is not None


def _normalize(d: Dict) -> Dict:
    """Parse JSON fields in place."""
    try:
        d["highlights"] = json.loads(d.get("highlights") or "[]")
    except Exception:
        d["highlights"] = []
    return d
