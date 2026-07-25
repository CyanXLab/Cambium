"""
Backup & Restore for Cambium — take your soul with you.

Export: creates a single JSON file containing ALL user data:
- All SQLite tables (cognitive kernel, memory, KG, episodes, chat vectors, etc.)
- All settings
- Workspace files (notes, drafts, plans)
- Skills directory
- Custom tools
- Schema version (for forward compatibility)

Import: restores from a backup file. Handles version differences by
running migrations after import.

The backup format is versioned. Higher versions can read lower versions.
Lower versions reading higher versions will get a warning.

Usage:
    from app.backup import export_all, import_all
    export_all(db_path, workspace_dir, output_path)
    import_all(db_path, workspace_dir, input_path)
"""
from __future__ import annotations
import json
import sqlite3
import time
import hashlib
import zipfile
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


BACKUP_FORMAT_VERSION = 2  # bump when backup format changes


# Tables to export (in dependency order — parents first)
EXPORT_TABLES = [
    # Core
    "settings",
    "schema_version",
    # Memory orchestrator
    "memory_items",
    "reflections",
    "conversation_goals",
    "tool_memory",
    "world_state",
    # Cognitive kernel
    "identity",
    "identity_evolution",
    "timeline_events",
    "narratives",
    "growth_insights",
    "corrections",
    "long_term_goals",
    "commitments",
    "world_entities",
    "world_relations",
    "causal_models",
    "self_model",
    "concepts",
    # Advanced memory
    "user_emotions",
    "user_profile",
    "emotion_state",
    # Memory (legacy)
    "memories",
    "memory_summary",
    # Knowledge graph
    "kg_entities",
    "kg_relations",
    # Episodic memory
    "episodes",
    "episode_links",
    # Meta cognition
    "meta_cognition_logs",
    # Chat vectors
    "chat_vectors",
    # RAG
    "rag_documents",
    "rag_chunks",
    # Sessions
    "sessions",
    # Cron
    "cron_jobs",
    "cron_runs",
    # Conversations
    "conversations",
    "messages",
    # MCP config (stored in settings, but list for reference)
    # Workspace
    "workspace_items",
    "runtime_tasks",
    "runtime_events",
    # Failed extractions (recovery queue)
    "failed_extractions",
]


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    )
    return cur.fetchone() is not None


def _export_table(conn: sqlite3.Connection, table: str) -> Dict:
    """Export a single table to {columns, rows}."""
    if not _table_exists(conn, table):
        return {"exists": False, "columns": [], "rows": []}
    cur = conn.execute(f"SELECT * FROM {table}")
    columns = [desc[0] for desc in cur.description]
    rows = []
    for row in cur.fetchall():
        rows.append(list(row))
    return {"exists": True, "columns": columns, "rows": rows, "count": len(rows)}


def _import_table(conn: sqlite3.Connection, table: str, data: Dict):
    """Import a table from {columns, rows}. Creates table if not exists,
    inserts rows. Skips rows that violate UNIQUE constraints."""
    if not data.get("exists"):
        return 0
    columns = data["columns"]
    rows = data["rows"]
    if not columns or not rows:
        return 0
    # Create table if not exists (with generic schema — actual schema is
    # created by init functions, this is just a fallback)
    if not _table_exists(conn, table):
        # We can't recreate exact schema from backup, but the init functions
        # should have already run. Log a warning.
        logger.warning(f"Table {table} doesn't exist, skipping {len(rows)} rows")
        return 0
    # Insert rows, skipping duplicates
    placeholders = ",".join("?" * len(columns))
    col_list = ",".join(columns)
    inserted = 0
    for row in rows:
        try:
            # Pad/truncate row to match columns
            row = list(row[:len(columns)]) + [None] * max(0, len(columns) - len(row))
            conn.execute(
                f"INSERT OR IGNORE INTO {table} ({col_list}) VALUES ({placeholders})",
                row
            )
            if conn.total_changes > 0:
                inserted += 1
        except sqlite3.Error as e:
            logger.debug(f"Skip row in {table}: {e}")
    return inserted


