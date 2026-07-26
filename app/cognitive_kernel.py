from __future__ import annotations
from app.llm_utils import extract_content as _extract_content
from app.db_utils import safe_connect


def _get_prompt(key, default):
    try:
        from app.main import get_prompt
        return get_prompt(key, default)
    except Exception:
        return default
"""
Cognitive Kernel for Cambium — the living layer beneath any model.

This module implements the seven cognitive primitives that make Cambium a
*persistent identity* rather than a stateless assistant:

1. Identity Graph   — self-narrative + evolution log (not a static role card)
2. Timeline         — shared history as a tree of formative events
3. Narrative        — story-form memories (not flat key-value facts)
4. Growth Engine    — strategy evolution from corrections + reflection
5. Goal Compass     — long-term goals + active commitments (cross-month)
6. World Model      — the user's world: projects, people, tools, causality
7. Self Model       — what the AI knows/doesn't, biases, confidence calibration
+ Concept Formation — emergent interest clustering from raw memories

Design philosophy:
- Identity is emergent, not prescribed. No role card. It grows from shared experience.
- Memory is narrative, not functional. Not "user_likes: TypeScript" but the story.
- Growth is one-way and irreversible. The AI doesn't reset.
- The cognitive kernel is model-agnostic. Models change; identity persists.

This module is self-contained. main.py wires it into chat_stream via the
Cognitive Organizer and exposes /api/cognitive/* endpoints.
"""
import json
import re
import sqlite3
import time
import hashlib
from typing import List, Dict, Optional, Any
from pathlib import Path
from collections import Counter, defaultdict


# ============================================================
# Timeline event categories — what kind of moment was this?
# Not just "user said X" but milestone/conflict/creation/growth/absence/reunion
# ============================================================
EVENT_CATEGORIES = [
    "milestone",      # 里程碑：第一个 star、一周年、第一次发布
    "conflict",       # 分歧：争论、不同意、pushback
    "creation",       # 共同创造：写了 README、做了设计、完成项目
    "growth",         # 成长：AI 或用户的变化、身份阶段转移
    "absence",        # 缺席：用户很久没来
    "reunion",        # 重逢：用户回来了
    "decision",       # 决策：选定方向、放弃方案
    "achievement",    # 成就：完成目标、达成里程碑
    "loss",           # 失去：删除项目、放弃目标
    "first",          # 第一次：第一次对话、第一次争论
    "daily",          # 日常：普通的一天
]

VALID_EVENT_CATEGORIES = set(EVENT_CATEGORIES)


