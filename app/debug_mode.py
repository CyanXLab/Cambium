"""
Debug Mode for Cambium — hidden testing & inspection panel.

Activated by: clicking the "关于 Cambium" button 5 times rapidly,
or via API: POST /api/debug/toggle

Provides:
1. Time acceleration — simulate hours/days/weeks passing instantly
2. Manual trigger of any Life Loop cycle
3. View/edit all AI-generated data (memories, identity, narratives, etc.)
4. Reset/clear specific data stores
5. System health dashboard
"""
from __future__ import annotations
import json
import time
import sqlite3
from typing import Dict, List, Optional
from pathlib import Path
from app.db_utils import safe_connect


def is_debug_enabled(db_path: Path) -> bool:
    """Check if debug mode is enabled."""
    conn = safe_connect(db_path, row_factory=False)
    try:
        row = conn.execute("SELECT value FROM settings WHERE key='debug_mode'").fetchone()
        return row is not None and row[0] == "true"
    except Exception:
        return False
    finally:
        conn.close()


def set_debug_enabled(db_path: Path, enabled: bool):
    """Enable/disable debug mode."""
    conn = safe_connect(db_path, row_factory=False)
    conn.execute(
        "INSERT INTO settings (key, value) VALUES ('debug_mode', ?) ON CONFLICT(key) DO UPDATE SET value=?",
        ("true" if enabled else "false", "true" if enabled else "false")
    )
    conn.commit()
    conn.close()


def accelerate_time(db_path: Path, seconds: int) -> Dict:
    """Simulate time passing by adjusting Life Loop last_run timestamps.
    This makes the Life Loop think N seconds have passed, so the next check
    will trigger the appropriate cycles."""
    conn = safe_connect(db_path, row_factory=False)
    # Get current last_run times
    row = conn.execute("SELECT value FROM settings WHERE key='life_loop_last_runs'").fetchone()
    if row:
        last_runs = json.loads(row[0])
    else:
        last_runs = {"hourly": 0, "daily": 0, "weekly": 0, "monthly": 0}
    # Shift all timestamps back by `seconds`
    for key in last_runs:
        if last_runs[key] > 0:
            last_runs[key] = max(0, last_runs[key] - seconds)
    conn.execute(
        "INSERT INTO settings (key, value) VALUES ('life_loop_last_runs', ?) ON CONFLICT(key) DO UPDATE SET value=?",
        (json.dumps(last_runs), json.dumps(last_runs))
    )
    conn.commit()
    conn.close()
    return {"accelerated_seconds": seconds, "new_last_runs": last_runs}


