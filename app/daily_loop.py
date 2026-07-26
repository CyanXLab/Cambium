"""
Daily Loop — the morning briefing that turns Cambium from chat-first
to life-first.

When the user opens Cambium, the first thing they see is NOT a chat box.
It's a curated dashboard:

    Good Morning, zjq.

    Yesterday
    - ✓ Cambium Runtime completed
    - ✓ Read 2 hours
    - ✓ Fixed 7 bugs

    AI Reflection
    Yesterday you iterated on Runtime 4 times. I noticed...

    Today's Goals
    - Finish backup export tests
    - Write Daily Loop module

    Journal
    [Today's entry — empty. Click to write.]

    Recent Activity
    - Inbox: 3 pending
    - Research: Embedding paper saved

    A Moment From Our History
    "3 weeks ago, we debated Continuity vs Memory for the README. You
    chose Continuity. Looking back, that framing still holds."

    [ Chat ] [ Inbox + ] [ Journal ]

The chat is just a button. The life comes first.

This module orchestrates data from:
  - cognitive_kernel (identity, goals, timeline)
  - reflection_tree (recent reflections)
  - runtime (tasks completed yesterday/today)
  - inbox (pending items)
  - journal (today's entry)
  - co_experience (today's surfaced moment)
  - sessions / conversations (recent activity)
"""
from __future__ import annotations
import sqlite3
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path

from app.db_utils import safe_connect
from app import journal as journal_mod
from app import inbox as inbox_mod
from app import co_experience as co_exp_mod


def _greeting(name: str = "") -> str:
    """Time-of-day greeting."""
    h = datetime.now().hour
    if h < 5:
        greet = "深夜好"
    elif h < 11:
        greet = "早上好"
    elif h < 14:
        greet = "中午好"
    elif h < 18:
        greet = "下午好"
    elif h < 22:
        greet = "晚上好"
    else:
        greet = "夜深了"
    return f"{greet}，{name}" if name else greet


def _today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _yesterday_str() -> str:
    return (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")


def _start_of_day_ts(d: Optional[str] = None) -> int:
    if d:
        dt = datetime.strptime(d, "%Y-%m-%d")
    else:
        dt = datetime.now()
    return int(datetime(dt.year, dt.month, dt.day).timestamp())


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
    )
    return cur.fetchone() is not None


def get_user_name(db_path: Path, user_id: str = "default") -> str:
    """Try to read user name from settings/profile; fall back to ''."""
    try:
        conn = safe_connect(db_path)
        # try settings table
        if _table_exists(conn, "settings"):
            r = conn.execute(
                "SELECT value FROM settings WHERE key='user_name'"
            ).fetchone()
            if r and r[0]:
                conn.close()
                return r[0]
        # try profile table
        if _table_exists(conn, "user_profile"):
            r = conn.execute(
                "SELECT name FROM user_profile WHERE user_id=?", (user_id,)
            ).fetchone()
            if r and r[0]:
                conn.close()
                return r[0]
        conn.close()
    except Exception:
        pass
    return ""


def get_yesterday_done(db_path: Path, user_id: str = "default") -> List[Dict]:
    """Things completed yesterday: runtime tasks + conversations + inbox processed."""
    y = _yesterday_str()
    start_ts = _start_of_day_ts(y)
    end_ts = start_ts + 86400
    out = []
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row

    if _table_exists(conn, "runtime_tasks"):
        try:
            rows = conn.execute(
                """SELECT id, title, completed_at FROM runtime_tasks
                   WHERE user_id=? AND status='completed'
                     AND completed_at >= ? AND completed_at < ?
                   ORDER BY completed_at DESC LIMIT 20""",
                (user_id, start_ts, end_ts)
            ).fetchall()
            for r in rows:
                out.append({
                    "type": "task",
                    "title": r["title"],
                    "id": r["id"],
                    "timestamp": r["completed_at"],
                })
        except Exception as e:
            print(f"[daily_loop] runtime_tasks yesterday query failed: {e}")

    if _table_exists(conn, "conversations"):
        try:
            rows = conn.execute(
                """SELECT id, title, updated_at FROM conversations
                   WHERE user_id=? AND updated_at >= ? AND updated_at < ?
                   ORDER BY updated_at DESC LIMIT 10""",
                (user_id, start_ts, end_ts)
            ).fetchall()
            for r in rows:
                out.append({
                    "type": "conversation",
                    "title": r["title"] or "(未命名对话)",
                    "id": r["id"],
                    "timestamp": r["updated_at"],
                })
        except Exception as e:
            print(f"[daily_loop] conversations yesterday query failed: {e}")

    if _table_exists(conn, "inbox_items"):
        try:
            rows = conn.execute(
                """SELECT id, title, type, processed_at FROM inbox_items
                   WHERE user_id=? AND status='processed'
                     AND processed_at >= ? AND processed_at < ?
                   ORDER BY processed_at DESC LIMIT 10""",
                (user_id, start_ts, end_ts)
            ).fetchall()
            for r in rows:
                out.append({
                    "type": "inbox",
                    "title": r["title"] or f"[{r['type']}]",
                    "id": r["id"],
                    "timestamp": r["processed_at"],
                })
        except Exception as e:
            print(f"[daily_loop] inbox yesterday query failed: {e}")

    conn.close()
    # Sort by timestamp desc
    out.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
    return out[:20]