COGNITIVE_SCHEMA = """
-- ============================================================
-- 1. IDENTITY GRAPH — the AI's living self-narrative
-- ============================================================
CREATE TABLE IF NOT EXISTS identity (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    name TEXT NOT NULL DEFAULT 'Cambium',
    born_at INTEGER NOT NULL,
    self_narrative TEXT NOT NULL DEFAULT '',
    personality_traits TEXT NOT NULL DEFAULT '[]',  -- JSON array
    relationship_with_user TEXT NOT NULL DEFAULT '',
    core_values TEXT NOT NULL DEFAULT '[]',
    current_phase TEXT NOT NULL DEFAULT 'forming',  -- forming/growing/mature/elder
    updated_at INTEGER NOT NULL,
    UNIQUE(user_id)
);

CREATE TABLE IF NOT EXISTS identity_evolution (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    shift_date INTEGER NOT NULL,
    shift_type TEXT NOT NULL DEFAULT 'observation',  -- observation/decision/milestone/correction
    description TEXT NOT NULL,
    significance INTEGER NOT NULL DEFAULT 50,  -- 0-100
    source TEXT NOT NULL DEFAULT 'auto',  -- auto/reflection/manual/user
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_identity_evo_user ON identity_evolution(user_id, shift_date);

-- ============================================================
-- 2. TIMELINE — shared history as formative events (tree structure)
-- ============================================================
CREATE TABLE IF NOT EXISTS timeline_events (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    occurred_at TEXT NOT NULL DEFAULT '',  -- human-readable: "2026-07" or "2026-07-26"
    occurred_ts INTEGER,  -- parsed timestamp if available
    category TEXT NOT NULL DEFAULT 'milestone',  -- milestone/decision/conflict/achievement/loss/first
    emotional_valence TEXT NOT NULL DEFAULT 'neutral',  -- positive/negative/neutral/bittersweet
    significance INTEGER NOT NULL DEFAULT 50,  -- 0-100, how formative
    parent_event TEXT,  -- for tree structure (causal/temporal links)
    related_entities TEXT NOT NULL DEFAULT '[]',  -- JSON array of entity names
    narrative TEXT NOT NULL DEFAULT '',  -- the story (not just facts)
    created_at INTEGER NOT NULL,
    UNIQUE(user_id, title, occurred_at)
);
CREATE INDEX IF NOT EXISTS idx_timeline_user ON timeline_events(user_id, occurred_ts);

-- ============================================================
-- 3. NARRATIVE — story-form memories (vs flat facts)
-- ============================================================
CREATE TABLE IF NOT EXISTS narratives (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    title TEXT NOT NULL,
    story TEXT NOT NULL,  -- the narrative text (second person, "你和他...")
    themes TEXT NOT NULL DEFAULT '[]',  -- JSON array of theme tags
    related_timeline_event TEXT,
    related_entities TEXT NOT NULL DEFAULT '[]',
    emotional_resonance TEXT NOT NULL DEFAULT 'neutral',
    importance INTEGER NOT NULL DEFAULT 50,
    created_at INTEGER NOT NULL,
    last_recalled INTEGER NOT NULL,
    recall_count INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_narratives_user ON narratives(user_id, importance);

-- ============================================================
-- 4. GROWTH ENGINE — strategy evolution from corrections
-- ============================================================
CREATE TABLE IF NOT EXISTS growth_insights (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    insight TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'communication',  -- communication/technical/emotional/strategic
    confidence REAL NOT NULL DEFAULT 0.5,  -- 0-1, how validated this insight is
    evidence_count INTEGER NOT NULL DEFAULT 0,
    source TEXT NOT NULL DEFAULT 'reflection',  -- reflection/correction/observation
    status TEXT NOT NULL DEFAULT 'forming',  -- forming/validated/integrated/superseded
    created_at INTEGER NOT NULL,
    last_reinforced INTEGER NOT NULL,
    superseded_by TEXT  -- if status=superseded, points to newer insight id
);
CREATE INDEX IF NOT EXISTS idx_growth_user ON growth_insights(user_id, status);

CREATE TABLE IF NOT EXISTS corrections (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    what_ai_did TEXT NOT NULL,
    what_user_wanted TEXT NOT NULL,
    correction_type TEXT NOT NULL DEFAULT 'style',  -- style/factual/strategic/emotional
    lesson TEXT NOT NULL DEFAULT '',
    created_at INTEGER NOT NULL,
    integrated INTEGER NOT NULL DEFAULT 0  -- 1 if fed into growth_insights
);
CREATE INDEX IF NOT EXISTS idx_corrections_user ON corrections(user_id, created_at);

-- ============================================================
-- 5. GOAL COMPASS — long-term goals + active commitments
-- ============================================================
CREATE TABLE IF NOT EXISTS long_term_goals (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    goal TEXT NOT NULL,
    rationale TEXT NOT NULL DEFAULT '',
    target_date TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active',  -- active/paused/achieved/abandoned/evolved
    progress INTEGER NOT NULL DEFAULT 0,  -- 0-100
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_goals_user ON long_term_goals(user_id, status);

CREATE TABLE IF NOT EXISTS commitments (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    description TEXT NOT NULL,
    due_date TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'open',  -- open/fulfilled/broken/superseded
    source TEXT NOT NULL DEFAULT 'conversation',  -- conversation/cron/manual
    created_at INTEGER NOT NULL,
    fulfilled_at INTEGER
);
CREATE INDEX IF NOT EXISTS idx_commitments_user ON commitments(user_id, status);

-- ============================================================
-- 6. WORLD MODEL — the user's world
-- ============================================================
CREATE TABLE IF NOT EXISTS world_entities (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    name TEXT NOT NULL,
    entity_type TEXT NOT NULL DEFAULT 'thing',  -- person/project/tool/place/concept/institution
    description TEXT NOT NULL DEFAULT '',
    attributes TEXT NOT NULL DEFAULT '{}',  -- JSON
    importance INTEGER NOT NULL DEFAULT 50,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    UNIQUE(user_id, name)
);
CREATE INDEX IF NOT EXISTS idx_world_entities_user ON world_entities(user_id, entity_type);

CREATE TABLE IF NOT EXISTS world_relations (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    subject TEXT NOT NULL,
    predicate TEXT NOT NULL,
    obj TEXT NOT NULL,
    evidence TEXT NOT NULL DEFAULT '',  -- why this relation exists
    confidence REAL NOT NULL DEFAULT 0.5,
    created_at INTEGER NOT NULL,
    UNIQUE(user_id, subject, predicate, obj)
);

CREATE TABLE IF NOT EXISTS causal_models (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    cause TEXT NOT NULL,
    effect TEXT NOT NULL,
    conditions TEXT NOT NULL DEFAULT '',
    confidence REAL NOT NULL DEFAULT 0.5,
    evidence_count INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL
);

-- ============================================================
-- 7. SELF MODEL — the AI's self-assessment
-- ============================================================
CREATE TABLE IF NOT EXISTS self_model (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    knows_well TEXT NOT NULL DEFAULT '[]',  -- JSON: domains where AI is confident
    doesnt_know TEXT NOT NULL DEFAULT '[]',  -- JSON: known blind spots
    biases TEXT NOT NULL DEFAULT '[]',  -- JSON: observed tendencies
    communication_preferences TEXT NOT NULL DEFAULT '[]',  -- JSON: what works with this user
    confidence_calibration REAL NOT NULL DEFAULT 0.5,  -- 0=overconfident, 1=well-calibrated
    last_updated INTEGER NOT NULL,
    UNIQUE(user_id)
);

-- ============================================================
-- 8. CONCEPT FORMATION — emergent interest clusters
-- ============================================================
CREATE TABLE IF NOT EXISTS concepts (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    name TEXT NOT NULL,  -- e.g., "复杂系统模拟"
    description TEXT NOT NULL DEFAULT '',
    member_entities TEXT NOT NULL DEFAULT '[]',  -- JSON: entity names that belong to this concept
    evidence_count INTEGER NOT NULL DEFAULT 0,
    first_observed INTEGER NOT NULL,
    last_reinforced INTEGER NOT NULL,
    confidence REAL NOT NULL DEFAULT 0.3,
    UNIQUE(user_id, name)
);
CREATE INDEX IF NOT EXISTS idx_concepts_user ON concepts(user_id, confidence);
"""


