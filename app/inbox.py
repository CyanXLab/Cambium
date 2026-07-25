"""
Inbox — universal capture for Cambium.

Everything goes in here first. Life Loop routes items to:
  - journal      (a reflection-worthy note)
  - memory       (a durable fact about the user)
  - goal         (an intention or commitment)
  - task         (a concrete todo)
  - research     (a topic to investigate)
  - note         (a general note in workspace)
  - archive      (kept but not routed)

The Inbox is the single entry point. Inspired by NP-OS: capture first,
triage later. This is what makes Cambium feel alive — the user can toss
in a stray thought, a URL, a voice memo, a todo, and trust that the
system will route it correctly without manual organization.

Self-contained module. main.py exposes it via HTTP endpoints.
"""
from __future__ import annotations
import sqlite3
import json
import uuid
import time
from typing import Dict, List, Optional
from pathlib import Path

from app.db_utils import safe_connect


VALID_TYPES = {"text", "url", "voice", "image", "todo", "file", "note", "idea"}
VALID_STATUSES = {"pending", "processed", "archived", "deleted"}
VALID_DESTINATIONS = {"", "journal", "memory", "goal", "task", "research", "note", "archive"}


def add_item(
    db_path: Path,
    user_id: str,
    type_: str,
    content: str,
    title: str = "",
    source: str = "manual",
    metadata: Optional[Dict] = None,
) -> Dict:
    """Add a new item to the inbox. Returns the created item."""
    if type_ not in VALID_TYPES:
        raise ValueError(f"invalid type: {type_}")
    item_id = str(uuid.uuid4())
    now = int(time.time())
    row = {
        "id": item_id,
        "user_id": user_id,
        "type": type_,
        "content": content,
        "title": title or (content[:60] if content else ""),
        "source": source,
        "metadata": json.dumps(metadata or {}, ensure_ascii=False),
        "status": "pending",
        "destination": "",
        "destination_id": "",
        "created_at": now,
        "processed_at": None,
    }
    conn = safe_connect(db_path)
    conn.execute(
        """INSERT INTO inbox_items
           (id, user_id, type, content, title, source, metadata,
            status, destination, destination_id, created_at, processed_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (row["id"], row["user_id"], row["type"], row["content"], row["title"],
         row["source"], row["metadata"], row["status"], row["destination"],
         row["destination_id"], row["created_at"], row["processed_at"])
    )
    conn.commit()
    conn.close()
    return row


def list_items(
    db_path: Path,
    user_id: str,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Dict]:
    """List inbox items, optionally filtered by status. Newest first."""
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    if status and status in VALID_STATUSES:
        cur = conn.execute(
            """SELECT * FROM inbox_items
               WHERE user_id=? AND status=?
               ORDER BY created_at DESC LIMIT ? OFFSET ?""",
            (user_id, status, limit, offset)
        )
    else:
        cur = conn.execute(
            """SELECT * FROM inbox_items
               WHERE user_id=? AND status != 'deleted'
               ORDER BY created_at DESC LIMIT ? OFFSET ?""",
            (user_id, limit, offset)
        )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    for r in rows:
        try:
            r["metadata"] = json.loads(r.get("metadata") or "{}")
        except Exception:
            r["metadata"] = {}
    return rows


def get_item(db_path: Path, item_id: str) -> Optional[Dict]:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    r = conn.execute("SELECT * FROM inbox_items WHERE id=?", (item_id,)).fetchone()
    conn.close()
    if not r:
        return None
    d = dict(r)
    try:
        d["metadata"] = json.loads(d.get("metadata") or "{}")
    except Exception:
        d["metadata"] = {}
    return d


def update_item(
    db_path: Path,
    item_id: str,
    content: Optional[str] = None,
    title: Optional[str] = None,
    metadata: Optional[Dict] = None,
) -> bool:
    """Edit an inbox item's content/title/metadata."""
    conn = safe_connect(db_path)
    cur = conn.execute("SELECT content, title, metadata FROM inbox_items WHERE id=?", (item_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return False
    new_content = content if content is not None else row[0]
    new_title = title if title is not None else row[1]
    if metadata is not None:
        new_meta = json.dumps(metadata, ensure_ascii=False)
    else:
        new_meta = row[2]
    conn.execute(
        "UPDATE inbox_items SET content=?, title=?, metadata=? WHERE id=?",
        (new_content, new_title, new_meta, item_id)
    )
    conn.commit()
    conn.close()
    return True


def process_item(
    db_path: Path,
    item_id: str,
    destination: str,
    destination_id: str = "",
) -> bool:
    """Mark an item as processed, recording where it was routed."""
    if destination not in VALID_DESTINATIONS:
        raise ValueError(f"invalid destination: {destination}")
    now = int(time.time())
    conn = safe_connect(db_path)
    cur = conn.execute(
        """UPDATE inbox_items
           SET status='processed', destination=?, destination_id=?, processed_at=?
           WHERE id=?""",
        (destination, destination_id, now, item_id)
    )
    conn.commit()
    ok = cur.rowcount > 0
    conn.close()
    return ok


def archive_item(db_path: Path, item_id: str) -> bool:
    now = int(time.time())
    conn = safe_connect(db_path)
    cur = conn.execute(
        "UPDATE inbox_items SET status='archived', processed_at=? WHERE id=?",
        (now, item_id)
    )
    conn.commit()
    ok = cur.rowcount > 0
    conn.close()
    return ok


def delete_item(db_path: Path, item_id: str) -> bool:
    conn = safe_connect(db_path)
    cur = conn.execute("UPDATE inbox_items SET status='deleted' WHERE id=?", (item_id,))
    conn.commit()
    ok = cur.rowcount > 0
    conn.close()
    return ok


def get_pending(db_path: Path, user_id: str, limit: int = 50) -> List[Dict]:
    """Get all pending items — these are what Life Loop should triage."""
    return list_items(db_path, user_id, status="pending", limit=limit)


def get_stats(db_path: Path, user_id: str) -> Dict:
    """Quick stats for dashboard display."""
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT status, COUNT(*) as cnt FROM inbox_items
           WHERE user_id=? GROUP BY status""",
        (user_id,)
    ).fetchall()
    by_status = {r["status"]: r["cnt"] for r in rows}
    conn.close()
    return {
        "pending": by_status.get("pending", 0),
        "processed": by_status.get("processed", 0),
        "archived": by_status.get("archived", 0),
        "total": sum(by_status.values()),
    }


def auto_route(content: str, type_: str, title: str = "") -> str:
    """Heuristic routing suggestion (Life Loop can override with LLM judgment).

    Rules:
    - URL → research (unless it looks like a todo)
    - "todo:"/"task:"/"need to"/"必须"/"要做" → task
    - "goal:"/"目标:"/"plan:"/"想要"/"希望" → goal
    - "remember"/"记住"/"fact:" → memory
    - everything else → note (or journal if long & reflective)
    """
    text = (content + " " + title).lower()
    if type_ == "url":
        return "research"
    if any(k in text for k in ["todo:", "task:", "need to", "must ", "要做", "必须", "待办"]):
        return "task"
    if any(k in text for k in ["goal:", "目标", "计划", "想要", "希望", "i want to", "plan:"]):
        return "goal"
    if any(k in text for k in ["remember", "记住", "fact:", "持久", "always"]):
        return "memory"
    # Long reflective text → journal candidate
    if len(content) > 200 and any(k in text for k in ["today", "feel", "感觉", "今天", "想", "觉得"]):
        return "journal"
    return "note"