def get_all_ai_data(db_path: Path, user_id: str = "default") -> Dict:
    """Get ALL AI-generated data for inspection."""
    conn = safe_connect(db_path, row_factory=False)
    data = {}

    # Memory items
    try:
        rows = conn.execute("SELECT * FROM memory_items WHERE user_id=? ORDER BY importance DESC", (user_id,)).fetchall()
        data["memories"] = [dict(zip([d[0] for d in conn.execute("SELECT * FROM memory_items LIMIT 0").description], r)) for r in rows]
    except Exception:
        data["memories"] = []

    # Memory summary
    try:
        row = conn.execute("SELECT * FROM memory_summary WHERE user_id=?", (user_id,)).fetchone()
        if row:
            data["memory_summary"] = dict(zip([d[0] for d in conn.execute("SELECT * FROM memory_summary LIMIT 0").description], row))
        else:
            data["memory_summary"] = None
    except Exception:
        data["memory_summary"] = None

    # Identity
    try:
        row = conn.execute("SELECT * FROM identity WHERE user_id=?", (user_id,)).fetchone()
        if row:
            data["identity"] = dict(zip([d[0] for d in conn.execute("SELECT * FROM identity LIMIT 0").description], row))
        else:
            data["identity"] = None
    except Exception:
        data["identity"] = None

    # Identity evolution
    try:
        rows = conn.execute("SELECT * FROM identity_evolution WHERE user_id=? ORDER BY created_at DESC LIMIT 20", (user_id,)).fetchall()
        data["identity_evolution"] = [dict(zip([d[0] for d in conn.execute("SELECT * FROM identity_evolution LIMIT 0").description], r)) for r in rows]
    except Exception:
        data["identity_evolution"] = []

    # Timeline events
    try:
        rows = conn.execute("SELECT * FROM timeline_events WHERE user_id=? ORDER BY created_at DESC LIMIT 20", (user_id,)).fetchall()
        data["timeline"] = [dict(zip([d[0] for d in conn.execute("SELECT * FROM timeline_events LIMIT 0").description], r)) for r in rows]
    except Exception:
        data["timeline"] = []

    # Narratives
    try:
        rows = conn.execute("SELECT * FROM narratives WHERE user_id=? ORDER BY importance DESC LIMIT 20", (user_id,)).fetchall()
        data["narratives"] = [dict(zip([d[0] for d in conn.execute("SELECT * FROM narratives LIMIT 0").description], r)) for r in rows]
    except Exception:
        data["narratives"] = []

    # Growth insights
    try:
        rows = conn.execute("SELECT * FROM growth_insights WHERE user_id=? AND status!='superseded' ORDER BY confidence DESC LIMIT 20", (user_id,)).fetchall()
        data["growth_insights"] = [dict(zip([d[0] for d in conn.execute("SELECT * FROM growth_insights LIMIT 0").description], r)) for r in rows]
    except Exception:
        data["growth_insights"] = []

    # Corrections
    try:
        rows = conn.execute("SELECT * FROM corrections WHERE user_id=? ORDER BY created_at DESC LIMIT 10", (user_id,)).fetchall()
        data["corrections"] = [dict(zip([d[0] for d in conn.execute("SELECT * FROM corrections LIMIT 0").description], r)) for r in rows]
    except Exception:
        data["corrections"] = []

    # Goals
    try:
        rows = conn.execute("SELECT * FROM long_term_goals WHERE user_id=? AND status='active'", (user_id,)).fetchall()
        data["goals"] = [dict(zip([d[0] for d in conn.execute("SELECT * FROM long_term_goals LIMIT 0").description], r)) for r in rows]
    except Exception:
        data["goals"] = []

    # Commitments
    try:
        rows = conn.execute("SELECT * FROM commitments WHERE user_id=? AND status='open'", (user_id,)).fetchall()
        data["commitments"] = [dict(zip([d[0] for d in conn.execute("SELECT * FROM commitments LIMIT 0").description], r)) for r in rows]
    except Exception:
        data["commitments"] = []

    # World entities
    try:
        rows = conn.execute("SELECT * FROM world_entities WHERE user_id=? ORDER BY importance DESC LIMIT 20", (user_id,)).fetchall()
        data["world_entities"] = [dict(zip([d[0] for d in conn.execute("SELECT * FROM world_entities LIMIT 0").description], r)) for r in rows]
    except Exception:
        data["world_entities"] = []

    # Self model
    try:
        row = conn.execute("SELECT * FROM self_model WHERE user_id=?", (user_id,)).fetchone()
        if row:
            data["self_model"] = dict(zip([d[0] for d in conn.execute("SELECT * FROM self_model LIMIT 0").description], row))
        else:
            data["self_model"] = None
    except Exception:
        data["self_model"] = None

    # Concepts
    try:
        rows = conn.execute("SELECT * FROM concepts WHERE user_id=? ORDER BY confidence DESC LIMIT 10", (user_id,)).fetchall()
        data["concepts"] = [dict(zip([d[0] for d in conn.execute("SELECT * FROM concepts LIMIT 0").description], r)) for r in rows]
    except Exception:
        data["concepts"] = []

    # Emotions (recent)
    try:
        rows = conn.execute("SELECT * FROM user_emotions WHERE user_id=? ORDER BY detected_at DESC LIMIT 10", (user_id,)).fetchall()
        data["emotions"] = [dict(zip([d[0] for d in conn.execute("SELECT * FROM user_emotions LIMIT 0").description], r)) for r in rows]
    except Exception:
        data["emotions"] = []

    # User profile
    try:
        row = conn.execute("SELECT * FROM user_profile WHERE user_id=?", (user_id,)).fetchone()
        if row:
            data["user_profile"] = dict(zip([d[0] for d in conn.execute("SELECT * FROM user_profile LIMIT 0").description], row))
        else:
            data["user_profile"] = None
    except Exception:
        data["user_profile"] = None

    # Reflections
    try:
        rows = conn.execute("SELECT * FROM reflections WHERE user_id=? ORDER BY created_at DESC LIMIT 5", (user_id,)).fetchall()
        data["reflections"] = [dict(zip([d[0] for d in conn.execute("SELECT * FROM reflections LIMIT 0").description], r)) for r in rows]
    except Exception:
        data["reflections"] = []

    # Meta-cognition logs
    try:
        rows = conn.execute("SELECT * FROM meta_cognition_logs WHERE user_id=? ORDER BY created_at DESC LIMIT 5", (user_id,)).fetchall()
        data["meta_cognition"] = [dict(zip([d[0] for d in conn.execute("SELECT * FROM meta_cognition_logs LIMIT 0").description], r)) for r in rows]
    except Exception:
        data["meta_cognition"] = []

    # Learned patterns
    try:
        rows = conn.execute("SELECT * FROM learned_patterns WHERE user_id=? AND status!='superseded' ORDER BY confidence DESC LIMIT 10", (user_id,)).fetchall()
        data["learned_patterns"] = [dict(zip([d[0] for d in conn.execute("SELECT * FROM learned_patterns LIMIT 0").description], r)) for r in rows]
    except Exception:
        data["learned_patterns"] = []

    # Life Loop status
    try:
        row = conn.execute("SELECT value FROM settings WHERE key='life_loop_last_runs'").fetchone()
        if row:
            last_runs = json.loads(row[0])
            now = int(time.time())
            data["life_loop"] = {
                k: {"last_run": v, "seconds_ago": now - v if v else None}
                for k, v in last_runs.items()
            }
        else:
            data["life_loop"] = {}
    except Exception:
        data["life_loop"] = {}

    # Stats
    data["stats"] = {
        "memories": len(data.get("memories", [])),
        "timeline": len(data.get("timeline", [])),
        "narratives": len(data.get("narratives", [])),
        "growth_insights": len(data.get("growth_insights", [])),
        "goals": len(data.get("goals", [])),
        "world_entities": len(data.get("world_entities", [])),
        "concepts": len(data.get("concepts", [])),
        "emotions": len(data.get("emotions", [])),
        "reflections": len(data.get("reflections", [])),
        "meta_cognition": len(data.get("meta_cognition", [])),
        "learned_patterns": len(data.get("learned_patterns", [])),
    }

    conn.close()
    return data