def init_cognitive_db(db_path: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = safe_connect(db_path)
    conn.executescript(COGNITIVE_SCHEMA)
    conn.commit()
    conn.close()


def _now() -> int:
    return int(time.time())


def _id(*parts) -> str:
    return hashlib.sha1(":".join(str(p) for p in parts).encode()).hexdigest()[:16]


def _parse_json(field: str, default):
    try:
        return json.loads(field) if field else default
    except Exception:
        return default


# ============================================================
# 1. IDENTITY GRAPH
# ============================================================

def get_identity(db_path: Path, user_id: str = "default") -> Dict:
    """Get or initialize the AI's identity for a user."""
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM identity WHERE user_id=?", (user_id,)).fetchone()
    if not row:
        # Initialize new identity
        iid = _id(user_id, "identity")
        now = _now()
        conn.execute(
            "INSERT INTO identity (id, user_id, name, born_at, self_narrative, updated_at) VALUES (?,?,?,?,?,?)",
            (iid, user_id, "Cambium", now, "", now)
        )
        conn.commit()
        row = conn.execute("SELECT * FROM identity WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    d = dict(row)
    d["personality_traits"] = _parse_json(d.get("personality_traits", "[]"), [])
    d["core_values"] = _parse_json(d.get("core_values", "[]"), [])
    return d


def update_identity(db_path: Path, user_id: str = "default", **fields) -> bool:
    allowed = {"name", "self_narrative", "personality_traits", "relationship_with_user",
               "core_values", "current_phase"}
    updates = {}
    for k, v in fields.items():
        if k in allowed:
            updates[k] = json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v
    if not updates:
        return False
    updates["updated_at"] = _now()
    # Ensure identity exists
    get_identity(db_path, user_id)
    sets = ", ".join(f"{k}=?" for k in updates)
    vals = list(updates.values()) + [user_id]
    conn = safe_connect(db_path)
    cur = conn.execute(f"UPDATE identity SET {sets} WHERE user_id=?", vals)
    conn.commit()
    conn.close()
    return cur.rowcount > 0


def record_identity_shift(db_path: Path, *, user_id: str = "default",
                          shift_type: str = "observation", description: str,
                          significance: int = 50, source: str = "auto") -> Dict:
    """Record an evolution event in the AI's identity (a 'shift')."""
    sid = _id(user_id, description, _now())
    now = _now()
    conn = safe_connect(db_path)
    conn.execute(
        "INSERT INTO identity_evolution (id, user_id, shift_date, shift_type, description, significance, source, created_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (sid, user_id, now, shift_type, description, significance, source, now)
    )
    conn.commit()
    conn.close()
    return {"id": sid, "shift_type": shift_type, "description": description}


def get_identity_evolution(db_path: Path, user_id: str = "default", limit: int = 50) -> List[Dict]:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM identity_evolution WHERE user_id=? ORDER BY shift_date DESC LIMIT ?",
        (user_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ============================================================
# 2. TIMELINE — shared history
# ============================================================

def add_timeline_event(db_path: Path, *, user_id: str = "default",
                       title: str, description: str = "",
                       occurred_at: str = "", category: str = "milestone",
                       emotional_valence: str = "neutral", significance: int = 50,
                       parent_event: Optional[str] = None,
                       related_entities: Optional[List[str]] = None,
                       narrative: str = "") -> Dict:
    # Validate category
    if category not in VALID_EVENT_CATEGORIES:
        category = "daily"  # fallback
    eid = _id(user_id, title, occurred_at)
    occurred_ts = _parse_human_date(occurred_at)
    entities = json.dumps(related_entities or [], ensure_ascii=False)
    now = _now()
    conn = safe_connect(db_path)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO timeline_events (id, user_id, title, description, occurred_at, occurred_ts, "
            "category, emotional_valence, significance, parent_event, related_entities, narrative, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (eid, user_id, title, description, occurred_at, occurred_ts, category,
             emotional_valence, significance, parent_event, entities, narrative, now)
        )
        conn.commit()
    finally:
        conn.close()
    # Publish event for event bus subscribers (co-experience harvesting, etc.)
    try:
        import asyncio
        from app import event_bus
        event_data = {
            "event_id": eid, "user_id": user_id, "title": title,
            "description": description[:200], "category": category,
            "significance": significance, "occurred_at": occurred_ts or now,
        }
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(event_bus.publish("timeline.event", event_data))
            else:
                loop.run_until_complete(event_bus.publish("timeline.event", event_data))
        except RuntimeError:
            pass  # no event loop
    except Exception:
        pass
    return {"id": eid, "title": title, "occurred_at": occurred_at}


def _parse_human_date(s: str) -> Optional[int]:
    """Parse '2026-07', '2026-07-26', '2026' to timestamp."""
    if not s:
        return None
    import re
    m = re.match(r"^(\d{4})(?:-(\d{1,2})(?:-(\d{1,2}))?)?$", s.strip())
    if not m:
        return None
    year = int(m.group(1))
    month = int(m.group(2)) if m.group(2) else 1
    day = int(m.group(3)) if m.group(3) else 1
    try:
        from datetime import datetime
        return int(datetime(year, month, day).timestamp())
    except Exception:
        return None


def get_timeline(db_path: Path, user_id: str = "default", limit: int = 50) -> List[Dict]:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM timeline_events WHERE user_id=? ORDER BY COALESCE(occurred_ts, created_at) ASC LIMIT ?",
        (user_id, limit)
    ).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["related_entities"] = _parse_json(d.get("related_entities", "[]"), [])
        out.append(d)
    return out


def search_timeline(db_path: Path, query: str, user_id: str = "default", top_k: int = 5) -> List[Dict]:
    q = query.lower()
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM timeline_events WHERE user_id=? ORDER BY significance DESC",
        (user_id,)
    ).fetchall()
    conn.close()
    scored = []
    for r in rows:
        d = dict(r)
        text = (d.get("title", "") + " " + d.get("description", "") + " " + d.get("narrative", "")).lower()
        if q in text:
            scored.append((d.get("significance", 50), d))
    scored.sort(key=lambda x: -x[0])
    return [d for _, d in scored[:top_k]]


# ============================================================
# 3. NARRATIVE — story-form memories
# ============================================================

def add_narrative(db_path: Path, *, user_id: str = "default",
                  title: str, story: str, themes: Optional[List[str]] = None,
                  related_timeline_event: Optional[str] = None,
                  related_entities: Optional[List[str]] = None,
                  emotional_resonance: str = "neutral",
                  importance: int = 50) -> Dict:
    nid = _id(user_id, title, _now())
    now = _now()
    conn = safe_connect(db_path)
    conn.execute(
        "INSERT INTO narratives (id, user_id, title, story, themes, related_timeline_event, "
        "related_entities, emotional_resonance, importance, created_at, last_recalled, recall_count) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (nid, user_id, title, story,
         json.dumps(themes or [], ensure_ascii=False),
         related_timeline_event,
         json.dumps(related_entities or [], ensure_ascii=False),
         emotional_resonance, importance, now, now, 0)
    )
    conn.commit()
    conn.close()
    return {"id": nid, "title": title}


