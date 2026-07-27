"""
System endpoints: health, migrations, debug, vector-store status.

These are the foundational endpoints that don't depend on the legacy
main.py helpers. They use the new config/lifespan/exceptions infrastructure.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.config import DB_PATH, get_config
from app.logging_config import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/api/v2", tags=["system"])


# ============================================================
# Health
# ============================================================

@router.get("/health")
async def health():
    """Lightweight health check — used by Docker/curl."""
    return {"status": "ok", "version": get_config().app_version}


@router.get("/version")
async def version():
    """Get application version and config summary."""
    c = get_config()
    return {
        "app_name": c.app_name,
        "app_version": c.app_version,
        "ai_name": c.ai_name,
        "schema_version": _get_schema_version(),
        "agent_loop_enabled": c.agent_loop.agent_loop_enabled,
        "memory_governance_enabled": c.memory.memory_governance_enabled,
        "swarm_engine": c.swarm.swarm_engine,
    }


def _get_schema_version() -> int:
    """Read current schema version from DB."""
    try:
        from app.db_utils import safe_connect
        conn = safe_connect(DB_PATH)
        row = conn.execute(
            "SELECT value FROM schema_meta WHERE key='version'"
        ).fetchone()
        conn.close()
        return int(row[0]) if row else 0
    except Exception:
        return 0


# ============================================================
# Vector Store Status
# ============================================================

@router.get("/vector-store/status")
async def vector_store_status():
    """Get vector store backend status — shows which embedding model is loaded.

    Returns:
        sentence_transformers_available: bool
        chromadb_available: bool
        api_embedding_configured: bool (whether API embedding is enabled)
        api_embedding_model: str (the model name if API embedding is configured)
        default_model: configured local model name
        loaded_model: actually loaded local model name (empty if none)
        current_backend: the active backend
        has_real_embeddings: bool
        install_hint: pip command if not fully loaded
    """
    from app.vector_store import get_status, get_vector_store
    status = get_status()
    vs = get_vector_store(DB_PATH)
    status["current_backend"] = vs.backend
    status["has_real_embeddings"] = vs.has_real_embeddings
    return status


@router.get("/vector-store/stats")
async def vector_store_stats():
    """Get vector store collection stats."""
    from app.vector_store import get_vector_store
    vs = get_vector_store(DB_PATH)
    return vs.stats()


# ============================================================
# Migrations
# ============================================================

@router.get("/migrations/version")
async def migrations_version():
    """Get current schema version."""
    return {"version": _get_schema_version()}


@router.post("/migrations/run")
async def migrations_run():
    """Run pending migrations."""
    from app import migrations
    result = migrations.run_migrations(DB_PATH)
    return result


# ============================================================
# Debug
# ============================================================

@router.get("/debug/status")
async def debug_status():
    """Get debug mode status."""
    from app import debug_mode
    return {"debug_mode": debug_mode.is_debug_enabled(DB_PATH)}


@router.post("/debug/toggle")
async def debug_toggle():
    """Toggle debug mode."""
    from app import debug_mode
    current = debug_mode.is_debug_enabled(DB_PATH)
    debug_mode.set_debug_enabled(DB_PATH, not current)
    return {"debug_mode": not current}


@router.post("/debug/accelerate-time")
async def debug_accelerate_time(payload: dict):
    """Accelerate time for testing Life Loop."""
    from app import debug_mode
    seconds = int(payload.get("seconds", 3600))
    return debug_mode.accelerate_time(DB_PATH, seconds)


# ============================================================
# Config (read-only view)
# ============================================================

@router.get("/config")
async def get_config_view():
    """Get the current application configuration (sanitized — no secrets)."""
    c = get_config()
    return {
        "app_name": c.app_name,
        "app_version": c.app_version,
        "ai_name": c.ai_name,
        "chat": c.chat.model_dump(),
        "memory": c.memory.model_dump(),
        "agent_loop": c.agent_loop.model_dump(),
        "swarm": c.swarm.model_dump(),
        "life_loop": c.life_loop.model_dump(),
        "compression": c.compression.model_dump(),
        # Sanitize: don't expose api keys
        "api_configured": bool(c.api.api_key),
        "backup_api_configured": bool(c.api.backup_api_key),
        "rag_enabled": c.rag.rag_enabled,
        "mcp_enabled": c.mcp.mcp_enabled,
    }
