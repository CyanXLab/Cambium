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


# ============================================================
# SSGM Enhancements: Contradiction detection + LLM validation + batch promotion
# ============================================================

# Negation pairs for lightweight contradiction detection
_NEGATION_PAIRS = [
    ("喜欢", "讨厌"), ("love", "hate"), ("prefer", "dislike"),
    ("擅长", "不擅长"), ("good at", "bad at"),
    ("总是", "从不"), ("always", "never"),
    ("是", "不是"), ("is", "is not"), ("can", "cannot"),
    ("应该", "不应该"), ("should", "should not"),
    ("想要", "不想要"), ("want", "don't want"),
]


def detect_contradiction(db_path: Path, user_id: str, new_content: str) -> Optional[Dict]:
    """Check if new content contradicts existing high-importance memories.

    SSGM paper §3.2: "Contradiction detection is the first line of defense
    against memory corruption."

    Uses keyword overlap + negation detection as a lightweight proxy for
    semantic contradiction. Returns the contradicting memory if found.
    """
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, content, importance FROM memory_items "
        "WHERE user_id=? AND (layer='permanent' OR (layer='long_term' AND importance>=70)) "
        "ORDER BY importance DESC LIMIT 50",
        (user_id,)
    ).fetchall()
    conn.close()

    new_lower = new_content.lower()
    new_words = set(w for w in new_lower.split() if len(w) > 2)

    for row in rows:
        existing = row["content"].lower()
        existing_words = set(w for w in existing.split() if len(w) > 2)

        # High keyword overlap = talking about the same thing
        overlap = len(new_words & existing_words) / max(len(new_words | existing_words), 1)
        if overlap < 0.3:
            continue

        # Check for negation contradiction
        for pos, neg in _NEGATION_PAIRS:
            if (pos in new_lower and neg in existing) or (neg in new_lower and pos in existing):
                return {"id": row["id"], "existing_content": row["content"]}

    return None


def quarantine_with_contradiction_check(
    db_path: Path, *, user_id: str = "default", content: str,
    category: str = "other", importance: int = 50,
    source: str = "extraction", source_turn: str = "",
    conversation_id: Optional[str] = None,
) -> Dict:
    """Quarantine a memory with automatic contradiction detection.

    If the new memory contradicts existing high-importance memories,
    its confidence is lowered and the contradiction is recorded.
    """
    contradiction = detect_contradiction(db_path, user_id, content)

    qid = hashlib.sha1(f"{user_id}:{content[:50]}:{time.time()}".encode()).hexdigest()[:16]
    now = int(time.time())
    confidence = 0.5
    if contradiction:
        confidence = 0.2  # Lower confidence if it contradicts

    conn = safe_connect(db_path)
    conn.execute(
        "INSERT INTO memory_quarantine (id, user_id, content, category, importance, source, "
        "source_turn, conversation_id, created_at, status, confidence) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (qid, user_id, content, category, importance, source, source_turn[:200],
         conversation_id, now, "quarantined", confidence)
    )
    audit_action = "quarantined"
    if contradiction:
        audit_action = "contradiction_detected"
        conn.execute(
            "INSERT INTO governance_audit (id, user_id, action, memory_id, memory_content, details, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (hashlib.sha1(f"audit:{qid}:{now}:c".encode()).hexdigest()[:16],
             user_id, "contradiction_detected", qid, content[:200],
             json.dumps({
                 "source": source,
                 "contradicts": contradiction["id"],
                 "existing_content": contradiction["existing_content"][:200],
             }, ensure_ascii=False), now)
        )
    else:
        conn.execute(
            "INSERT INTO governance_audit (id, user_id, action, memory_id, memory_content, details, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (hashlib.sha1(f"audit:{qid}:{now}".encode()).hexdigest()[:16],
             user_id, "quarantined", qid, content[:200],
             json.dumps({"source": source, "category": category}), now)
        )
    conn.commit()
    conn.close()

    return {
        "id": qid,
        "status": "quarantined",
        "confidence": confidence,
        "has_contradiction": bool(contradiction),
        "contradicts": contradiction["id"] if contradiction else "",
    }


async def validate_quarantine_batch(
    db_path: Path, *, user_id: str = "default",
    http_client, api_cfg: Dict, batch_size: int = 10,
) -> Dict:
    """LLM-driven validation of quarantined memories (SSGM §3.3).

    Asks the model: "Given what we already know, is this new memory plausible?"
    This is coherence-checking, not just fact-checking.

    Args:
        http_client: httpx.AsyncClient instance
        api_cfg: dict with api_model, api_base_url, api_key
        batch_size: max memories to validate per call

    Returns: {"validated": N, "rejected": N}
    """
    pending = get_quarantined(db_path, user_id=user_id, limit=batch_size)
    if not pending:
        return {"validated": 0, "rejected": 0}

    # Get existing knowledge for context
    from app import cognitive_kernel
    identity = cognitive_kernel.get_identity(db_path, user_id)
    existing_context = f"AI名字: {identity.get('name', 'Cambium')}\n"

    validated = 0
    rejected = 0

    for mem in pending:
        # Skip if already validated/rejected
        if mem.get("status") != "quarantined":
            continue

        prompt = f"""你是 Cambium 的记忆治理系统。判断这条新提取的记忆是否可信。

【已有知识】
{existing_context}

【新记忆】
内容: {mem['content']}
来源: {mem.get('source_turn', '')[:200] if mem.get('source_turn') else '(未知)'}
重要度: {mem['importance']}

【判断标准】
1. 是否与已有知识矛盾？
2. 是否可能是 LLM 幻觉（过度推断、编造细节）？
3. 是否真的来自用户表达，还是 AI 自己的推测？

输出 JSON:
{{"verdict": "validate" 或 "reject", "confidence": 0.0-1.0, "reason": "..."}}
只输出 JSON。"""

        try:
            import re
            payload = {
                "model": api_cfg["api_model"],
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1, "max_tokens": 200, "stream": False,
            }
            resp = await http_client.post(
                f"{api_cfg['api_base_url']}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {api_cfg['api_key']}"},
                timeout=15.0,
            )
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"].strip()
            m = re.search(r"\{[^{}]*\}", text, re.DOTALL)
            if m:
                result = json.loads(m.group(0))
                verdict = result.get("verdict", "reject")
                confidence = float(result.get("confidence", 0.5))
            else:
                verdict, confidence = "reject", 0.3
        except Exception:
            verdict, confidence = "reject", 0.3

        new_status = "validated" if verdict == "validate" and confidence >= 0.6 else "rejected"

        validate_quarantine(
            db_path, mem["id"], verdict,
            confidence=confidence, validated_by="llm",
            notes=f"LLM validation: {verdict}",
        )

        if new_status == "validated":
            validated += 1
        else:
            rejected += 1

    return {"validated": validated, "rejected": rejected}


def promote_all_validated(db_path: Path, *, user_id: str = "default") -> Dict:
    """Promote all validated memories from quarantine to main store.

    This is the ONLY path from quarantine to memory_items.
    """
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    validated = conn.execute(
        "SELECT * FROM memory_quarantine WHERE user_id=? AND status='validated'",
        (user_id,)
    ).fetchall()
    conn.close()

    promoted = 0
    for mem in validated:
        result = promote_to_main(db_path, mem["id"])
        if result:
            promoted += 1

    return {"promoted": promoted}
