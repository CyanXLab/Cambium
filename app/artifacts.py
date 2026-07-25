"""
Artifacts — the things the user and AI create together.

In Cambium, the unit of long-term value is NOT the message. It's the artifact.
A README, a design doc, a paper, a prompt, a piece of code, a note, a project
plan, a novel chapter, an image, a knowledge entry, a model.

Artifacts are versioned (parent_id links versions). They can be related to
each other (related_artifacts). They can be tagged. They remember which
resident helped create them.

This is the "World" module — created things live here.

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


VALID_TYPES = {
    "readme", "design", "paper", "prompt", "code", "note", "project",
    "novel", "image", "knowledge", "model", "skill", "plan", "research",
    "essay", "spec", "outline", "draft"
}
VALID_FORMATS = {"markdown", "code", "html", "json", "text", "yaml"}
VALID_STATUSES = {"draft", "in_review", "published", "archived"}
VALID_CREATED_BY = {"user", "ai", "joint"}


def create(
    db_path: Path,
    user_id: str,
    type_: str,
    title: str,
    content: str = "",
    format_: str = "markdown",
    parent_id: Optional[str] = None,
    status: str = "draft",
    created_by: str = "joint",
    created_with_resident: str = "",
    related_artifacts: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict] = None,
    file_path: str = "",
) -> Dict:
    if type_ not in VALID_TYPES:
        raise ValueError(f"invalid type: {type_}")
    if format_ not in VALID_FORMATS:
        raise ValueError(f"invalid format: {format_}")
    aid = str(uuid.uuid4())
    now = int(time.time())
    # Determine version: if parent_id given, increment parent's version
    version = 1
    if parent_id:
        parent = get(db_path, parent_id)
        if parent:
            version = parent["version"] + 1
    row = {
        "id": aid, "user_id": user_id, "type": type_, "title": title,
        "content": content, "format": format_, "parent_id": parent_id,
        "version": version, "status": status, "created_by": created_by,
        "created_with_resident": created_with_resident,
        "related_artifacts": json.dumps(related_artifacts or [], ensure_ascii=False),
        "tags": json.dumps(tags or [], ensure_ascii=False),
        "metadata": json.dumps(metadata or {}, ensure_ascii=False),
        "file_path": file_path,
        "created_at": now, "updated_at": now, "accessed_at": now, "access_count": 0,
    }
    conn = safe_connect(db_path)
    conn.execute(
        """INSERT INTO artifacts
           (id, user_id, type, title, content, format, parent_id, version, status,
            created_by, created_with_resident, related_artifacts, tags, metadata,
            file_path, created_at, updated_at, accessed_at, access_count)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        tuple(row.values())
    )
    conn.commit()
    conn.close()
    row["related_artifacts"] = related_artifacts or []
    row["tags"] = tags or []
    row["metadata"] = metadata or {}
    return row


def get(db_path: Path, artifact_id: str, track_access: bool = False) -> Optional[Dict]:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    r = conn.execute("SELECT * FROM artifacts WHERE id=?", (artifact_id,)).fetchone()
    if r and track_access:
        conn.execute(
            "UPDATE artifacts SET accessed_at=?, access_count=access_count+1 WHERE id=?",
            (int(time.time()), artifact_id)
        )
        conn.commit()
    conn.close()
    if not r:
        return None
    return _normalize(dict(r))


def list_artifacts(
    db_path: Path,
    user_id: str,
    type_: Optional[str] = None,
    status: Optional[str] = None,
    tag: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Dict]:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    q = "SELECT * FROM artifacts WHERE user_id=?"
    params = [user_id]
    if type_ and type_ in VALID_TYPES:
        q += " AND type=?"
        params.append(type_)
    if status and status in VALID_STATUSES:
        q += " AND status=?"
        params.append(status)
    if tag:
        q += " AND tags LIKE ?"
        params.append(f'%"{tag}"%')
    q += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [_normalize(dict(r)) for r in rows]