def get_today_goals(db_path: Path, user_id: str = "default") -> List[Dict]:
    """Today's goals: pull from cognitive goals (active) + inbox todos (pending) +
    runtime tasks (pending/running)."""
    out = []
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row

    if _table_exists(conn, "long_term_goals"):
        try:
            rows = conn.execute(
                """SELECT id, goal, status FROM long_term_goals
                   WHERE user_id=? AND status='active'
                   ORDER BY updated_at DESC LIMIT 10""",
                (user_id,)
            ).fetchall()
            for r in rows:
                out.append({
                    "type": "goal",
                    "id": r["id"],
                    "title": r["goal"],
                    "status": r["status"],
                    "source": "cognitive",
                })
        except Exception as e:
            print(f"[daily_loop] long_term_goals query failed: {e}")

    if _table_exists(conn, "runtime_tasks"):
        try:
            rows = conn.execute(
                """SELECT id, title, status, priority FROM runtime_tasks
                   WHERE user_id=? AND status IN ('pending', 'running')
                   ORDER BY priority DESC, created_at ASC LIMIT 10""",
                (user_id,)
            ).fetchall()
            for r in rows:
                out.append({
                    "type": "task",
                    "id": r["id"],
                    "title": r["title"],
                    "status": r["status"],
                    "source": "runtime",
                })
        except Exception as e:
            print(f"[daily_loop] runtime_tasks query failed: {e}")

    if _table_exists(conn, "inbox_items"):
        try:
            rows = conn.execute(
                """SELECT id, title, type FROM inbox_items
                   WHERE user_id=? AND status='pending' AND type='todo'
                   ORDER BY created_at DESC LIMIT 10""",
                (user_id,)
            ).fetchall()
            for r in rows:
                out.append({
                    "type": "todo",
                    "id": r["id"],
                    "title": r["title"],
                    "status": "pending",
                    "source": "inbox",
                })
        except Exception as e:
            print(f"[daily_loop] inbox_items query failed: {e}")

    conn.close()
    return out


def get_recent_reflection(db_path: Path, user_id: str = "default", limit: int = 1) -> Optional[Dict]:
    """Get the latest reflection(s) for AI Reflection panel."""
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    if not _table_exists(conn, "reflection_tree_nodes"):
        conn.close()
        return None
    try:
        rows = conn.execute(
            """SELECT id, observation, insight, level, created_at
               FROM reflection_tree_nodes
               ORDER BY created_at DESC LIMIT ?""",
            (limit,)
        ).fetchall()
    except Exception as e:
        print(f"[daily_loop] reflection query failed: {e}")
        conn.close()
        return None
    conn.close()
    if not rows:
        return None
    r = dict(rows[0])
    return r


def get_inbox_pending_count(db_path: Path, user_id: str = "default") -> int:
    try:
        stats = inbox_mod.get_stats(db_path, user_id)
        return stats.get("pending", 0)
    except Exception:
        return 0


def get_today_journal_preview(db_path: Path, user_id: str = "default") -> Dict:
    """Today's journal entry (or empty placeholder)."""
    today = _today_str()
    j = journal_mod.get(db_path, user_id, today)
    if not j:
        return {
            "date": today,
            "content": "",
            "ai_draft": "",
            "ai_summary": "",
            "emotional_tone": "",
            "highlights": [],
            "exists": False,
        }
    return {
        "date": today,
        "content": j["content"],
        "ai_draft": j["ai_draft"],
        "ai_summary": j["ai_summary"],
        "emotional_tone": j["emotional_tone"],
        "highlights": j["highlights"],
        "exists": True,
    }


def get_recent_activity(db_path: Path, user_id: str = "default", limit: int = 5) -> List[Dict]:
    """Recent activity across the system."""
    out = []
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row

    if _table_exists(conn, "conversations"):
        rows = conn.execute(
            """SELECT id, title, updated_at FROM conversations
               WHERE user_id=? ORDER BY updated_at DESC LIMIT ?""",
            (user_id, limit)
        ).fetchall()
        for r in rows:
            out.append({
                "type": "conversation",
                "title": r["title"] or "(未命名)",
                "id": r["id"],
                "timestamp": r["updated_at"],
            })

    if _table_exists(conn, "memory_items"):
        rows = conn.execute(
            """SELECT id, content, created_at FROM memory_items
               WHERE user_id=? ORDER BY created_at DESC LIMIT ?""",
            (user_id, limit)
        ).fetchall()
        for r in rows:
            out.append({
                "type": "memory",
                "title": r["content"][:60],
                "id": r["id"],
                "timestamp": r["created_at"],
            })

    conn.close()
    out.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
    return out[:limit]


def build_briefing(db_path: Path, user_id: str = "default") -> Dict:
    """Assemble the full morning briefing."""
    name = get_user_name(db_path, user_id)
    yesterday_done = get_yesterday_done(db_path, user_id)
    today_goals = get_today_goals(db_path, user_id)
    reflection = get_recent_reflection(db_path, user_id)
    inbox_pending = get_inbox_pending_count(db_path, user_id)
    journal_preview = get_today_journal_preview(db_path, user_id)
    recent_activity = get_recent_activity(db_path, user_id, limit=5)

    # Co-experience moment for today (may be None)
    try:
        moment = co_exp_mod.surface_for_today(db_path, user_id)
    except Exception:
        moment = None

    return {
        "greeting": _greeting(name),
        "date": _today_str(),
        "user_name": name,
        "yesterday_done": yesterday_done,
        "yesterday_count": len(yesterday_done),
        "today_goals": today_goals,
        "today_goals_count": len(today_goals),
        "reflection": reflection,
        "inbox_pending": inbox_pending,
        "journal": journal_preview,
        "recent_activity": recent_activity,
        "co_experience_moment": moment,
        "generated_at": int(time.time()),
    }