def get_narratives(db_path: Path, user_id: str = "default", limit: int = 20) -> List[Dict]:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM narratives WHERE user_id=? ORDER BY importance DESC, created_at DESC LIMIT ?",
        (user_id, limit)
    ).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["themes"] = _parse_json(d.get("themes", "[]"), [])
        d["related_entities"] = _parse_json(d.get("related_entities", "[]"), [])
        out.append(d)
    return out


def search_narratives(db_path: Path, query: str, user_id: str = "default", top_k: int = 3) -> List[Dict]:
    q = query.lower()
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM narratives WHERE user_id=? ORDER BY importance DESC LIMIT 50",
        (user_id,)
    ).fetchall()
    conn.close()
    scored = []
    for r in rows:
        d = dict(r)
        text = (d.get("title", "") + " " + d.get("story", "")).lower()
        if q in text:
            scored.append((d.get("importance", 50), d))
    scored.sort(key=lambda x: -x[0])
    return [d for _, d in scored[:top_k]]


# ============================================================
# 4. GROWTH ENGINE — strategy evolution
# ============================================================

def add_growth_insight(db_path: Path, *, user_id: str = "default",
                       insight: str, category: str = "communication",
                       confidence: float = 0.5, source: str = "reflection") -> Dict:
    gid = _id(user_id, insight, _now())
    now = _now()
    conn = safe_connect(db_path)
    # Check if similar insight exists (substring match)
    existing = conn.execute(
        "SELECT id, confidence, evidence_count FROM growth_insights WHERE user_id=? AND insight LIKE ? AND status!='superseded'",
        (user_id, f"%{insight[:30]}%")
    ).fetchone()
    if existing:
        # Reinforce existing
        conn.execute(
            "UPDATE growth_insights SET confidence=MIN(1.0, confidence+0.1), evidence_count=evidence_count+1, last_reinforced=? WHERE id=?",
            (now, existing[0])
        )
        conn.commit()
        conn.close()
        return {"id": existing[0], "action": "reinforced", "confidence": existing[1] + 0.1}
    conn.execute(
        "INSERT INTO growth_insights (id, user_id, insight, category, confidence, evidence_count, source, status, created_at, last_reinforced) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (gid, user_id, insight, category, confidence, 1, source, "forming", now, now)
    )
    conn.commit()
    conn.close()
    return {"id": gid, "action": "created"}


def record_correction(db_path: Path, *, user_id: str = "default",
                      what_ai_did: str, what_user_wanted: str,
                      correction_type: str = "style", lesson: str = "") -> Dict:
    cid = _id(user_id, what_ai_did, _now())
    now = _now()
    conn = safe_connect(db_path)
    conn.execute(
        "INSERT INTO corrections (id, user_id, what_ai_did, what_user_wanted, correction_type, lesson, created_at, integrated) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (cid, user_id, what_ai_did, what_user_wanted, correction_type, lesson, now, 0)
    )
    conn.commit()
    conn.close()
    # Auto-extract a growth insight from the correction
    if lesson:
        add_growth_insight(db_path, user_id=user_id, insight=lesson,
                          category="communication" if correction_type == "style" else correction_type,
                          confidence=0.7, source="correction")
        conn = safe_connect(db_path)
        conn.execute("UPDATE corrections SET integrated=1 WHERE id=?", (cid,))
        conn.commit()
        conn.close()
    return {"id": cid}