def list_recent(db_path: Path, user_id: str, days: int = 7, limit: int = 10) -> List[Dict]:
    cutoff = int(time.time()) - days * 86400
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT * FROM artifacts
           WHERE user_id=? AND created_at >= ?
           ORDER BY created_at DESC LIMIT ?""",
        (user_id, cutoff, limit)
    ).fetchall()
    conn.close()
    return [_normalize(dict(r)) for r in rows]


def update(
    db_path: Path,
    artifact_id: str,
    fields: Dict,
) -> Optional[Dict]:
    """Update fields. If content changes, this should typically create a new version instead."""
    allowed = {"title", "content", "format", "status", "related_artifacts", "tags", "metadata"}
    sets, vals = [], []
    for k, v in fields.items():
        if k not in allowed:
            continue
        if k in ("related_artifacts", "tags", "metadata"):
            v = json.dumps(v, ensure_ascii=False)
        sets.append(f"{k}=?")
        vals.append(v)
    if not sets:
        return get(db_path, artifact_id)
    sets.append("updated_at=?")
    vals.append(int(time.time()))
    vals.append(artifact_id)
    conn = safe_connect(db_path)
    conn.execute(f"UPDATE artifacts SET {', '.join(sets)} WHERE id=?", vals)
    conn.commit()
    conn.close()
    return get(db_path, artifact_id)


def new_version(
    db_path: Path,
    artifact_id: str,
    new_content: str,
    title: Optional[str] = None,
    created_by: str = "joint",
    created_with_resident: str = "",
) -> Optional[Dict]:
    """Create a new version of an artifact. The old one stays; the new one links via parent_id."""
    parent = get(db_path, artifact_id)
    if not parent:
        return None
    return create(
        db_path, parent["user_id"],
        type_=parent["type"],
        title=title or parent["title"],
        content=new_content,
        format_=parent["format"],
        parent_id=parent["id"],
        status="draft",
        created_by=created_by,
        created_with_resident=created_with_resident,
        related_artifacts=parent["related_artifacts"],
        tags=parent["tags"],
        metadata=parent["metadata"],
    )


def get_history(db_path: Path, artifact_id: str) -> List[Dict]:
    """Get the full version history of an artifact (walking parent_id chain)."""
    history = []
    current = get(db_path, artifact_id)
    if not current:
        return []
    history.append(current)
    # Walk back via parent_id
    seen = {current["id"]}
    while current.get("parent_id"):
        pid = current["parent_id"]
        if pid in seen:
            break  # cycle protection
        seen.add(pid)
        current = get(db_path, pid)
        if not current:
            break
        history.append(current)
    return history


def delete(db_path: Path, artifact_id: str) -> bool:
    conn = safe_connect(db_path)
    cur = conn.execute("DELETE FROM artifacts WHERE id=?", (artifact_id,))
    conn.commit()
    ok = cur.rowcount > 0
    conn.close()
    return ok


def get_stats(db_path: Path, user_id: str = "default") -> Dict:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    total = conn.execute(
        "SELECT COUNT(*) as cnt FROM artifacts WHERE user_id=?", (user_id,)
    ).fetchone()
    by_type_rows = conn.execute(
        "SELECT type, COUNT(*) as cnt FROM artifacts WHERE user_id=? GROUP BY type",
        (user_id,)
    ).fetchall()
    by_status_rows = conn.execute(
        "SELECT status, COUNT(*) as cnt FROM artifacts WHERE user_id=? GROUP BY status",
        (user_id,)
    ).fetchall()
    recent_7d = conn.execute(
        "SELECT COUNT(*) as cnt FROM artifacts WHERE user_id=? AND created_at >= ?",
        (user_id, int(time.time()) - 7 * 86400)
    ).fetchone()
    conn.close()
    return {
        "total": total["cnt"] if total else 0,
        "by_type": {r["type"]: r["cnt"] for r in by_type_rows},
        "by_status": {r["status"]: r["cnt"] for r in by_status_rows},
        "recent_7d": recent_7d["cnt"] if recent_7d else 0,
    }


def _normalize(d: Dict) -> Dict:
    for k in ("related_artifacts", "tags", "metadata"):
        try:
            d[k] = json.loads(d.get(k) or "[]")
        except Exception:
            d[k] = []
    return d
