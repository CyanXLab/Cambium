"""
Schema Migration System for Cambium.

Handles schema evolution over years. Every time Cambium starts, it checks
the schema version and runs pending migrations.

Design:
- Version tracked in `schema_version` table
- Each migration is a Python function that takes a connection and ALTERs schema
- Migrations are idempotent where possible (use IF NOT EXISTS, check column existence)
- Supports both DDL (ALTER TABLE) and data migrations
- Forward-only (no down-migrations — backup before running)

Usage:
    from app.migrations import run_migrations
    run_migrations(db_path)  # call on startup

Adding a new migration:
    1. Bump SCHEMA_VERSION
    2. Add a function `def _migrate_v7_to_v8(conn): ...`
    3. Register it in _MIGRATIONS dict
"""
from __future__ import annotations
import sqlite3
import json
import time
from typing import Callable, Dict, List, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


# Current schema version. Bump this when adding a migration.
SCHEMA_VERSION = 7


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    )
    return cur.fetchone() is not None


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    cur = conn.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cur.fetchall()]
    return column in columns


def _get_version(conn: sqlite3.Connection) -> int:
    """Get current schema version. Returns 0 if not tracked."""
    if not _table_exists(conn, "schema_version"):
        return 0
    cur = conn.execute("SELECT MAX(version) FROM schema_version")
    row = cur.fetchone()
    return row[0] if row and row[0] is not None else 0


def _set_version(conn: sqlite3.Connection, version: int, description: str = ""):
    conn.execute(
        "INSERT INTO schema_version (version, description, applied_at) VALUES (?,?,?)",
        (version, description, int(time.time()))
    )
    conn.commit()


# ============================================================
# Migration functions
# ============================================================

