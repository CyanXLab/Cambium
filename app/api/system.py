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
# WebLLM embedding endpoints (browser-side embeddings)
# ============================================================

from pydantic import BaseModel
from typing import List as TypingList, Optional as TypingOptional


class WebLLMEmbedAdd(BaseModel):
    """Add an item with a pre-computed embedding (from WebLLM frontend)."""
    collection: str
    id: str
    text: str
    embedding: TypingList[float]
    metadata: dict = {}


class WebLLMEmbedQuery(BaseModel):
    """Query with a pre-computed embedding (from WebLLM frontend)."""
    collection: str
    embedding: TypingList[float]
    top_k: int = 5
    where: TypingOptional[dict] = None


@router.post("/vector-store/webllm/add")
async def webllm_add(req: WebLLMEmbedAdd):
    """Add an item with a pre-computed embedding vector.

    The frontend computes the embedding using Transformers.js (WebLLM),
    then sends the vector here for storage in ChromaDB.
    """
    from app.vector_store import get_vector_store, CHROMA_AVAILABLE
    if not CHROMA_AVAILABLE:
        raise HTTPException(status_code=503, detail="ChromaDB not installed on server")
    vs = get_vector_store(DB_PATH)
    col = vs._get_collection(req.collection)
    if not col:
        raise HTTPException(status_code=500, detail="Failed to get collection")
    try:
        col.upsert(
            ids=[req.id],
            embeddings=[req.embedding],
            documents=[req.text],
            metadatas=[req.metadata],
        )
        return {"status": "ok", "id": req.id}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/vector-store/webllm/query")
async def webllm_query(req: WebLLMEmbedQuery):
    """Query a collection with a pre-computed embedding vector.

    The frontend computes the query embedding using Transformers.js (WebLLM),
    then sends the vector here for similarity search in ChromaDB.
    """
    from app.vector_store import get_vector_store, CHROMA_AVAILABLE
    if not CHROMA_AVAILABLE:
        raise HTTPException(status_code=503, detail="ChromaDB not installed on server")
    vs = get_vector_store(DB_PATH)
    col = vs._get_collection(req.collection)
    if not col:
        raise HTTPException(status_code=500, detail="Failed to get collection")
    try:
        results = col.query(
            query_embeddings=[req.embedding],
            n_results=req.top_k,
            where=req.where,
        )
        return {"results": vs._format_chroma_results(results)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ============================================================
# Vision / Image Description (VLM)
# ============================================================

class VisionDescribeRequest(BaseModel):
    """Request to describe an image using a Vision Language Model."""
    data_url: str  # data:image/...;base64,...
    name: str = ""
    prompt: str = ""  # Optional custom prompt


@router.post("/vision/describe")
async def vision_describe(req: VisionDescribeRequest):
    """Describe an image using a Vision Language Model (VLM).

    This endpoint receives a base64-encoded image (as a data URL),
    sends it to a VLM (e.g., Qwen2.5-VL), and returns a text description.
    The description is then passed to the main LLM as part of the user message.

    The VLM model is configured via settings:
      - model_slot_3 = "Qwen/Qwen2.5-VL-72B-Instruct" (or any VL model)
      - Or use a dedicated vision_api_key/base_url/model in settings

    Falls back to the main API config if no VLM-specific config is set.
    """
    if not req.data_url:
        raise HTTPException(status_code=400, detail="data_url required")

    # Get VLM config: try vision-specific settings, fall back to main config
    from app.main import get_api_config, settings_get_all, DB_PATH
    s = settings_get_all()
    api_cfg = {
        "api_key": s.get("vision_api_key") or "",
        "api_base_url": s.get("vision_api_base_url") or "",
        "api_model": s.get("vision_api_model") or "",
    }
    # Fall back to main config
    if not api_cfg["api_key"]:
        main = get_api_config()
        api_cfg = main
    # Fall back to model_slot_3 (Qwen2.5-VL by default)
    if not api_cfg["api_model"] or "VL" not in api_cfg["api_model"].upper():
        vlm_model = s.get("model_slot_3", "")
        if vlm_model:
            api_cfg["api_model"] = vlm_model

    if not api_cfg.get("api_key"):
        raise HTTPException(status_code=503, detail="No API key configured for vision model")

    import httpx
    prompt = req.prompt or "请详细描述这张图片的内容，包括场景、物体、文字、人物、颜色等关键信息。用中文回答。"

    payload = {
        "model": api_cfg["api_model"],
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": req.data_url}},
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        "temperature": 0.3,
        "max_tokens": 800,
        "stream": False,
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{api_cfg['api_base_url'].rstrip('/')}/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_cfg['api_key']}",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            description = data["choices"][0]["message"]["content"]
            return {
                "description": description,
                "model": api_cfg["api_model"],
                "name": req.name,
            }
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"VLM API error: {exc.response.status_code} {exc.response.text[:500]}"
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"VLM call failed: {exc}")


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
