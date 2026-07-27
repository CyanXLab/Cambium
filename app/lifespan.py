"""
Cambium Application Lifespan.

Replaces the deprecated @app.on_event("startup") with a modern
FastAPI lifespan context manager. Handles:
  - Directory creation
  - Database migrations
  - Cron scheduler startup
  - Background reflection loop
  - Life Loop (circadian rhythm)
  - Plugin loading
  - Vector store initialization
  - Graceful shutdown
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional
from pathlib import Path

from app.logging_config import get_logger
from app.config import ensure_directories, DB_PATH, get_config

log = get_logger(__name__)


@asynccontextmanager
async def cambium_lifespan(app) -> AsyncIterator[None]:
    """Application lifespan: startup → yield → shutdown.

    All background tasks are tracked for graceful cancellation on shutdown.
    """
    log.info("lifespan.starting", extra={"version": get_config().app_version})

    # ── STARTUP ──

    # 1. Ensure directories exist
    ensure_directories()
    log.info("directories.ready")

    # 2. Run database migrations
    from app import migrations
    result = migrations.run_migrations(DB_PATH)
    log.info("migrations.complete", extra={
        "from": result.get("from_version"),
        "to": result.get("to_version"),
        "steps": result.get("migrations_run", []),
    })

    # 3. Initialize module-level DB schemas
    _init_module_schemas()

    # 4. Load plugins
    _load_plugins()

    # 5. Initialize vector store
    _init_vector_store()

    # 6. Start background tasks
    background_tasks: list[asyncio.Task] = []

    config = get_config()
    if config.sessions.cron_enabled:
        task = asyncio.create_task(_start_cron_scheduler())
        background_tasks.append(task)
        log.info("cron.started")

    if config.memory.background_reflection_enabled:
        task = asyncio.create_task(_background_reflection_loop())
        background_tasks.append(task)
        log.info("reflection_loop.started", extra={
            "interval_sec": config.memory.background_reflection_interval_sec,
        })

    if config.life_loop.life_loop_enabled:
        task = asyncio.create_task(_start_life_loop())
        background_tasks.append(task)
        log.info("life_loop.started")

    if config.memory.memory_governance_enabled:
        task = asyncio.create_task(_governance_loop())
        background_tasks.append(task)
        log.info("governance_loop.started")

    log.info("lifespan.ready", extra={"background_tasks": len(background_tasks)})

    # ── YIELD (app runs) ──
    try:
        yield
    finally:
        # ── SHUTDOWN ──
        log.info("lifespan.stopping", extra={"tasks": len(background_tasks)})

        for task in background_tasks:
            task.cancel()
        if background_tasks:
            await asyncio.gather(*background_tasks, return_exceptions=True)

        # Shutdown vector store / plugins
        _shutdown_vector_store()
        log.info("lifespan.stopped")


# ============================================================
# Startup helpers
# ============================================================

def _init_module_schemas():
    """Initialize module-specific DB tables."""
    from app import (
        cognitive_kernel, memory_orchestrator, memory_governance,
        adaptive_retrieval, identity_consistency,
    )
    cognitive_kernel.init_cognitive_db(DB_PATH)
    memory_orchestrator.init_memory_db(DB_PATH)
    memory_governance.init_governance_db(DB_PATH)
    adaptive_retrieval.init_adaptive_db(DB_PATH)
    identity_consistency.init_identity_consistency_db(DB_PATH)


def _load_plugins():
    """Load plugins from the plugins/ directory."""
    try:
        from app import plugin_sdk
        plugin_sdk.load_all_plugins()
        log.info("plugins.loaded")
    except Exception as exc:
        log.warning("plugins.load_failed", extra={"error": str(exc)})


def _init_vector_store():
    """Initialize the vector store backend."""
    try:
        from app.vector_store import get_vector_store
        vs = get_vector_store(DB_PATH)
        stats = vs.stats()
        log.info("vector_store.ready", extra={
            "backend": vs._backend,
            "collections": stats.get("collections", {}),
        })
    except Exception as exc:
        log.warning("vector_store.init_failed", extra={"error": str(exc)})


def _shutdown_vector_store():
    """Clean up vector store resources."""
    try:
        from app.vector_store import _stores
        for vs in _stores.values():
            if hasattr(vs, "close"):
                vs.close()
        _stores.clear()
    except Exception:
        pass


# ============================================================
# Background task implementations
# ============================================================

async def _start_cron_scheduler():
    """Start the cron job scheduler."""
    try:
        from app import cron as cron_mod, sessions as sessions_mod
        from app.config import DB_PATH
        import httpx

        async def _spawn_fn(job: dict) -> str:
            from app.main import get_subtask_api_config
            api_cfg = get_subtask_api_config()
            if job.get("model"):
                api_cfg = {**api_cfg, "api_model": job["model"]}
            sess = sessions_mod.session_create(
                DB_PATH, title=f"[cron] {job.get('name', job['id'])}",
                model=api_cfg["api_model"], system_prompt=job.get("system_prompt", ""),
                user_message=job["prompt"],
            )
            try:
                await sessions_mod.spawn_session(
                    sess["id"], DB_PATH, api_cfg,
                    job.get("system_prompt", ""), job["prompt"],
                    title=sess["title"], model=api_cfg["api_model"],
                )
            except Exception as exc:
                log.error("cron.spawn_failed", extra={"session": sess["id"], "error": str(exc)})
            return sess["id"]

        cron_mod.start_scheduler(DB_PATH, _spawn_fn)
    except Exception as exc:
        log.error("cron.start_failed", extra={"error": str(exc)})


async def _background_reflection_loop():
    """Periodically: apply memory decay, run reflection if enough new messages."""
    from app.config import DB_PATH
    config = get_config()
    interval = config.memory.background_reflection_interval_sec
    trigger_msgs = config.memory.background_reflection_trigger_msgs

    while True:
        try:
            await asyncio.sleep(interval)
            await _run_reflection_cycle(trigger_msgs)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            log.error("reflection_loop.error", extra={"error": str(exc)})
            await asyncio.sleep(60)  # backoff


async def _run_reflection_cycle(trigger_msgs: int):
    """One reflection cycle: decay + reflection + KG/episode extraction."""
    from app import memory_orchestrator, episodic_memory
    import sqlite3

    # 1. Decay
    try:
        memory_orchestrator.apply_decay(DB_PATH, user_id="default", days_elapsed=0.007)
        episodic_memory.apply_decay(DB_PATH, user_id="default")
    except Exception as exc:
        log.warning("reflection.decay_failed", extra={"error": str(exc)})

    # 2. Check if reflection should run
    last_reflection = memory_orchestrator.get_latest_reflection(DB_PATH, user_id="default")
    msgs_since = 9999
    if last_reflection:
        conn = sqlite3.connect(str(DB_PATH))
        cnt = conn.execute(
            "SELECT COUNT(*) FROM chat_vectors WHERE created_at > ?",
            (last_reflection.get("created_at", 0),)
        ).fetchone()[0]
        conn.close()
        msgs_since = cnt

    if msgs_since < trigger_msgs:
        return

    # 3. Gather recent conversation
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT role, content FROM chat_vectors ORDER BY created_at DESC LIMIT 50"
    ).fetchall()
    conn.close()
    if not rows:
        return

    config = get_config()
    ai_name = config.ai_name
    recent_text = "\n\n".join(
        f"{'用户' if r['role'] == 'user' else ai_name}: {r['content']}"
        for r in reversed(rows)
    )

    # 4. Run reflection
    from app.main import get_memory_api_config
    import httpx
    mem_cfg = get_memory_api_config()
    try:
        async with httpx.AsyncClient(timeout=90.0) as c:
            result = await memory_orchestrator.run_reflection(
                DB_PATH, user_id="default",
                recent_conversation=recent_text,
                message_count=msgs_since,
                http_client=c, api_cfg=mem_cfg,
            )
        if result.get("success"):
            log.info("reflection.completed", extra={
                "new_memories": result.get("new_memories_added", 0)
            })

            # 5. Extract KG triples + episodes (if enabled)
            if config.memory.kg_auto_extract or config.memory.episodic_auto_extract:
                await _extract_kg_and_episodes(recent_text, mem_cfg)
    except Exception as exc:
        log.error("reflection.failed", extra={"error": str(exc)})


async def _extract_kg_and_episodes(recent_text: str, mem_cfg: dict):
    """Extract knowledge graph triples and episodic memories."""
    from app import knowledge_graph, episodic_memory
    import httpx
    try:
        async with httpx.AsyncClient(timeout=30.0) as c:
            if get_config().memory.kg_auto_extract:
                triples = await knowledge_graph.extract_triples_via_llm(recent_text, c, mem_cfg)
                if triples:
                    knowledge_graph.add_triples(DB_PATH, user_id="default", triples=triples)
                    log.info("kg.extracted", extra={"triples": len(triples)})

            if get_config().memory.episodic_auto_extract:
                episodes = await episodic_memory.extract_episodes_via_llm(recent_text, c, mem_cfg)
                for ep in episodes:
                    episodic_memory.create_episode(
                        DB_PATH, user_id="default",
                        title=ep.get("title", ""),
                        description=ep.get("description", ""),
                        occurred_at=ep.get("occurred_at", ""),
                        importance=int(ep.get("importance", 50)),
                        tags=ep.get("tags", ""),
                        emotional_valence=ep.get("emotional_valence", "neutral"),
                        status=ep.get("status", "completed"),
                        source="reflection",
                    )
                if episodes:
                    log.info("episodes.extracted", extra={"count": len(episodes)})
    except Exception as exc:
        log.warning("kg_episode.extraction_failed", extra={"error": str(exc)})


async def _start_life_loop():
    """Start the Life Loop circadian rhythm."""
    try:
        from app import life_loop
        from app.main import get_memory_api_config
        import httpx as _httpx

        loop_inst = life_loop.LifeLoop(
            db_path=DB_PATH,
            get_memory_api_cfg=get_memory_api_config,
            httpx_client_factory=lambda timeout: _httpx.AsyncClient(timeout=timeout),
        )
        loop_inst.start()
    except Exception as exc:
        log.error("life_loop.start_failed", extra={"error": str(exc)})


async def _governance_loop():
    """Periodically run memory governance: auto-validate + LLM validation + promotion."""
    from app import memory_governance
    config = get_config()
    interval = config.memory.governance_auto_validate_interval_sec

    while True:
        try:
            await asyncio.sleep(interval)

            # 1. Rule-based auto-validation
            result = memory_governance.auto_validate_by_rules(DB_PATH, user_id="default")
            if result["auto_validated"] or result["auto_rejected"]:
                log.info("governance.auto_validated", extra=result)

            # 2. LLM validation for remaining quarantined items
            try:
                from app.main import get_memory_api_config
                import httpx
                mem_cfg = get_memory_api_config()
                if mem_cfg.get("api_key"):
                    async with httpx.AsyncClient(timeout=30.0) as c:
                        llm_result = await memory_governance.validate_quarantine_batch(
                            DB_PATH, user_id="default",
                            http_client=c, api_cfg=mem_cfg,
                        )
                        if llm_result.get("validated", 0) or llm_result.get("rejected", 0):
                            log.info("governance.llm_validated", extra=llm_result)
            except Exception as exc:
                log.warning("governance.llm_validation_failed", extra={"error": str(exc)})

            # 3. Promote validated memories
            promoted = memory_governance.promote_all_validated(DB_PATH, user_id="default")
            if promoted.get("promoted", 0):
                log.info("governance.promoted", extra=promoted)

        except asyncio.CancelledError:
            break
        except Exception as exc:
            log.error("governance_loop.error", extra={"error": str(exc)})
            await asyncio.sleep(60)