def _migrate_v0_to_v1(conn: sqlite3.Connection):
    """v0 → v1: Initialize schema version tracking + add missing core tables."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_version ("
        "version INTEGER PRIMARY KEY, description TEXT, applied_at INTEGER)"
    )
    conn.commit()


def _migrate_v1_to_v2(conn: sqlite3.Connection):
    """v1 → v2: Add emotional_tone to narratives (was missing in original schema)."""
    if not _column_exists(conn, "narratives", "emotional_tone"):
        try:
            conn.execute("ALTER TABLE narratives ADD COLUMN emotional_tone TEXT DEFAULT 'neutral'")
        except sqlite3.OperationalError:
            pass  # Column might already exist
    conn.commit()


def _migrate_v2_to_v3(conn: sqlite3.Connection):
    """v2 → v3: Add importance_weight to timeline_events (allows REAL importance)."""
    if not _column_exists(conn, "timeline_events", "importance_weight"):
        try:
            conn.execute("ALTER TABLE timeline_events ADD COLUMN importance_weight REAL DEFAULT 1.0")
        except sqlite3.OperationalError:
            pass
    conn.commit()


def _migrate_v3_to_v4(conn: sqlite3.Connection):
    """v3 → v4: Add workspace tables (Cambium Home directory structure)."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS workspace_items (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL DEFAULT 'default',
            section TEXT NOT NULL,  -- brain/projects/library/notebook/goals/people/skills
            title TEXT NOT NULL,
            content TEXT NOT NULL DEFAULT '',
            item_type TEXT NOT NULL DEFAULT 'note',  -- note/doc/draft/plan/idea/log
            tags TEXT NOT NULL DEFAULT '[]',
            metadata TEXT NOT NULL DEFAULT '{}',
            parent_id TEXT,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            accessed_at INTEGER NOT NULL,
            access_count INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_workspace_section ON workspace_items(user_id, section);
        CREATE INDEX IF NOT EXISTS idx_workspace_parent ON workspace_items(parent_id);
    """)
    conn.commit()


def _migrate_v4_to_v5(conn: sqlite3.Connection):
    """v4 → v5: Add agent_runtime tables (task lifecycle state machine)."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS runtime_tasks (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL DEFAULT 'default',
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending',
            -- pending/running/paused/resumed/completed/cancelled/failed
            priority INTEGER NOT NULL DEFAULT 5,
            parent_task TEXT,
            depends_on TEXT NOT NULL DEFAULT '[]',  -- JSON array of task ids
            assigned_agent TEXT NOT NULL DEFAULT '',  -- planner/researcher/memory/reflection/critic
            input TEXT NOT NULL DEFAULT '{}',  -- JSON input
            output TEXT NOT NULL DEFAULT '{}',  -- JSON output
            error TEXT NOT NULL DEFAULT '',
            progress INTEGER NOT NULL DEFAULT 0,  -- 0-100
            created_at INTEGER NOT NULL,
            started_at INTEGER,
            paused_at INTEGER,
            completed_at INTEGER,
            updated_at INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_runtime_status ON runtime_tasks(user_id, status);
        CREATE INDEX IF NOT EXISTS idx_runtime_agent ON runtime_tasks(assigned_agent);

        CREATE TABLE IF NOT EXISTS runtime_events (
            id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            event_type TEXT NOT NULL,  -- created/started/paused/resumed/cancelled/completed/failed/log
            message TEXT NOT NULL DEFAULT '',
            timestamp INTEGER NOT NULL,
            FOREIGN KEY (task_id) REFERENCES runtime_tasks(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_runtime_events_task ON runtime_events(task_id);
    """)
    conn.commit()


def _migrate_v5_to_v6(conn: sqlite3.Connection):
    """v5 → v6: Add life-first pivot tables (inbox / journals / co-experience moments / prompt templates)."""
    conn.executescript("""
        -- Inbox: universal capture. Everything goes here first, then Life Loop routes it.
        CREATE TABLE IF NOT EXISTS inbox_items (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL DEFAULT 'default',
            type TEXT NOT NULL,            -- text/url/voice/image/todo/file/note/idea
            content TEXT NOT NULL,         -- main text or URL
            title TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT 'manual',  -- manual/web/voice/capture/email/...
            metadata TEXT NOT NULL DEFAULT '{}',    -- JSON: tags, attachments, etc.
            status TEXT NOT NULL DEFAULT 'pending', -- pending/processed/archived/deleted
            destination TEXT NOT NULL DEFAULT '',   -- where Life Loop routed it: journal/memory/goal/task/research/note
            destination_id TEXT NOT NULL DEFAULT '',-- id of the routed item
            created_at INTEGER NOT NULL,
            processed_at INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_inbox_status ON inbox_items(user_id, status);
        CREATE INDEX IF NOT EXISTS idx_inbox_created ON inbox_items(user_id, created_at);

        -- Journals: AI-assisted daily journal. One entry per day.
        CREATE TABLE IF NOT EXISTS journals (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL DEFAULT 'default',
            date TEXT NOT NULL,            -- YYYY-MM-DD
            content TEXT NOT NULL DEFAULT '',       -- user-editable body
            ai_draft TEXT NOT NULL DEFAULT '',      -- AI-generated draft
            ai_summary TEXT NOT NULL DEFAULT '',    -- one-paragraph summary
            emotional_tone TEXT NOT NULL DEFAULT '',-- happy/focused/tired/frustrated/calm/...
            highlights TEXT NOT NULL DEFAULT '[]',  -- JSON array of strings
            growth_notes TEXT NOT NULL DEFAULT '',  -- what user learned / improved
            failures TEXT NOT NULL DEFAULT '',      -- what didn't work
            gratitude TEXT NOT NULL DEFAULT '',     -- optional gratitude
            is_auto_generated INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            UNIQUE(user_id, date)
        );
        CREATE INDEX IF NOT EXISTS idx_journals_date ON journals(user_id, date);

        -- Co-experience moments: "remember when we..." — shared history between user and AI
        CREATE TABLE IF NOT EXISTS co_experience_moments (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL DEFAULT 'default',
            moment_type TEXT NOT NULL DEFAULT 'shared',  -- shared/milestone/first/turning_point
            title TEXT NOT NULL,
            story TEXT NOT NULL,                  -- narrative of what happened
            context_ref TEXT NOT NULL DEFAULT '', -- JSON: {conversation_id, message_id, ...}
            occurred_at INTEGER NOT NULL,         -- when it happened
            emotional_weight REAL NOT NULL DEFAULT 0.5,  -- 0-1, how meaningful
            surfaced_count INTEGER NOT NULL DEFAULT 0,    -- how many times AI recalled this
            last_surfaced_at INTEGER,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_co_exp_occurred ON co_experience_moments(user_id, occurred_at);
        CREATE INDEX IF NOT EXISTS idx_co_exp_weight ON co_experience_moments(user_id, emotional_weight);

        -- Prompt templates: registry of all editable LLM prompts (Prompt Engineering)
        CREATE TABLE IF NOT EXISTS prompt_templates (
            key TEXT PRIMARY KEY,                -- e.g. prompt_memory_edit
            category TEXT NOT NULL,              -- memory/cognitive/reflection/identity/journal/...
            label TEXT NOT NULL,                 -- display label
            description TEXT NOT NULL DEFAULT '',
            content TEXT NOT NULL,               -- the actual prompt text
            is_default INTEGER NOT NULL DEFAULT 1, -- 1 if user hasn't customized
            updated_at INTEGER NOT NULL
        );
    """)
    conn.commit()


def _migrate_v6_to_v7(conn: sqlite3.Connection):
    """v6 → v7: The 'Residents' pivot — agents become living residents, plus artifacts, philosophy, evolution, discoveries, AI mornings.

    This is the largest schema change yet. It transforms Cambium from "chat + memory + features"
    into "a world with residents, artifacts, philosophy, and an AI that writes to you each morning."
    """
    conn.executescript("""
        -- ===== Residents (formerly "Agents") =====
        CREATE TABLE IF NOT EXISTS residents (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL DEFAULT 'default',
            name TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'general',
            system_prompt TEXT NOT NULL DEFAULT '',
            llm_config TEXT NOT NULL DEFAULT '{}',
            working_dir TEXT NOT NULL DEFAULT '',
            mode TEXT NOT NULL DEFAULT 'sync',
            max_retries INTEGER NOT NULL DEFAULT 3,
            depends_on TEXT NOT NULL DEFAULT '[]',
            triggers TEXT NOT NULL DEFAULT '[]',
            skill_id TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'active',
            personality_traits TEXT NOT NULL DEFAULT '{}',
            current_concerns TEXT NOT NULL DEFAULT '[]',
            last_run_at INTEGER,
            last_run_status TEXT NOT NULL DEFAULT '',
            run_count INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_residents_user ON residents(user_id, status);

        CREATE TABLE IF NOT EXISTS resident_runs (
            id TEXT PRIMARY KEY,
            resident_id TEXT NOT NULL,
            user_id TEXT NOT NULL DEFAULT 'default',
            trigger TEXT NOT NULL,
            trigger_payload TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'pending',
            input TEXT NOT NULL DEFAULT '',
            output TEXT NOT NULL DEFAULT '',
            error TEXT NOT NULL DEFAULT '',
            retry_count INTEGER NOT NULL DEFAULT 0,
            started_at INTEGER,
            completed_at INTEGER,
            duration_ms INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER NOT NULL,
            FOREIGN KEY (resident_id) REFERENCES residents(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_runs_resident ON resident_runs(resident_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_runs_status ON resident_runs(status);

        CREATE TABLE IF NOT EXISTS resident_skills (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            description TEXT NOT NULL DEFAULT '',
            path TEXT NOT NULL,
            manifest TEXT NOT NULL DEFAULT '{}',
            is_builtin INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        );

        -- ===== Artifacts (the "World" — created things) =====
        CREATE TABLE IF NOT EXISTS artifacts (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL DEFAULT 'default',
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL DEFAULT '',
            format TEXT NOT NULL DEFAULT 'markdown',
            parent_id TEXT,
            version INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'draft',
            created_by TEXT NOT NULL DEFAULT 'joint',
            created_with_resident TEXT NOT NULL DEFAULT '',
            related_artifacts TEXT NOT NULL DEFAULT '[]',
            tags TEXT NOT NULL DEFAULT '[]',
            metadata TEXT NOT NULL DEFAULT '{}',
            file_path TEXT NOT NULL DEFAULT '',
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            accessed_at INTEGER NOT NULL,
            access_count INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_artifacts_type ON artifacts(user_id, type);
        CREATE INDEX IF NOT EXISTS idx_artifacts_parent ON artifacts(parent_id);
        CREATE INDEX IF NOT EXISTS idx_artifacts_status ON artifacts(user_id, status);

        -- ===== Philosophy (Values, Beliefs, Principles, Anti-goals) =====
        CREATE TABLE IF NOT EXISTS philosophy_items (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL DEFAULT 'default',
            type TEXT NOT NULL,
            content TEXT NOT NULL,
            rationale TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT 'user',
            confidence REAL NOT NULL DEFAULT 0.8,
            status TEXT NOT NULL DEFAULT 'active',
            superseded_by TEXT NOT NULL DEFAULT '',
            first_observed_at INTEGER,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_phil_user_type ON philosophy_items(user_id, type, status);

        -- ===== Evolution events (thought evolution tree) =====
        CREATE TABLE IF NOT EXISTS evolution_events (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL DEFAULT 'default',
            type TEXT NOT NULL,
            from_state TEXT NOT NULL DEFAULT '',
            to_state TEXT NOT NULL DEFAULT '',
            evidence TEXT NOT NULL DEFAULT '',
            evidence_refs TEXT NOT NULL DEFAULT '[]',
            confidence REAL NOT NULL DEFAULT 0.5,
            observed_by TEXT NOT NULL DEFAULT 'ai',
            status TEXT NOT NULL DEFAULT 'observed',
            occurred_at INTEGER NOT NULL,
            created_at INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_evo_user_type ON evolution_events(user_id, type);
        CREATE INDEX IF NOT EXISTS idx_evo_occurred ON evolution_events(user_id, occurred_at);

        -- ===== Discoveries (daily surprises from AI) =====
        CREATE TABLE IF NOT EXISTS discoveries (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL DEFAULT 'default',
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            evidence TEXT NOT NULL DEFAULT '',
            evidence_refs TEXT NOT NULL DEFAULT '[]',
            confidence REAL NOT NULL DEFAULT 0.5,
            status TEXT NOT NULL DEFAULT 'new',
            discovered_by TEXT NOT NULL DEFAULT 'ai',
            date_str TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            seen_at INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_disc_user_date ON discoveries(user_id, date_str);
        CREATE INDEX IF NOT EXISTS idx_disc_status ON discoveries(user_id, status);

        -- ===== AI Mornings (the daily letter) =====
        CREATE TABLE IF NOT EXISTS ai_mornings (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL DEFAULT 'default',
            date TEXT NOT NULL,
            letter TEXT NOT NULL DEFAULT '',
            concerns TEXT NOT NULL DEFAULT '[]',
            growth_notes TEXT NOT NULL DEFAULT '',
            discovery_refs TEXT NOT NULL DEFAULT '[]',
            artifact_refs TEXT NOT NULL DEFAULT '[]',
            mood TEXT NOT NULL DEFAULT '',
            generated_at INTEGER NOT NULL,
            read_at INTEGER,
            UNIQUE(user_id, date)
        );
        CREATE INDEX IF NOT EXISTS idx_mornings_date ON ai_mornings(user_id, date);
    """)
    conn.commit()


# Migration registry: version → function
_MIGRATIONS: Dict[int, Callable] = {
    1: _migrate_v0_to_v1,
    2: _migrate_v1_to_v2,
    3: _migrate_v2_to_v3,
    4: _migrate_v3_to_v4,
    5: _migrate_v4_to_v5,
    6: _migrate_v5_to_v6,
    7: _migrate_v6_to_v7,
}


def run_migrations(db_path: Path) -> Dict:
    """Run all pending migrations. Call on startup.

    Returns:
        {from_version, to_version, migrations_run: [...]}
    """
    from app.db_utils import safe_connect
    conn = safe_connect(db_path)
    current = _get_version(conn)
    migrations_run = []

    if current == 0:
        # Fresh install — just record v1 (tables are created by init_* functions)
        _migrate_v0_to_v1(conn)
        _set_version(conn, 1, "initial schema version tracking")
        current = 1
        migrations_run.append("v0→v1 (init)")

    for version in range(current + 1, SCHEMA_VERSION + 1):
        migrate_fn = _MIGRATIONS.get(version)
        if migrate_fn is None:
            logger.warning(f"No migration function for v{version}, skipping")
            continue
        try:
            migrate_fn(conn)
            _set_version(conn, version, migrate_fn.__doc__ or f"migrate to v{version}")
            migrations_run.append(f"v{version-1}→v{version}")
            logger.info(f"Migration v{version-1}→v{version} applied: {migrate_fn.__doc__}")
        except Exception as e:
            logger.error(f"Migration v{version-1}→v{version} failed: {e}")
            conn.rollback()
            conn.close()
            raise

    conn.close()
    return {
        "from_version": current,
        "to_version": SCHEMA_VERSION,
        "migrations_run": migrations_run,
    }


def get_schema_version(db_path: Path) -> int:
    """Get current schema version without running migrations."""
    from app.db_utils import safe_connect
    conn = safe_connect(db_path)
    v = _get_version(conn)
    conn.close()
    return v
