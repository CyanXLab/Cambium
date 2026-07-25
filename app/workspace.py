"""
Workspace for Cambium — the AI's own home directory.

Unlike a database (which is structured but opaque), the workspace is a
human-readable, browsable home where the AI organizes its thoughts, plans,
drafts, and knowledge.

Seven sections (aligned with the Cognitive Pillars):
- Brain:    free-form thoughts, ideas, observations
- Projects: project notes, status, decisions
- Library:  reference material, collected knowledge
- Notebook: journal entries, daily logs
- Goals:    goal tracking, milestones
- People:   notes about people in the user's life
- Skills:   skill notes and learnings

Each item has: title, content (markdown), type, tags, parent (for trees),
and access tracking.

The AI can read/write these via tools. Users can browse via the UI.
This is the "home" that makes Cambium feel like someone who lives somewhere,
not a stateless API.
"""
from __future__ import annotations
import json
import time
import hashlib
import sqlite3
from typing import List, Dict, Optional
from pathlib import Path
from app.db_utils import safe_connect


SECTIONS = ["brain", "projects", "library", "notebook", "goals", "people", "skills"]
ITEM_TYPES = ["note", "doc", "draft", "plan", "idea", "log", "decision", "question"]


def create_item(db_path: Path, *, user_id: str = "default",
                section: str, title: str, content: str = "",
                item_type: str = "note", tags: Optional[List[str]] = None,
                parent_id: Optional[str] = None,
                metadata: Optional[Dict] = None) -> Dict:
    """Create a workspace item."""
    if section not in SECTIONS:
        raise ValueError(f"Invalid section: {section}. Must be one of {SECTIONS}")
    if item_type not in ITEM_TYPES:
        item_type = "note"
    iid = hashlib.sha1(f"{user_id}:{section}:{title}:{time.time()}".encode()).hexdigest()[:16]
    now = int(time.time())
    conn = safe_connect(db_path)
    conn.execute(
        "INSERT INTO workspace_items (id, user_id, section, title, content, item_type, "
        "tags, metadata, parent_id, created_at, updated_at, accessed_at, access_count) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (iid, user_id, section, title, content, item_type,
         json.dumps(tags or [], ensure_ascii=False),
         json.dumps(metadata or {}, ensure_ascii=False),
         parent_id, now, now, now, 0)
    )
    conn.commit()
    conn.close()
    return {"id": iid, "section": section, "title": title}


def get_item(db_path: Path, item_id: str) -> Optional[Dict]:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM workspace_items WHERE id=?", (item_id,)).fetchone()
    if row:
        # Update access tracking
        conn.execute(
            "UPDATE workspace_items SET accessed_at=?, access_count=access_count+1 WHERE id=?",
            (int(time.time()), item_id)
        )
        conn.commit()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["tags"] = json.loads(d.get("tags", "[]"))
    d["metadata"] = json.loads(d.get("metadata", "{}"))
    return d


def list_items(db_path: Path, *, user_id: str = "default",
               section: Optional[str] = None, item_type: Optional[str] = None,
               parent_id: Optional[str] = None, limit: int = 50,
               search: Optional[str] = None) -> List[Dict]:
    """List workspace items, optionally filtered."""
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    sql = "SELECT * FROM workspace_items WHERE user_id=?"
    params = [user_id]
    if section:
        sql += " AND section=?"
        params.append(section)
    if item_type:
        sql += " AND item_type=?"
        params.append(item_type)
    if parent_id:
        sql += " AND parent_id=?"
        params.append(parent_id)
    if search:
        sql += " AND (title LIKE ? OR content LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    sql += " ORDER BY updated_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["tags"] = json.loads(d.get("tags", "[]"))
        d["metadata"] = json.loads(d.get("metadata", "{}"))
        out.append(d)
    return out


def update_item(db_path: Path, item_id: str, **fields) -> bool:
    """Update a workspace item."""
    allowed = {"title", "content", "item_type", "tags", "metadata", "section"}
    updates = {}
    for k, v in fields.items():
        if k in allowed:
            if k in ("tags", "metadata"):
                updates[k] = json.dumps(v, ensure_ascii=False)
            else:
                updates[k] = v
    if not updates:
        return False
    updates["updated_at"] = int(time.time())
    sets = ", ".join(f"{k}=?" for k in updates)
    vals = list(updates.values()) + [item_id]
    conn = safe_connect(db_path)
    cur = conn.execute(f"UPDATE workspace_items SET {sets} WHERE id=?", vals)
    conn.commit()
    conn.close()
    return cur.rowcount > 0


def delete_item(db_path: Path, item_id: str) -> bool:
    conn = safe_connect(db_path)
    cur = conn.execute("DELETE FROM workspace_items WHERE id=?", (item_id,))
    conn.commit()
    conn.close()
    return cur.rowcount > 0


def get_stats(db_path: Path, user_id: str = "default") -> Dict:
    """Get workspace statistics per section."""
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    stats = {}
    for section in SECTIONS:
        count = conn.execute(
            "SELECT COUNT(*) FROM workspace_items WHERE user_id=? AND section=?",
            (user_id, section)
        ).fetchone()[0]
        stats[section] = count
    total = sum(stats.values())
    conn.close()
    return {"total": total, "by_section": stats}
