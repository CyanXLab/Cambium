"""
Agent Loop v2 endpoint (CoALA + Claude Code).

The v2 Agent Loop implements the full cognitive decision cycle:
  Observe → Retrieve → Reason → Act → Learn

This is exposed as a SSE streaming endpoint that yields structured
events for real-time frontend rendering.

Events:
  - tool_call:    {type, tool_name, tool_args, timestamp}
  - tool_result:  {type, tool_name, tool_result, timestamp}
  - respond:      {type, content, timestamp}  (terminal)
  - error:        {type, content, timestamp}  (terminal)
"""
from __future__ import annotations

import json
import asyncio
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Optional, Any

from app.config import DB_PATH, get_config
from app.logging_config import get_logger
from app.exceptions import LLMError, ValidationError

log = get_logger(__name__)
router = APIRouter(prefix="/api/v2", tags=["agent"])


class AgentRequest(BaseModel):
    """Request body for the v2 Agent Loop endpoint."""
    messages: List[Dict[str, Any]] = []
    conversation_id: str = ""
    user_id: str = "default"
    system_prompt: Optional[str] = None
    personality: Optional[str] = None
    # Override permission mode for this request (default: from config)
    permission_mode: Optional[str] = None
    # Override max steps
    max_steps: Optional[int] = None


@router.post("/chat/agent")
async def chat_agent(req: AgentRequest):
    """Agent Loop v2 — CoALA decision cycle with Claude Code permissions.

    This endpoint is the v2 replacement for /api/chat/stream. It uses the
    AgentLoop class which implements:
      1. OBSERVE — get user message + history
      2. RETRIEVE — query cognitive kernel + memory
      3. REASON — LLM thinks with tools
      4. ACT — execute tools (with permission gates)
      5. LEARN — async cognitive update

    Permission modes (Claude Code §3.4):
      plan:       read-only, no writes
      reflect:    can write memories, not identity
      grow:       memories + growth, identity needs confirmation (default)
      autonomous: everything auto-approved
    """
    config = get_config()
    if not config.agent_loop.agent_loop_enabled:
        raise ValidationError("Agent Loop v2 is disabled in config")

    if not req.messages:
        raise ValidationError("messages must not be empty")

    try:
        from app.agent_loop_v2 import AgentLoop
        from app.model_adapter import OpenAICompatibleAdapter
        from app.tool_registry import ToolRegistry
    except ImportError as exc:
        raise LLMError(f"Agent Loop dependencies not available: {exc}")

    # Get the last user message
    last_user_msg = ""
    for m in reversed(req.messages):
        if m.get("role") == "user":
            last_user_msg = m.get("content", "")
            break
    if not last_user_msg:
        raise ValidationError("No user message found in messages")

    # Build adapter from settings
    from app.main import (
        get_api_config, WORKSPACE_DIR, PROJECT_ROOT, CUSTOM_TOOLS_DIR,
        _memory_search_cb, _memory_add_cb, _web_search_via_mcp, _sessions_spawn_sync,
    )
    api_cfg = get_api_config()
    if not api_cfg.get("api_key"):
        raise LLMError("API key not configured — set it in Settings → API")

    adapter = OpenAICompatibleAdapter(
        base_url=api_cfg.get("api_base_url", ""),
        api_key=api_cfg.get("api_key", ""),
        model=api_cfg.get("api_model", ""),
    )

    # Build tool registry
    reg = ToolRegistry(
        workspace=WORKSPACE_DIR,
        skills_dir=PROJECT_ROOT / ".skills",
        custom_tools_dir=CUSTOM_TOOLS_DIR,
        db_path=DB_PATH,
        memory_search_fn=_memory_search_cb,
        memory_add_fn=_memory_add_cb,
        web_search_fn=lambda args: _web_search_via_mcp(args.get("query", "")),
        sessions_spawn_fn=_sessions_spawn_sync,
    )

    # Build cognitive context
    cog_ctx = ""
    try:
        from app import cognitive_kernel
        ctx = cognitive_kernel.build_cognitive_context(
            DB_PATH, query=last_user_msg, user_id=req.user_id, max_chars=3000,
        )
        cog_ctx = ctx.get("combined", "")
    except Exception as exc:
        log.warning("agent_v2.cognitive_context_failed", extra={"error": str(exc)})

    # Build history
    history = [
        {"role": m["role"], "content": m.get("content", "")}
        for m in req.messages[:-1]
    ]

    # Determine permission mode
    perm_mode = req.permission_mode or config.agent_loop.agent_loop_permission_mode
    max_steps = req.max_steps or config.agent_loop.agent_loop_max_steps

    loop = AgentLoop(
        db_path=DB_PATH,
        adapter=adapter,
        tools=reg,
        permission_mode=perm_mode,
        max_steps=max_steps,
        max_context_chars=config.agent_loop.agent_loop_max_context_chars,
    )

    log.info("agent_v2.started", extra={
        "conversation_id": req.conversation_id,
        "permission_mode": perm_mode,
        "max_steps": max_steps,
        "tools_registered": len(reg.list_all_tools()) if hasattr(reg, "list_all_tools") else 0,
    })

    async def _stream():
        try:
            async for step in loop.run(
                user_message=last_user_msg,
                session_id=req.conversation_id,
                history=history,
                cognitive_context=cog_ctx,
            ):
                event_data = {
                    "type": step.step_type,
                    "content": step.content,
                    "tool_name": step.tool_name,
                    "tool_args": step.tool_args,
                    "tool_result": step.tool_result,
                    "timestamp": step.timestamp,
                }
                yield f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"
                if step.step_type in ("respond", "error"):
                    break
        except Exception as exc:
            log.error("agent_v2.stream_error", extra={
                "error": str(exc),
                "conversation_id": req.conversation_id,
            })
            yield f"data: {json.dumps({'type': 'error', 'content': str(exc)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream")


@router.get("/agent/capabilities")
async def agent_capabilities():
    """Get the v2 Agent Loop capabilities and current configuration.

    Useful for the frontend to show what's available before starting a session.
    """
    c = get_config()
    return {
        "enabled": c.agent_loop.agent_loop_enabled,
        "permission_modes": ["plan", "reflect", "grow", "autonomous"],
        "default_mode": c.agent_loop.agent_loop_permission_mode,
        "max_steps": c.agent_loop.agent_loop_max_steps,
        "max_context_chars": c.agent_loop.agent_loop_max_context_chars,
        "permission_matrix": {
            "memory.write":           [False, True,  True,  True],
            "identity.evolve":        [False, False, False, True],
            "growth.add_insight":     [False, True,  True,  True],
            "goal.update":            [False, False, True,  True],
            "tool.execute":           [False, True,  True,  True],
            "tool.execute_dangerous": [False, False, False, True],
        },
        "modes": {
            "plan": "Read-only: analyze but don't modify any cognitive state",
            "reflect": "Can write memories, cannot change identity",
            "grow": "Can write memories + growth, identity changes need confirmation",
            "autonomous": "Everything auto-approved (trust mode)",
        },
    }