def export_all(db_path: Path, workspace_dir: Path, skills_dir: Path,
               custom_tools_dir: Path, output_path: Path) -> Dict:
    """Export ALL user data to a zip file.

    The zip contains:
    - backup.json: all DB tables + metadata
    - workspace/: workspace files
    - skills/: skill SKILL.md files
    - custom_tools/: custom Python tools

    Returns {path, size, tables, format_version}
    """
    from app.db_utils import safe_connect

    backup = {
        "format_version": BACKUP_FORMAT_VERSION,
        "created_at": int(time.time()),
        "created_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "cambium_version": "1.0.0",
        "schema_version": 0,
        "tables": {},
    }

    # Export DB tables
    conn = safe_connect(db_path)
    # Get schema version
    try:
        cur = conn.execute("SELECT MAX(version) FROM schema_version")
        row = cur.fetchone()
        backup["schema_version"] = row[0] if row and row[0] else 0
    except Exception:
        backup["schema_version"] = 0

    total_rows = 0
    for table in EXPORT_TABLES:
        backup["tables"][table] = _export_table(conn, table)
        total_rows += backup["tables"][table].get("count", 0)
    conn.close()

    # Create zip
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Write backup.json
        zf.writestr("backup.json", json.dumps(backup, ensure_ascii=False, indent=2))
        # Write workspace files
        if workspace_dir.exists():
            for f in workspace_dir.rglob("*"):
                if f.is_file():
                    arcname = f"workspace/{f.relative_to(workspace_dir)}"
                    zf.write(f, arcname)
        # Write skills
        if skills_dir.exists():
            for f in skills_dir.rglob("*"):
                if f.is_file():
                    arcname = f"skills/{f.relative_to(skills_dir)}"
                    zf.write(f, arcname)
        # Write custom tools
        if custom_tools_dir.exists():
            for f in custom_tools_dir.rglob("*"):
                if f.is_file():
                    arcname = f"custom_tools/{f.relative_to(custom_tools_dir)}"
                    zf.write(f, arcname)

    return {
        "path": str(output_path),
        "size": output_path.stat().st_size,
        "tables": len(backup["tables"]),
        "total_rows": total_rows,
        "format_version": BACKUP_FORMAT_VERSION,
        "schema_version": backup["schema_version"],
    }


def import_all(db_path: Path, workspace_dir: Path, skills_dir: Path,
               custom_tools_dir: Path, input_path: Path,
               overwrite: bool = False) -> Dict:
    """Import ALL user data from a backup zip file.

    Args:
        overwrite: If True, drop existing tables before import (destructive).
                   If False, merge (INSERT OR IGNORE, keeps existing data).

    Returns {tables_imported, rows_imported, files_restored, schema_version}
    """
    from app.db_utils import safe_connect

    if not input_path.exists():
        raise FileNotFoundError(f"Backup file not found: {input_path}")

    with zipfile.ZipFile(input_path, "r") as zf:
        # Read backup.json
        backup = json.loads(zf.read("backup.json"))
        backup_version = backup.get("format_version", 1)
        backup_schema = backup.get("schema_version", 0)

        if backup_version > BACKUP_FORMAT_VERSION:
            logger.warning(
                f"Backup format v{backup_version} is newer than supported v{BACKUP_FORMAT_VERSION}. "
                "Some data may not import correctly."
            )

        # Extract files
        files_restored = 0
        for name in zf.namelist():
            if name == "backup.json":
                continue
            # Determine target directory
            if name.startswith("workspace/"):
                target = workspace_dir / name[len("workspace/"):]
            elif name.startswith("skills/"):
                target = skills_dir / name[len("skills/"):]
            elif name.startswith("custom_tools/"):
                target = custom_tools_dir / name[len("custom_tools/"):]
            else:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "wb") as f:
                f.write(zf.read(name))
            files_restored += 1

    # Import DB tables
    # First, ensure all init functions have run so tables exist
    from app import (cognitive_kernel, memory_orchestrator, knowledge_graph,
                     episodic_memory, meta_cognition, advanced_memory,
                     chat_vectors, sessions as sessions_mod, cron as cron_mod)
    cognitive_kernel.init_cognitive_db(db_path)
    memory_orchestrator.init_orchestrator_db(db_path)
    knowledge_graph.init_kg_db(db_path)
    episodic_memory.init_episodic_db(db_path)
    meta_cognition.init_meta_cog_db(db_path)
    advanced_memory.init_advanced_db(db_path)
    chat_vectors.init_chat_vectors_db(db_path)
    sessions_mod.init_db(db_path)
    cron_mod.init_db(db_path)
    # Run migrations to ensure latest schema
    from app.migrations import run_migrations
    run_migrations(db_path)

    conn = safe_connect(db_path)
    tables_imported = 0
    rows_imported = 0

    if overwrite:
        # Delete all existing data in export tables
        for table in EXPORT_TABLES:
            if _table_exists(conn, table):
                conn.execute(f"DELETE FROM {table}")

    for table, data in backup.get("tables", {}).items():
        count = _import_table(conn, table, data)
        if count > 0:
            tables_imported += 1
            rows_imported += count

    conn.commit()
    conn.close()

    # Run migrations again (in case imported data has older schema)
    migration_result = run_migrations(db_path)

    return {
        "tables_imported": tables_imported,
        "rows_imported": rows_imported,
        "files_restored": files_restored,
        "backup_format_version": backup_version,
        "backup_schema_version": backup_schema,
        "current_schema_version": migration_result["to_version"],
        "migrations_run": migration_result["migrations_run"],
    }