def get_growth_insights(db_path: Path, user_id: str = "default",
                        status: Optional[str] = None, limit: int = 30) -> List[Dict]:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    if status:
        rows = conn.execute(
            "SELECT * FROM growth_insights WHERE user_id=? AND status=? ORDER BY confidence DESC, last_reinforced DESC LIMIT ?",
            (user_id, status, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM growth_insights WHERE user_id=? AND status!='superseded' ORDER BY confidence DESC, last_reinforced DESC LIMIT ?",
            (user_id, limit)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_corrections(db_path: Path, user_id: str = "default", limit: int = 20) -> List[Dict]:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM corrections WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ============================================================
# 5. GOAL COMPASS — long-term goals + commitments
# ============================================================

def add_long_term_goal(db_path: Path, *, user_id: str = "default",
                       goal: str, rationale: str = "", target_date: str = "") -> Dict:
    gid = _id(user_id, goal, _now())
    now = _now()
    conn = safe_connect(db_path)
    conn.execute(
        "INSERT INTO long_term_goals (id, user_id, goal, rationale, target_date, status, progress, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (gid, user_id, goal, rationale, target_date, "active", 0, now, now)
    )
    conn.commit()
    conn.close()
    return {"id": gid, "goal": goal}


def get_active_goals(db_path: Path, user_id: str = "default") -> List[Dict]:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM long_term_goals WHERE user_id=? AND status='active' ORDER BY updated_at DESC",
        (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_goal_progress(db_path: Path, goal_id: str, progress: int, status: Optional[str] = None) -> bool:
    now = _now()
    conn = safe_connect(db_path)
    if status:
        cur = conn.execute(
            "UPDATE long_term_goals SET progress=?, status=?, updated_at=? WHERE id=?",
            (progress, status, now, goal_id)
        )
    else:
        cur = conn.execute(
            "UPDATE long_term_goals SET progress=?, updated_at=? WHERE id=?",
            (progress, now, goal_id)
        )
    conn.commit()
    conn.close()
    return cur.rowcount > 0


def add_commitment(db_path: Path, *, user_id: str = "default",
                   description: str, due_date: str = "", source: str = "conversation") -> Dict:
    cid = _id(user_id, description, _now())
    now = _now()
    conn = safe_connect(db_path)
    conn.execute(
        "INSERT INTO commitments (id, user_id, description, due_date, status, source, created_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (cid, user_id, description, due_date, "open", source, now)
    )
    conn.commit()
    conn.close()
    return {"id": cid, "description": description}


def get_open_commitments(db_path: Path, user_id: str = "default") -> List[Dict]:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM commitments WHERE user_id=? AND status='open' ORDER BY created_at DESC",
        (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def fulfill_commitment(db_path: Path, commitment_id: str) -> bool:
    now = _now()
    conn = safe_connect(db_path)
    cur = conn.execute(
        "UPDATE commitments SET status='fulfilled', fulfilled_at=? WHERE id=?",
        (now, commitment_id)
    )
    conn.commit()
    conn.close()
    return cur.rowcount > 0


# ============================================================
# 6. WORLD MODEL — the user's world
# ============================================================

def upsert_world_entity(db_path: Path, *, user_id: str = "default",
                        name: str, entity_type: str = "thing",
                        description: str = "", attributes: Optional[Dict] = None,
                        importance: int = 50) -> str:
    now = _now()
    attrs = json.dumps(attributes or {}, ensure_ascii=False)
    conn = safe_connect(db_path)
    try:
        existing = conn.execute(
            "SELECT id FROM world_entities WHERE user_id=? AND name=?",
            (user_id, name)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE world_entities SET entity_type=?, description=?, attributes=?, importance=?, updated_at=? WHERE id=?",
                (entity_type, description, attrs, importance, now, existing[0])
            )
            eid = existing[0]
        else:
            eid = _id(user_id, name)
            conn.execute(
                "INSERT INTO world_entities (id, user_id, name, entity_type, description, attributes, importance, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (eid, user_id, name, entity_type, description, attrs, importance, now, now)
            )
        conn.commit()
    finally:
        conn.close()
    return eid


def add_world_relation(db_path: Path, *, user_id: str = "default",
                       subject: str, predicate: str, obj: str,
                       evidence: str = "", confidence: float = 0.5) -> bool:
    rid = _id(user_id, subject, predicate, obj)
    now = _now()
    conn = safe_connect(db_path)
    try:
        existing = conn.execute(
            "SELECT id, confidence FROM world_relations WHERE user_id=? AND subject=? AND predicate=? AND obj=?",
            (user_id, subject, predicate, obj)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE world_relations SET confidence=MIN(1.0, confidence+0.1) WHERE id=?",
                (existing[0],)
            )
        else:
            conn.execute(
                "INSERT INTO world_relations (id, user_id, subject, predicate, obj, evidence, confidence, created_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (rid, user_id, subject, predicate, obj, evidence, confidence, now)
            )
        conn.commit()
    finally:
        conn.close()
    return True


def add_causal_model(db_path: Path, *, user_id: str = "default",
                     cause: str, effect: str, conditions: str = "",
                     confidence: float = 0.5) -> Dict:
    cid = _id(user_id, cause, effect)
    now = _now()
    conn = safe_connect(db_path)
    try:
        existing = conn.execute(
            "SELECT id, evidence_count FROM causal_models WHERE user_id=? AND cause=? AND effect=?",
            (user_id, cause, effect)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE causal_models SET confidence=MIN(1.0, confidence+0.1), evidence_count=evidence_count+1 WHERE id=?",
                (existing[0],)
            )
        else:
            conn.execute(
                "INSERT INTO causal_models (id, user_id, cause, effect, conditions, confidence, evidence_count, created_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (cid, user_id, cause, effect, conditions, confidence, 1, now)
            )
        conn.commit()
    finally:
        conn.close()
    return {"id": cid, "cause": cause, "effect": effect}


def get_world_entities(db_path: Path, user_id: str = "default",
                       entity_type: Optional[str] = None) -> List[Dict]:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    if entity_type:
        rows = conn.execute(
            "SELECT * FROM world_entities WHERE user_id=? AND entity_type=? ORDER BY importance DESC",
            (user_id, entity_type)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM world_entities WHERE user_id=? ORDER BY importance DESC",
            (user_id,)
        ).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["attributes"] = _parse_json(d.get("attributes", "{}"), {})
        out.append(d)
    return out


def get_world_relations(db_path: Path, user_id: str = "default", limit: int = 100) -> List[Dict]:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM world_relations WHERE user_id=? ORDER BY confidence DESC LIMIT ?",
        (user_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_causal_models(db_path: Path, user_id: str = "default") -> List[Dict]:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM causal_models WHERE user_id=? ORDER BY confidence DESC",
        (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ============================================================
# 7. SELF MODEL — AI's self-assessment
# ============================================================

def get_self_model(db_path: Path, user_id: str = "default") -> Dict:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM self_model WHERE user_id=?", (user_id,)).fetchone()
    if not row:
        sid = _id(user_id, "self_model")
        now = _now()
        conn.execute(
            "INSERT INTO self_model (id, user_id, knows_well, doesnt_know, biases, communication_preferences, confidence_calibration, last_updated) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (sid, user_id, "[]", "[]", "[]", "[]", 0.5, now)
        )
        conn.commit()
        row = conn.execute("SELECT * FROM self_model WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    d = dict(row)
    d["knows_well"] = _parse_json(d.get("knows_well", "[]"), [])
    d["doesnt_know"] = _parse_json(d.get("doesnt_know", "[]"), [])
    d["biases"] = _parse_json(d.get("biases", "[]"), [])
    d["communication_preferences"] = _parse_json(d.get("communication_preferences", "[]"), [])
    return d


def update_self_model(db_path: Path, user_id: str = "default", **fields) -> bool:
    allowed = {"knows_well", "doesnt_know", "biases", "communication_preferences", "confidence_calibration"}
    updates = {}
    for k, v in fields.items():
        if k in allowed:
            updates[k] = json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v
    if not updates:
        return False
    updates["last_updated"] = _now()
    # Ensure exists
    get_self_model(db_path, user_id)
    sets = ", ".join(f"{k}=?" for k in updates)
    vals = list(updates.values()) + [user_id]
    conn = safe_connect(db_path)
    cur = conn.execute(f"UPDATE self_model SET {sets} WHERE user_id=?", vals)
    conn.commit()
    conn.close()
    return cur.rowcount > 0


# ============================================================
# 8. CONCEPT FORMATION — emergent interest clusters
# ============================================================

def add_concept(db_path: Path, *, user_id: str = "default",
                name: str, description: str = "",
                member_entities: Optional[List[str]] = None,
                confidence: float = 0.3) -> Dict:
    cid = _id(user_id, name)
    members = json.dumps(member_entities or [], ensure_ascii=False)
    now = _now()
    conn = safe_connect(db_path)
    try:
        existing = conn.execute(
            "SELECT id, evidence_count FROM concepts WHERE user_id=? AND name=?",
            (user_id, name)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE concepts SET confidence=MIN(1.0, confidence+0.1), evidence_count=evidence_count+1, last_reinforced=?, member_entities=? WHERE id=?",
                (now, members, existing[0])
            )
            cid = existing[0]
        else:
            conn.execute(
                "INSERT INTO concepts (id, user_id, name, description, member_entities, evidence_count, first_observed, last_reinforced, confidence) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (cid, user_id, name, description, members, 1, now, now, confidence)
            )
        conn.commit()
    finally:
        conn.close()
    return {"id": cid, "name": name}


def get_concepts(db_path: Path, user_id: str = "default", min_confidence: float = 0.0) -> List[Dict]:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM concepts WHERE user_id=? AND confidence>=? ORDER BY confidence DESC, evidence_count DESC",
        (user_id, min_confidence)
    ).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["member_entities"] = _parse_json(d.get("member_entities", "[]"), [])
        out.append(d)
    return out


# ============================================================
# COGNITIVE ORGANIZER — weaves all modules into context
# ============================================================

def build_cognitive_context(db_path: Path, *, user_id: str = "default",
                             query: str, conversation_id: Optional[str] = None,
                             max_chars: int = 2000) -> Dict:
    """Weave the cognitive kernel into a context section for the LLM.

    Unlike the memory orchestrator (which handles factual recall), this builds
    the AI's *sense of self and shared history*: identity, timeline, narrative,
    growth, goals, world model, self model.

    Priority order:
    1. Identity self-narrative (who the AI is, in its own words)
    2. Active long-term goals + open commitments (what we're working toward)
    3. Relevant timeline events (shared history)
    4. Relevant narratives (stories, not facts)
    5. Top growth insights (what the AI has learned about this user)
    6. World model entities (the user's world)
    7. Self model (AI's confidence + blind spots)
    """
    sections = []
    total = 0

    # 1. Identity
    identity = get_identity(db_path, user_id)
    if identity.get("self_narrative"):
        sections.append(f"【我是谁（身份）】\n{identity['self_narrative']}")
        total += len(identity["self_narrative"])
    elif identity.get("name"):
        sections.append(f"【我是谁（身份）】\n你是 {identity['name']}，与这位用户共同成长的 AI 搭档。")
        total += 50

    # 2. Goals + commitments
    goals = get_active_goals(db_path, user_id)
    commitments = get_open_commitments(db_path, user_id)
    goal_parts = []
    if goals:
        goal_parts.append("我们正在追求：\n" + "\n".join(f"- {g['goal']}" for g in goals[:3]))
    if commitments:
        goal_parts.append("我答应过的事：\n" + "\n".join(f"- {c['description']}" for c in commitments[:3]))
    if goal_parts:
        text = "\n".join(goal_parts)
        sections.append(f"【共同目标与承诺】\n{text}")
        total += len(text)

    # 3. Timeline (relevant to query)
    if query and total < max_chars * 0.6:
        timeline = search_timeline(db_path, query, user_id, top_k=3)
        if timeline:
            text = "\n".join(f"- [{t.get('occurred_at', '?')}] {t['title']}" for t in timeline)
            sections.append(f"【共同历史（时间线）】\n{text}")
            total += len(text)

    # 4. Narratives (relevant stories)
    if query and total < max_chars * 0.7:
        narratives = search_narratives(db_path, query, user_id, top_k=2)
        if narratives:
            text = "\n".join(f"- {n['title']}: {n['story'][:200]}" for n in narratives)
            sections.append(f"【我们的故事】\n{text}")
            total += len(text)

    # 5. Growth insights (what AI learned)
    insights = get_growth_insights(db_path, user_id, status="validated", limit=3)
    if not insights:
        insights = get_growth_insights(db_path, user_id, limit=3)
    if insights:
        text = "\n".join(f"- {i['insight']}" for i in insights if i.get("confidence", 0) >= 0.5)
        if text:
            sections.append(f"【我学到的（成长）】\n{text}")
            total += len(text)

    # 6. World model (top entities)
    if total < max_chars * 0.85:
        entities = get_world_entities(db_path, user_id)
        if entities:
            text = "\n".join(f"- {e['name']} ({e['entity_type']})" for e in entities[:8])
            sections.append(f"【你的世界】\n{text}")
            total += len(text)

    # 7. Self model (compact)
    sm = get_self_model(db_path, user_id)
    sm_parts = []
    if sm.get("knows_well"):
        sm_parts.append("我擅长: " + ", ".join(sm["knows_well"][:3]))
    if sm.get("doesnt_know"):
        sm_parts.append("我不确定: " + ", ".join(sm["doesnt_know"][:3]))
    if sm.get("communication_preferences"):
        sm_parts.append("你偏好的方式: " + "; ".join(sm["communication_preferences"][:2]))
    if sm_parts and total < max_chars:
        text = "; ".join(sm_parts)
        sections.append(f"【自我认知】\n{text}")

    return {
        "sections": sections,
        "combined": "\n\n".join(sections) if sections else "",
        "total_chars": total,
    }


# ============================================================
# LLM-driven cognitive updates
# ============================================================

COGNITIVE_EXTRACTION_PROMPT_DEFAULT = """你是 Cambium 的认知内核。从最近的对话中提取认知层面的更新。

【当前身份】
{identity}

【当前目标】
{goals}

【最近对话】
{conversation}

【任务】
从对话中提取以下认知更新（只输出有变化的字段，没有则对应空数组或空对象）：

1. identity_shifts: 身份演化事件（如"第一次参与架构决策"、"开始主动提出反对意见"）
   [{{shift_type, description, significance}}]
2. timeline_events: 值得记入共同时间线的事件（里程碑/决策/冲突/成就）
   [{{title, occurred_at, category, significance, narrative}}]
3. narratives: 故事性记忆（不是事实，而是有情节的故事）
   [{{title, story, themes, emotional_resonance}}]
4. growth_insights: 从这次交互中学到的（如"用户不喜欢太多选项"）
   [{{insight, category, confidence}}]
5. corrections: 用户纠正了 AI 的地方
   [{{what_ai_did, what_user_wanted, lesson}}]
6. world_entities: 用户世界中出现的实体（人/项目/工具/地点）
   [{{name, entity_type, description}}]
7. world_relations: 实体间关系
   [{{subject, predicate, obj}}]
8. long_term_goals: 用户提到的长期目标
   [{{goal, rationale}}]
9. commitments: AI 答应要做的事
   [{{description, due_date}}]
10. concepts: 兴趣概念聚类（如从多个具体游戏抽象出"复杂系统模拟"）
    [{{name, description, member_entities}}]

输出 JSON：
```json
{{
  "identity_shifts": [],
  "timeline_events": [],
  "narratives": [],
  "growth_insights": [],
  "corrections": [],
  "world_entities": [],
  "world_relations": [],
  "long_term_goals": [],
  "commitments": [],
  "concepts": []
}}
```

只输出 JSON。"""


async def extract_cognitive_updates(db_path: Path, *, user_id: str,
                                      conversation: str, http_client, api_cfg: Dict,
                                      max_retries: int = 2) -> Dict:
    """Ask the LLM to extract cognitive updates from recent conversation.
    Includes retry on JSON parse failure + failure logging to a queue table."""
    if len(conversation) < 100:
        return {"extracted": False, "reason": "conversation too short"}
    last_error = None
    for attempt in range(max_retries):
        try:
            identity = get_identity(db_path, user_id)
            goals = get_active_goals(db_path, user_id)
            identity_str = identity.get("self_narrative", "") or f"{identity.get('name', 'Cambium')} (forming)"
            goals_str = "\n".join(f"- {g['goal']}" for g in goals[:3]) or "(无)"

            messages = [{"role": "user", "content": _get_prompt("prompt_cognitive_extraction", COGNITIVE_EXTRACTION_PROMPT_DEFAULT).format(
                identity=identity_str,
                goals=goals_str,
                conversation=conversation[:4000],
            )}]
            # On retry, add corrective instruction
            if attempt > 0:
                messages.append({"role": "assistant", "content": "（上次回复格式有误）"})
                messages.append({"role": "user", "content": "请只输出纯 JSON，不要其他文字。"})

            payload = {
                "model": api_cfg["api_model"],
                "messages": messages,
                "temperature": 0.3,
                "max_tokens": 1500,
                "stream": False,
                "enable_thinking": False,
            }
            resp = await http_client.post(
                f"{api_cfg['api_base_url']}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {api_cfg['api_key']}", "Content-Type": "application/json"},
                timeout=60.0,
            )
            resp.raise_for_status()
            data = resp.json()
            text = _extract_content(data)
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if not m:
                last_error = f"no JSON in response (attempt {attempt+1})"
                continue
            try:
                result = json.loads(m.group(0))
            except json.JSONDecodeError as e:
                last_error = f"invalid JSON: {e} (attempt {attempt+1})"
                continue

            # Apply all extracted updates
            applied = {"identity_shifts": 0, "timeline_events": 0, "narratives": 0,
                       "growth_insights": 0, "corrections": 0, "world_entities": 0,
                       "world_relations": 0, "long_term_goals": 0, "commitments": 0, "concepts": 0}

            for shift in result.get("identity_shifts", []):
                if isinstance(shift, dict) and shift.get("description"):
                    try:
                        sig_val = shift.get("significance", 50)
                        try:
                            sig = int(sig_val)
                        except (ValueError, TypeError):
                            sig = 50
                        record_identity_shift(db_path, user_id=user_id,
                            shift_type=str(shift.get("shift_type", "observation")),
                            description=str(shift["description"]),
                            significance=sig,
                            source="reflection")
                        applied["identity_shifts"] += 1
                    except Exception as e:
                        print(f"[cognitive] identity shift add failed: {e}")

            for ev in result.get("timeline_events", []):
                if isinstance(ev, dict) and ev.get("title"):
                    try:
                        add_timeline_event(db_path, user_id=user_id,
                            title=str(ev["title"]),
                            description=str(ev.get("description", "")),
                            occurred_at=str(ev.get("occurred_at", "")),
                            category=str(ev.get("category", "milestone")),
                            significance=int(ev.get("significance", 50)) if str(ev.get("significance", "50")).isdigit() or str(ev.get("significance", "50")).replace(".","").isdigit() else 50,
                            narrative=str(ev.get("narrative", "")))
                        applied["timeline_events"] += 1
                    except Exception as e:
                        print(f"[cognitive] timeline event add failed: {e}")

            for n in result.get("narratives", []):
                if isinstance(n, dict) and n.get("title") and n.get("story"):
                    add_narrative(db_path, user_id=user_id,
                        title=n["title"], story=n["story"],
                        themes=n.get("themes", []),
                        emotional_resonance=n.get("emotional_resonance", "neutral"),
                        importance=int(n.get("importance", 50)))
                    applied["narratives"] += 1

            for gi in result.get("growth_insights", []):
                if isinstance(gi, dict) and gi.get("insight"):
                    add_growth_insight(db_path, user_id=user_id,
                        insight=gi["insight"],
                        category=gi.get("category", "communication"),
                        confidence=float(gi.get("confidence", 0.5)),
                        source="reflection")
                    applied["growth_insights"] += 1

            for c in result.get("corrections", []):
                if isinstance(c, dict) and c.get("what_ai_did"):
                    record_correction(db_path, user_id=user_id,
                        what_ai_did=c["what_ai_did"],
                        what_user_wanted=c.get("what_user_wanted", ""),
                        correction_type=c.get("correction_type", "style"),
                        lesson=c.get("lesson", ""))
                    applied["corrections"] += 1

            for we in result.get("world_entities", []):
                if isinstance(we, dict) and we.get("name"):
                    upsert_world_entity(db_path, user_id=user_id,
                        name=we["name"],
                        entity_type=we.get("entity_type", "thing"),
                        description=we.get("description", ""))
                    applied["world_entities"] += 1

            for wr in result.get("world_relations", []):
                if isinstance(wr, dict) and wr.get("subject") and wr.get("obj"):
                    add_world_relation(db_path, user_id=user_id,
                        subject=wr["subject"],
                        predicate=wr.get("predicate", "related_to"),
                        obj=wr["obj"],
                        evidence=wr.get("evidence", ""))
                    applied["world_relations"] += 1

            for g in result.get("long_term_goals", []):
                if isinstance(g, dict) and g.get("goal"):
                    add_long_term_goal(db_path, user_id=user_id,
                        goal=g["goal"],
                        rationale=g.get("rationale", ""),
                        target_date=g.get("target_date", ""))
                    applied["long_term_goals"] += 1

            for cm in result.get("commitments", []):
                if isinstance(cm, dict) and cm.get("description"):
                    add_commitment(db_path, user_id=user_id,
                        description=cm["description"],
                        due_date=cm.get("due_date", ""))
                    applied["commitments"] += 1

            for con in result.get("concepts", []):
                if isinstance(con, dict) and con.get("name"):
                    add_concept(db_path, user_id=user_id,
                        name=con["name"],
                        description=con.get("description", ""),
                        member_entities=con.get("member_entities", []))
                    applied["concepts"] += 1

            return {"extracted": True, "applied": applied}
        except Exception as e:
            last_error = str(e)
            if attempt < max_retries - 1:
                import asyncio
                await asyncio.sleep(1)
                continue
    # All retries failed — log to failure queue for later retry
    _log_failed_extraction(db_path, user_id, conversation[:500], last_error or "unknown")
    print(f"[cognitive] extraction failed after {max_retries} retries: {last_error}")
    return {"extracted": False, "error": last_error, "logged_to_queue": True}


def _log_failed_extraction(db_path: Path, user_id: str, conversation_snippet: str, error: str):
    """Log a failed cognitive extraction to a queue table for later retry."""
    try:
        conn = safe_connect(db_path)
        fid = hashlib.sha1(f"{user_id}:{time.time()}".encode()).hexdigest()[:16]
        conn.execute(
            "CREATE TABLE IF NOT EXISTS failed_extractions ("
            "id TEXT PRIMARY KEY, user_id TEXT, conversation_snippet TEXT, error TEXT, "
            "created_at INTEGER, retried INTEGER DEFAULT 0)"
        )
        conn.execute(
            "INSERT INTO failed_extractions (id, user_id, conversation_snippet, error, created_at) "
            "VALUES (?,?,?,?,?)",
            (fid, user_id, conversation_snippet, error, int(time.time()))
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[cognitive] failed to log extraction failure: {e}")


# ============================================================
# Dashboard stats
# ============================================================

def get_cognitive_stats(db_path: Path, user_id: str = "default") -> Dict:
    conn = safe_connect(db_path)
    stats = {}
    stats["identity_shifts"] = conn.execute(
        "SELECT COUNT(*) FROM identity_evolution WHERE user_id=?", (user_id,)
    ).fetchone()[0]
    stats["timeline_events"] = conn.execute(
        "SELECT COUNT(*) FROM timeline_events WHERE user_id=?", (user_id,)
    ).fetchone()[0]
    stats["narratives"] = conn.execute(
        "SELECT COUNT(*) FROM narratives WHERE user_id=?", (user_id,)
    ).fetchone()[0]
    stats["growth_insights"] = conn.execute(
        "SELECT COUNT(*) FROM growth_insights WHERE user_id=? AND status!='superseded'",
        (user_id,)
    ).fetchone()[0]
    stats["corrections"] = conn.execute(
        "SELECT COUNT(*) FROM corrections WHERE user_id=?", (user_id,)
    ).fetchone()[0]
    stats["active_goals"] = conn.execute(
        "SELECT COUNT(*) FROM long_term_goals WHERE user_id=? AND status='active'",
        (user_id,)
    ).fetchone()[0]
    stats["open_commitments"] = conn.execute(
        "SELECT COUNT(*) FROM commitments WHERE user_id=? AND status='open'",
        (user_id,)
    ).fetchone()[0]
    stats["world_entities"] = conn.execute(
        "SELECT COUNT(*) FROM world_entities WHERE user_id=?", (user_id,)
    ).fetchone()[0]
    stats["world_relations"] = conn.execute(
        "SELECT COUNT(*) FROM world_relations WHERE user_id=?", (user_id,)
    ).fetchone()[0]
    stats["causal_models"] = conn.execute(
        "SELECT COUNT(*) FROM causal_models WHERE user_id=?", (user_id,)
    ).fetchone()[0]
    stats["concepts"] = conn.execute(
        "SELECT COUNT(*) FROM concepts WHERE user_id=?", (user_id,)
    ).fetchone()[0]
    # Identity phase
    conn.row_factory = sqlite3.Row
    id_row = conn.execute("SELECT name, current_phase, born_at FROM identity WHERE user_id=?", (user_id,)).fetchone()
    stats["identity_name"] = id_row["name"] if id_row else "Cambium"
    stats["identity_phase"] = id_row["current_phase"] if id_row else "forming"
    stats["identity_born"] = id_row["born_at"] if id_row else 0
    conn.close()
    return stats
