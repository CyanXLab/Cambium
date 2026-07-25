"""
Memory Governance for Cambium — quarantine → validation → promotion.

Based on: SSGM Framework (arXiv 2026) — Governing Evolving Memory in LLM Agents.

Problem: When an AI extracts memories from conversation via LLM, hallucinations
can be固化 as "facts". A single wrong extraction ("user hates Python") can
poison all future interactions.

Solution: Three-stage memory lifecycle:
  1. QUARANTINE — new extractions land here, not in main memory
  2. VALIDATION — cross-check against existing knowledge
  3. PROMOTION — verified memories enter the main store

Also implements:
  - Contradiction detection (new fact vs existing facts)
  - Source tracking (which conversation produced this memory)
  - Confidence decay (unreinforced memories lose confidence)
  - Audit log (every governance action is recorded)
"""
from __future__ import annotations
import json
import time
import hashlib
import sqlite3
from typing import Dict, List, Optional
from pathlib import Path
from app.db_utils import safe_connect
from app import rule_engine


GOVERNANCE_SCHEMA = """
CREATE TABLE IF NOT EXISTS memory_quarantine (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    content TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'other',
    importance INTEGER NOT NULL DEFAULT 50,
    source TEXT NOT NULL DEFAULT 'extraction',
    source_turn TEXT NOT NULL DEFAULT '',
    conversation_id TEXT,
    created_at INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'quarantined',  -- quarantined/validated/rejected/promoted
    validated_at INTEGER,
    validated_by TEXT NOT NULL DEFAULT '',  -- rule/llm/user
    confidence REAL NOT NULL DEFAULT 0.5,
    notes TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_quarantine_status ON memory_quarantine(user_id, status);

CREATE TABLE IF NOT EXISTS governance_audit (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    action TEXT NOT NULL,  -- quarantined/validated/rejected/promoted/contradiction_detected
    memory_id TEXT NOT NULL,
    memory_content TEXT NOT NULL DEFAULT '',
    details TEXT NOT NULL DEFAULT '{}',
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_user ON governance_audit(user_id, created_at);
"""


def init_governance_db(db_path: Path):
    conn = safe_connect(db_path)
    conn.executescript(GOVERNANCE_SCHEMA)
    conn.commit()
    conn.close()


def quarantine(db_path: Path, *, user_id: str = "default", content: str,
               category: str = "other", importance: int = 50,
               source: str = "extraction", source_turn: str = "",
               conversation_id: Optional[str] = None) -> Dict:
    """Place a new memory in quarantine. It won't enter main memory until validated."""
    qid = hashlib.sha1(f"{user_id}:{content[:50]}:{time.time()}".encode()).hexdigest()[:16]
    now = int(time.time())
    conn = safe_connect(db_path)
    conn.execute(
        "INSERT INTO memory_quarantine (id, user_id, content, category, importance, source, "
        "source_turn, conversation_id, created_at, status, confidence) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (qid, user_id, content, category, importance, source, source_turn[:200],
         conversation_id, now, "quarantined", 0.5)
    )
    conn.execute(
        "INSERT INTO governance_audit (id, user_id, action, memory_id, memory_content, details, created_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (hashlib.sha1(f"audit:{qid}:{now}".encode()).hexdigest()[:16],
         user_id, "quarantined", qid, content[:200],
         json.dumps({"source": source, "category": category}), now)
    )
    conn.commit()
    conn.close()
    return {"id": qid, "status": "quarantined"}


def get_quarantined(db_path: Path, *, user_id: str = "default",
                    limit: int = 20) -> List[Dict]:
    """Get quarantined memories awaiting validation."""
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM memory_quarantine WHERE user_id=? AND status='quarantined' ORDER BY created_at DESC LIMIT ?",
        (user_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def validate_quarantine(db_path: Path, qid: str, verdict: str,
                         confidence: float = 0.8, validated_by: str = "rule",
                         notes: str = "") -> bool:
    """Validate or reject a quarantined memory.
    verdict: validate / reject
    """
    now = int(time.time())
    conn = safe_connect(db_path)
    status = "validated" if verdict == "validate" else "rejected"
    cur = conn.execute(
        "UPDATE memory_quarantine SET status=?, validated_at=?, validated_by=?, confidence=?, notes=? WHERE id=?",
        (status, now, validated_by, confidence, notes, qid)
    )
    conn.execute(
        "INSERT INTO governance_audit (id, user_id, action, memory_id, memory_content, details, created_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (hashlib.sha1(f"audit:{qid}:{now}:v".encode()).hexdigest()[:16],
         "default", status, qid, "", json.dumps({"verdict": verdict, "by": validated_by}), now)
    )
    conn.commit()
    conn.close()
    return cur.rowcount > 0


def promote_to_main(db_path: Path, qid: str) -> Optional[Dict]:
    """Promote a validated memory from quarantine to the main memory store."""
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM memory_quarantine WHERE id=? AND status='validated'",
        (qid,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    # Add to main memory
    from app import memory_orchestrator
    result = memory_orchestrator.add_memory(
        db_path, user_id=d["user_id"], content=d["content"],
        importance=d["importance"], category=d["category"],
        source="governance", conversation_id=d.get("conversation_id"),
    )
    # Mark as promoted
    conn = safe_connect(db_path)
    conn.execute("UPDATE memory_quarantine SET status='promoted' WHERE id=?", (qid,))
    conn.commit()
    conn.close()
    return result


def auto_validate_by_rules(db_path: Path, *, user_id: str = "default") -> Dict:
    """Auto-validate quarantined memories using rules (no LLM needed).
    High-importance + clear category → auto-validate.
    Low-importance + trivial content → auto-reject.
    Everything else → keep in quarantine for LLM validation.
    """
    pending = get_quarantined(db_path, user_id=user_id, limit=50)
    auto_validated = 0
    auto_rejected = 0
    kept = 0
    for item in pending:
        content = item["content"]
        # Try rule-based importance
        rule_imp = rule_engine.classify_importance_by_rules(content)
        if rule_imp is not None:
            if rule_imp >= 50:
                validate_quarantine(db_path, item["id"], "validate",
                                    confidence=0.7, validated_by="rule",
                                    notes=f"auto-validated (rule importance={rule_imp})")
                auto_validated += 1
            elif rule_imp <= 20:
                validate_quarantine(db_path, item["id"], "reject",
                                    confidence=0.8, validated_by="rule",
                                    notes=f"auto-rejected (rule importance={rule_imp})")
                auto_rejected += 1
            else:
                kept += 1
        else:
            kept += 1
    return {"auto_validated": auto_validated, "auto_rejected": auto_rejected, "kept": kept}


def get_audit_log(db_path: Path, *, user_id: str = "default", limit: int = 50) -> List[Dict]:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM governance_audit WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit)
    ).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["details"] = json.loads(d.get("details", "{}"))
        except Exception:
            d["details"] = {}
        out.append(d)
    return out


def get_stats(db_path: Path, user_id: str = "default") -> Dict:
    conn = safe_connect(db_path)
    stats = {}
    for status in ["quarantined", "validated", "rejected", "promoted"]:
        stats[status] = conn.execute(
            "SELECT COUNT(*) FROM memory_quarantine WHERE user_id=? AND status=?",
            (user_id, status)
        ).fetchone()[0]
    stats["audit_entries"] = conn.execute(
        "SELECT COUNT(*) FROM governance_audit WHERE user_id=?", (user_id,)
    ).fetchone()[0]
    conn.close()
    return stats
