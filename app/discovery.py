"""
Discovery — the daily surprises the AI surfaces to the user.

Each morning (or whenever Life Loop runs), the AI looks at recent activity
and notices things:
  - patterns:    "you've mentioned X 5 times this week"
  - insights:    "three concepts you've been using are actually the same thing"
  - contradictions: "you said X yesterday but Y three weeks ago"
  - suggestions: "you haven't touched Z in 2 months — has your interest shifted?"
  - merges:      "auto-merged 2 duplicate knowledge entries"
  - observations: anything else noteworthy

These surface in the morning letter and on the Today homepage.
They are the AI's voice — "I noticed", "I wonder", "I found".

Self-contained module. main.py exposes via HTTP.
"""
from __future__ import annotations
import sqlite3
import json
import uuid
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path

from app.db_utils import safe_connect


VALID_TYPES = {
    "pattern", "insight", "contradiction", "suggestion",
    "merge", "observation"
}
VALID_STATUSES = {"new", "seen", "acted", "dismissed"}
VALID_DISCOVERED_BY = {"ai", "life_loop", "resident", "user"}


def create(
    db_path: Path,
    user_id: str,
    type_: str,
    title: str,
    content: str,
    evidence: str = "",
    evidence_refs: Optional[List] = None,
    confidence: float = 0.5,
    discovered_by: str = "ai",
    date_str: Optional[str] = None,
) -> Dict:
    if type_ not in VALID_TYPES:
        raise ValueError(f"invalid type: {type_}")
    if discovered_by not in VALID_DISCOVERED_BY:
        raise ValueError(f"invalid discovered_by: {discovered_by}")
    did = str(uuid.uuid4())
    now = int(time.time())
    date_str = date_str or datetime.now().strftime("%Y-%m-%d")
    row = {
        "id": did, "user_id": user_id, "type": type_,
        "title": title, "content": content,
        "evidence": evidence,
        "evidence_refs": json.dumps(evidence_refs or [], ensure_ascii=False),
        "confidence": max(0.0, min(1.0, confidence)),
        "status": "new", "discovered_by": discovered_by,
        "date_str": date_str,
        "created_at": now, "seen_at": None,
    }
    conn = safe_connect(db_path)
    conn.execute(
        """INSERT INTO discoveries
           (id, user_id, type, title, content, evidence, evidence_refs,
            confidence, status, discovered_by, date_str, created_at, seen_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        tuple(row.values())
    )
    conn.commit()
    conn.close()
    row["evidence_refs"] = evidence_refs or []
    # Auto-index to vector store
    try:
        from app.vector_indexer import index_discovery
        index_discovery(db_path, did, title, content, type_)
    except Exception:
        pass
    return row


def get(db_path: Path, discovery_id: str) -> Optional[Dict]:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    r = conn.execute("SELECT * FROM discoveries WHERE id=?", (discovery_id,)).fetchone()
    conn.close()
    if not r:
        return None
    d = dict(r)
    try:
        d["evidence_refs"] = json.loads(d.get("evidence_refs") or "[]")
    except Exception:
        d["evidence_refs"] = []
    return d


def list_by_date(
    db_path: Path,
    user_id: str,
    date_str: str,
    status: Optional[str] = None,
) -> List[Dict]:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    if status and status in VALID_STATUSES:
        rows = conn.execute(
            """SELECT * FROM discoveries
               WHERE user_id=? AND date_str=? AND status=?
               ORDER BY created_at DESC""",
            (user_id, date_str, status)
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT * FROM discoveries
               WHERE user_id=? AND date_str=?
               ORDER BY created_at DESC""",
            (user_id, date_str)
        ).fetchall()
    conn.close()
    return [_normalize(dict(r)) for r in rows]


def list_by_date_range(
    db_path: Path,
    user_id: str,
    start_date: str,
    end_date: str,
    status: Optional[str] = None,
) -> List[Dict]:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    if status and status in VALID_STATUSES:
        rows = conn.execute(
            """SELECT * FROM discoveries
               WHERE user_id=? AND date_str >= ? AND date_str <= ? AND status=?
               ORDER BY date_str DESC, created_at DESC""",
            (user_id, start_date, end_date, status)
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT * FROM discoveries
               WHERE user_id=? AND date_str >= ? AND date_str <= ?
               ORDER BY date_str DESC, created_at DESC""",
            (user_id, start_date, end_date)
        ).fetchall()
    conn.close()
    return [_normalize(dict(r)) for r in rows]


def list_recent(
    db_path: Path,
    user_id: str,
    days: int = 7,
    limit: int = 50,
) -> List[Dict]:
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT * FROM discoveries
           WHERE user_id=? AND date_str >= ?
           ORDER BY date_str DESC, created_at DESC LIMIT ?""",
        (user_id, cutoff, limit)
    ).fetchall()
    conn.close()
    return [_normalize(dict(r)) for r in rows]


def mark_seen(db_path: Path, discovery_id: str) -> bool:
    now = int(time.time())
    conn = safe_connect(db_path)
    cur = conn.execute(
        "UPDATE discoveries SET status='seen', seen_at=? WHERE id=? AND status='new'",
        (now, discovery_id)
    )
    conn.commit()
    ok = cur.rowcount > 0
    conn.close()
    return ok


def mark_acted(db_path: Path, discovery_id: str) -> bool:
    now = int(time.time())
    conn = safe_connect(db_path)
    cur = conn.execute(
        "UPDATE discoveries SET status='acted', seen_at=? WHERE id=?",
        (now, discovery_id)
    )
    conn.commit()
    ok = cur.rowcount > 0
    conn.close()
    return ok


def dismiss(db_path: Path, discovery_id: str) -> bool:
    now = int(time.time())
    conn = safe_connect(db_path)
    cur = conn.execute(
        "UPDATE discoveries SET status='dismissed', seen_at=? WHERE id=?",
        (now, discovery_id)
    )
    conn.commit()
    ok = cur.rowcount > 0
    conn.close()
    return ok


def delete(db_path: Path, discovery_id: str) -> bool:
    conn = safe_connect(db_path)
    cur = conn.execute("DELETE FROM discoveries WHERE id=?", (discovery_id,))
    conn.commit()
    ok = cur.rowcount > 0
    conn.close()
    return ok


def get_stats(db_path: Path, user_id: str = "default") -> Dict:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    today = datetime.now().strftime("%Y-%m-%d")
    new_today = conn.execute(
        "SELECT COUNT(*) as cnt FROM discoveries WHERE user_id=? AND date_str=? AND status='new'",
        (user_id, today)
    ).fetchone()
    by_status_rows = conn.execute(
        "SELECT status, COUNT(*) as cnt FROM discoveries WHERE user_id=? GROUP BY status",
        (user_id,)
    ).fetchall()
    total = conn.execute(
        "SELECT COUNT(*) as cnt FROM discoveries WHERE user_id=?", (user_id,)
    ).fetchone()
    conn.close()
    by_status = {r["status"]: r["cnt"] for r in by_status_rows}
    return {
        "total": total["cnt"] if total else 0,
        "new_today": new_today["cnt"] if new_today else 0,
        "by_status": by_status,
    }


def _normalize(d: Dict) -> Dict:
    try:
        d["evidence_refs"] = json.loads(d.get("evidence_refs") or "[]")
    except Exception:
        d["evidence_refs"] = []
    return d
