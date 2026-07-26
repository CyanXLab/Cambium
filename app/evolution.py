"""
Evolution — tracks how the user's thoughts, interests, and beliefs change over time.

The AI uses this to:
  - Draw "thought evolution" curves ("a year ago you cared about Memory; now Identity")
  - Surface "you used to think X — has that changed?"
  - Show milestones in the Living Timeline

Event types:
  - interest_shift:    user's primary interest moved (Memory → Identity → Continuity)
  - belief_change:     a philosophy item was added/superseded/retired
  - skill_growth:      user got measurably better at something
  - relationship_change: the dynamic between user and AI shifted
  - identity_shift:    the AI's own identity phase changed (forming → growing → mature)

Sources:
  - philosophy changes (auto-logged when items are added/superseded)
  - cognitive_kernel identity phase transitions
  - timeline_events importance shifts
  - manual user creation
  - AI observation during reflection

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
    "interest_shift", "belief_change", "skill_growth",
    "relationship_change", "identity_shift", "principle_override"
}
VALID_OBSERVED_BY = {"ai", "user", "auto"}
VALID_STATUSES = {"observed", "confirmed", "disputed"}


def create_event(
    db_path: Path,
    user_id: str,
    type_: str,
    from_state: str = "",
    to_state: str = "",
    evidence: str = "",
    evidence_refs: Optional[Dict] = None,
    confidence: float = 0.5,
    observed_by: str = "ai",
    occurred_at: Optional[int] = None,
) -> Dict:
    if type_ not in VALID_TYPES:
        raise ValueError(f"invalid type: {type_}")
    if observed_by not in VALID_OBSERVED_BY:
        raise ValueError(f"invalid observed_by: {observed_by}")
    eid = str(uuid.uuid4())
    now = int(time.time())
    row = {
        "id": eid, "user_id": user_id, "type": type_,
        "from_state": from_state, "to_state": to_state,
        "evidence": evidence,
        "evidence_refs": json.dumps(evidence_refs or {}, ensure_ascii=False),
        "confidence": max(0.0, min(1.0, confidence)),
        "observed_by": observed_by,
        "status": "observed",
        "occurred_at": occurred_at or now,
        "created_at": now,
    }
    conn = safe_connect(db_path)
    conn.execute(
        """INSERT INTO evolution_events
           (id, user_id, type, from_state, to_state, evidence, evidence_refs,
            confidence, observed_by, status, occurred_at, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        tuple(row.values())
    )
    conn.commit()
    conn.close()
    row["evidence_refs"] = evidence_refs or {}
    return row


def get_event(db_path: Path, event_id: str) -> Optional[Dict]:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    r = conn.execute("SELECT * FROM evolution_events WHERE id=?", (event_id,)).fetchone()
    conn.close()
    if not r:
        return None
    d = dict(r)
    try:
        d["evidence_refs"] = json.loads(d.get("evidence_refs") or "{}")
    except Exception:
        d["evidence_refs"] = {}
    return d


def list_events(
    db_path: Path,
    user_id: str,
    type_: Optional[str] = None,
    limit: int = 100,
) -> List[Dict]:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    if type_ and type_ in VALID_TYPES:
        rows = conn.execute(
            """SELECT * FROM evolution_events
               WHERE user_id=? AND type=?
               ORDER BY occurred_at DESC LIMIT ?""",
            (user_id, type_, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT * FROM evolution_events
               WHERE user_id=?
               ORDER BY occurred_at DESC LIMIT ?""",
            (user_id, limit)
        ).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["evidence_refs"] = json.loads(d.get("evidence_refs") or "{}")
        except Exception:
            d["evidence_refs"] = {}
        out.append(d)
    return out


def confirm_event(db_path: Path, event_id: str) -> bool:
    conn = safe_connect(db_path)
    cur = conn.execute(
        "UPDATE evolution_events SET status='confirmed' WHERE id=?", (event_id,)
    )
    conn.commit()
    ok = cur.rowcount > 0
    conn.close()
    return ok


def dispute_event(db_path: Path, event_id: str) -> bool:
    conn = safe_connect(db_path)
    cur = conn.execute(
        "UPDATE evolution_events SET status='disputed' WHERE id=?", (event_id,)
    )
    conn.commit()
    ok = cur.rowcount > 0
    conn.close()
    return ok


def get_evolution_curve(
    db_path: Path,
    user_id: str,
    type_: str = "interest_shift",
    months: int = 12,
) -> List[Dict]:
    """Get the evolution curve for a given type, last N months.
    Returns chronological list of {date, from_state, to_state, evidence}."""
    cutoff = int(time.time()) - months * 30 * 86400
    events = list_events(db_path, user_id, type_=type_, limit=200)
    return [e for e in events if e["occurred_at"] >= cutoff]


def get_stats(db_path: Path, user_id: str = "default") -> Dict:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT type, COUNT(*) as cnt FROM evolution_events
           WHERE user_id=? GROUP BY type""",
        (user_id,)
    ).fetchall()
    conn.close()
    by_type = {r["type"]: r["cnt"] for r in rows}
    return {
        "total": sum(by_type.values()),
        "by_type": by_type,
    }