def edit_ai_data(db_path: Path, table: str, item_id: str, field: str, value: str) -> bool:
    """Edit a specific field of an AI-generated data item."""
    # Whitelist allowed tables and fields
    ALLOWED = {
        "memory_items": {"content", "importance", "category", "layer", "decay_weight"},
        "identity": {"name", "self_narrative", "personality_traits", "current_phase", "relationship_with_user"},
        "narratives": {"title", "story", "importance", "emotional_resonance"},
        "growth_insights": {"insight", "confidence", "status"},
        "long_term_goals": {"goal", "status", "progress"},
        "timeline_events": {"title", "description", "significance", "narrative"},
        "self_model": {"knows_well", "doesnt_know", "biases", "confidence_calibration"},
        "user_profile": {"personality", "interests", "preferences", "communication_style", "emotional_patterns", "auto_summary"},
        "memory_summary": {"summary"},
        "commitments": {"description", "status"},
        "world_entities": {"name", "description", "importance"},
    }
    if table not in ALLOWED or field not in ALLOWED[table]:
        return False
    conn = safe_connect(db_path, row_factory=False)
    try:
        conn.execute(f"UPDATE {table} SET {field}=? WHERE id=?", (value, item_id))
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def delete_ai_data(db_path: Path, table: str, item_id: str) -> bool:
    """Delete an AI-generated data item."""
    ALLOWED_TABLES = {
        "memory_items", "identity_evolution", "timeline_events", "narratives",
        "growth_insights", "corrections", "long_term_goals", "commitments",
        "world_entities", "world_relations", "causal_models", "concepts",
        "reflections", "meta_cognition_logs", "learned_patterns", "learning_observations",
        "memory_quarantine", "reflection_tree", "identity_assessments",
    }
    if table not in ALLOWED_TABLES:
        return False
    conn = safe_connect(db_path, row_factory=False)
    try:
        cur = conn.execute(f"DELETE FROM {table} WHERE id=?", (item_id,))
        conn.commit()
        return cur.rowcount > 0
    except Exception:
        return False
    finally:
        conn.close()


def clear_data_store(db_path: Path, store: str, user_id: str = "default") -> int:
    """Clear all data in a specific store."""
    STORES = {
        "memories": "memory_items",
        "timeline": "timeline_events",
        "narratives": "narratives",
        "growth": "growth_insights",
        "corrections": "corrections",
        "goals": "long_term_goals",
        "commitments": "commitments",
        "world": "world_entities",
        "concepts": "concepts",
        "reflections": "reflections",
        "meta_cognition": "meta_cognition_logs",
        "learned_patterns": "learned_patterns",
        "emotions": "user_emotions",
        "kg_entities": "kg_entities",
        "kg_relations": "kg_relations",
        "episodes": "episodes",
        "chat_vectors": "chat_vectors",
        "reflection_tree": "reflection_tree",
        "quarantine": "memory_quarantine",
        "identity_assessments": "identity_assessments",
    }
    table = STORES.get(store)
    if not table:
        return 0
    conn = safe_connect(db_path, row_factory=False)
    try:
        cur = conn.execute(f"DELETE FROM {table} WHERE user_id=?", (user_id,))
        conn.commit()
        return cur.rowcount
    except Exception:
        # Some tables may not have user_id column
        try:
            cur = conn.execute(f"DELETE FROM {table}")
            conn.commit()
            return cur.rowcount
        except Exception:
            return 0
    finally:
        conn.close()


def get_system_health(db_path: Path) -> Dict:
    """Get system health metrics."""
    conn = safe_connect(db_path, row_factory=False)
    health = {}
    # Table counts
    tables = [
        "memory_items", "identity", "timeline_events", "narratives",
        "growth_insights", "long_term_goals", "commitments", "world_entities",
        "self_model", "concepts", "user_emotions", "user_profile",
        "reflections", "meta_cognition_logs", "learned_patterns",
        "chat_vectors", "rag_documents", "rag_chunks",
        "kg_entities", "kg_relations", "episodes",
        "sessions", "cron_jobs", "workspace_items",
        "runtime_tasks", "memory_quarantine", "reflection_tree",
        "failed_extractions", "event_log",
    ]
    for t in tables:
        try:
            count = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            health[t] = count
        except Exception:
            health[t] = -1  # table doesn't exist
    # DB file size
    try:
        health["_db_size_bytes"] = db_path.stat().st_size
    except Exception:
        pass
    conn.close()
    return health
