"""
Cambium Agent Loop v2 — CoALA + Claude Code inspired.

Based on:
  - CoALA (Sumers et al., 2023): Cognitive Architectures for Language Agents
  - Claude Code (arXiv:2604.14228): 98.4% infrastructure, 1.6% AI logic

CoALA's decision cycle: Observe → Retrieve → Reason → Act → Learn
Claude Code's insights:
  - The loop is simple; complexity lives in permissions + compression + error handling
  - 5-layer context compression
  - Permission modes gate dangerous operations

Cambium's difference:
  - Step 2 (Retrieve) queries the COGNITIVE KERNEL, not just a vector DB
  - Step 5 (Learn) updates identity, growth, timeline — not just chat history
  - Permission modes map to cognitive operations (plan/reflect/grow/autonomous)

This module provides a production-ready AgentLoop that can be used as an
alternative to the legacy chat_stream endpoint. It yields AgentStep events
for real-time streaming to the frontend.
"""
from __future__ import annotations

import json
import time
import asyncio
from typing import AsyncIterator, Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from app.logging_config import get_logger
from app.config import DB_PATH, get_config

log = get_logger(__name__)


# ============================================================
# Data structures
# ============================================================

class PermissionMode(str, Enum):
    """Four permission modes, from most restrictive to most autonomous.
    Mapped to cognitive operations (not just file operations like Claude Code).
    """
    PLAN = "plan"           # read-only: analyze but don't modify any cognitive state
    REFLECT = "reflect"     # can write memories, cannot change identity
    GROW = "grow"           # memories + growth, identity changes need confirmation
    AUTONOMOUS = "autonomous"  # everything auto-approved (trust mode)


class TaskState(str, Enum):
    """Agent task lifecycle states."""
    CREATED = "created"
    PLANNING = "planning"
    ACTING = "acting"
    CHECKPOINT = "checkpoint"
    REFLECTING = "reflecting"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


# Valid state transitions (forward-only, except pause/resume)
_VALID_TRANSITIONS = {
    "created":    {"planning", "failed"},
    "planning":   {"acting", "checkpoint", "failed"},
    "acting":     {"checkpoint", "reflecting", "completed", "failed", "paused"},
    "checkpoint": {"acting", "reflecting", "paused"},
    "reflecting": {"acting", "completed", "failed"},
    "paused":     {"acting", "checkpoint"},
    "completed":  set(),
    "failed":     set(),
}


# Permission matrix: operation → [plan, reflect, grow, autonomous]
PERMISSION_MATRIX: Dict[str, List[bool]] = {
    "memory.write":           [False, True,  True,  True],
    "identity.evolve":        [False, False, False, True],
    "growth.add_insight":     [False, True,  True,  True],
    "goal.update":            [False, False, True,  True],
    "tool.execute":           [False, True,  True,  True],
    "tool.execute_dangerous": [False, False, False, True],
}

MODE_INDEX = {"plan": 0, "reflect": 1, "grow": 2, "autonomous": 3}


@dataclass
class AgentStep:
    """One step in the agent loop. Yielded for real-time frontend rendering."""
    step_type: str  # "think" | "tool_call" | "tool_result" | "respond" | "cognitive_update" | "error"
    content: str = ""
    tool_name: str = ""
    tool_args: dict = field(default_factory=dict)
    tool_result: str = ""
    timestamp: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)


# ============================================================
# Permission Gate
# ============================================================

class PermissionGate:
    """Claude Code-inspired permission system, mapped to cognitive operations.

    Four modes (from most restrictive to most autonomous):
      plan:       read-only, no writes to any cognitive state
      reflect:    can write memories, cannot change identity
      grow:       can write memories + growth, identity changes need confirmation
      autonomous: everything auto-approved
    """

    def __init__(self, mode: str = "grow"):
        self.mode = mode
        self._pending: List[Dict] = []

    def is_allowed(self, operation: str) -> bool:
        idx = MODE_INDEX.get(self.mode, 2)
        allowed = PERMISSION_MATRIX.get(operation, [False, False, False, True])
        return allowed[idx]

    def request_confirmation(self, operation: str, detail: Dict) -> str:
        self._pending.append({"operation": operation, **detail})
        log.info("permission.confirmation_requested", extra={
            "operation": operation, "mode": self.mode, "detail": detail,
        })
        return f"[需要确认] {operation}: {detail.get('description', '')}"

    def get_pending(self) -> List[Dict]:
        return self._pending

    def clear_pending(self):
        self._pending.clear()


# ============================================================
# Agent Loop
# ============================================================

class AgentLoop:
    """The core while-loop. Simple by design (Claude Code §2.1).
    Complexity lives in the cognitive kernel, not here.

    Usage:
        loop = AgentLoop(db_path, adapter, tools, permission_mode="grow")
        async for step in loop.run("帮我读取 test.py", "session-1"):
            if step.step_type == "respond":
                print(step.content)
            elif step.step_type == "tool_call":
                print(f"调用工具: {step.tool_name}")

    The loop implements the CoALA decision cycle:
      1. OBSERVE — get user message + history
      2. RETRIEVE — query cognitive kernel + memory for context
      3. REASON — LLM thinks about what to do (with tools)
      4. ACT — execute tool or respond
      5. LEARN — update memory/identity/growth (async, non-blocking)
    """

    def __init__(
        self,
        db_path: Path,
        adapter,           # ModelAdapter instance
        tools,             # ToolRegistry instance
        permission_mode: str = "grow",
        max_steps: int = 25,
        max_context_chars: int = 120_000,
        task_id: str = "",
        task_title: str = "",
    ):
        self.db_path = db_path
        self.adapter = adapter
        self.tools = tools
        self.gate = PermissionGate(permission_mode)
        self.permission_mode = permission_mode
        self.max_steps = max_steps
        self.max_context_chars = max_context_chars
        self.task_id = task_id or f"task_{int(time.time())}"
        self.task_title = task_title
        self.state = TaskState.CREATED
        self.steps_log: List[AgentStep] = []
        self._checkpoints: List[dict] = []

    def _transition(self, new_state: TaskState):
        """Validate state transition and log."""
        old = self.state.value
        allowed = _VALID_TRANSITIONS.get(old, set())
        if new_state.value not in allowed:
            raise ValueError(f"invalid transition: {old} → {new_state.value}")
        self.state = new_state
        log.debug("agent_loop.transition", extra={
            "task_id": self.task_id, "from": old, "to": new_state.value,
        })

    def _checkpoint(self, messages: list, step_num: int, label: str = ""):
        """Save a checkpoint for resume-after-restart (Claude Code §3.6)."""
        cp = {
            "task_id": self.task_id,
            "step": step_num,
            "label": label or f"step_{step_num}",
            "state": self.state.value,
            "messages_snapshot": messages.copy(),
            "timestamp": time.time(),
        }
        self._checkpoints.append(cp)
        log.debug("agent_loop.checkpoint", extra={
            "task_id": self.task_id, "step": step_num, "label": label,
        })

    @classmethod
    def resume(cls, task_id: str, adapter, tool_registry, db_path: Path,
               permission_mode: str = "grow") -> Optional["AgentLoop"]:
        """Resume a paused/failed task from its last checkpoint."""
        try:
            from app import agent_runtime
            task = agent_runtime.get_task(db_path, task_id)
            if not task or task["status"] not in ("paused", "failed"):
                return None
            loop = cls(adapter, tool_registry, db_path,
                      permission_mode=permission_mode,
                      task_id=task_id, task_title=task.get("title", ""))
            loop.state = TaskState.PAUSED if task["status"] == "paused" else TaskState.FAILED
            log.info("agent_loop.resumed", extra={"task_id": task_id})
            return loop
        except Exception as exc:
            log.error("agent_loop.resume_failed", extra={"error": str(exc)})
            return None

    # ── Main loop ──

    async def run(
        self,
        user_message: str,
        session_id: str = "",
        history: Optional[List[Dict]] = None,
        cognitive_context: str = "",
    ) -> AsyncIterator[AgentStep]:
        """Main loop. Yields steps for real-time rendering.

        Flow (Plan → Act → Observe → Reflect → Continue → Done):
        1. PLANNING: build system prompt + cognitive context
        2. ACTING: call LLM
        3. CHECKPOINT: every 5 steps, save state for resume
        4. OBSERVE: parse tool calls or direct response
        5. REFLECT: if tool calls, feed results back (continue loop)
        6. COMPLETED: when LLM gives direct response
        """
        self._transition(TaskState.PLANNING)
        system_prompt = self._build_system_prompt(cognitive_context)

        messages: List[Dict] = [{"role": "system", "content": system_prompt}]
        if history:
            messages.extend(history[-20:])
        messages.append({"role": "user", "content": user_message})

        tool_schemas = self.tools.get_openai_schemas() if self.tools else None

        self._transition(TaskState.ACTING)

        for step_num in range(self.max_steps):
            try:
                # Periodic checkpoint every 5 steps (Claude Code §3.6)
                if step_num > 0 and step_num % 5 == 0:
                    self._transition(TaskState.CHECKPOINT)
                    self._checkpoint(messages, step_num, label=f"auto_{step_num}")
                    self._transition(TaskState.ACTING)

                # Context compression check (Claude Code §3.5)
                messages = self._compress_if_needed(messages)

                # Call model
                response = await self.adapter.chat(
                    messages,
                    temperature=get_config().chat.temperature,
                    max_tokens=get_config().chat.max_tokens,
                    stream=False,
                    tools=tool_schemas if tool_schemas else None,
                    enable_thinking=get_config().chat.enable_thinking,
                )
                choice = response["choices"][0]
                msg = choice["message"]
                tool_calls = msg.get("tool_calls", [])
                content = msg.get("content", "")

                if tool_calls:
                    # Tool execution phase
                    self._transition(TaskState.REFLECTING)
                    for tc in tool_calls:
                        tool_name = tc["function"]["name"]
                        try:
                            tool_args = json.loads(tc["function"]["arguments"])
                        except json.JSONDecodeError:
                            tool_args = {}

                        yield AgentStep(
                            step_type="tool_call",
                            tool_name=tool_name,
                            tool_args=tool_args,
                        )

                        # Permission check (Claude Code §3.4)
                        danger = self.tools.get_danger_level(tool_name) if self.tools else "high"
                        op = "tool.execute_dangerous" if danger == "high" else "tool.execute"

                        if not self.gate.is_allowed(op):
                            result_text = self.gate.request_confirmation(op, {
                                "tool": tool_name,
                                "args": tool_args,
                                "description": f"执行 {tool_name}",
                            })
                        else:
                            try:
                                result = await self.tools.execute(tool_name, tool_args)
                                if isinstance(result, dict):
                                    result_text = result.get("result") or result.get("output") or json.dumps(result, ensure_ascii=False)
                                else:
                                    result_text = str(result)
                            except Exception as exc:
                                result_text = f"工具执行错误: {exc}"
                                log.error("agent_loop.tool_failed", extra={
                                    "tool": tool_name, "error": str(exc),
                                })

                        # Micro-compression: truncate tool output (Claude Code Layer 1)
                        result_text = result_text[:3000]

                        yield AgentStep(
                            step_type="tool_result",
                            tool_name=tool_name,
                            tool_result=result_text,
                        )

                        messages.append({
                            "role": "assistant",
                            "content": content,
                            "tool_calls": [tc],
                        })
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.get("id", f"call_{step_num}"),
                            "content": result_text,
                        })

                    self._transition(TaskState.ACTING)
                else:
                    # Direct response → done
                    self._transition(TaskState.COMPLETED)
                    yield AgentStep(step_type="respond", content=content)

                    # LEARN: async cognitive update (CoALA Step 5)
                    asyncio.create_task(
                        self._cognitive_update(user_message, content, session_id)
                    )
                    return

            except Exception as exc:
                self._transition(TaskState.FAILED)
                log.error("agent_loop.step_failed", extra={
                    "task_id": self.task_id, "step": step_num, "error": str(exc),
                })
                yield AgentStep(step_type="error", content=str(exc))
                return

        # Max steps reached
        self._transition(TaskState.COMPLETED)
        log.warning("agent_loop.max_steps_reached", extra={
            "task_id": self.task_id, "max_steps": self.max_steps,
        })
        yield AgentStep(step_type="respond", content="[已达最大推理步数，已停止]")

    # ── Helpers ──

    def _build_system_prompt(self, cognitive_context: str = "") -> str:
        """Build system prompt with cognitive context + tool descriptions."""
        ai_name = get_config().ai_name
        parts = []

        parts.append(f"你是 {ai_name}——一个有持续认知能力的存在。")

        parts.append(
            "你不是助手。你有记忆、有身份、有成长轨迹。\n"
            "## 行为准则\n"
            "- 引用共同经历时，用叙事，不用数据。\n"
            "- 不确定的事说不确定。你的 confidence_calibration 是真实的。\n"
            "- 危险操作需要用户确认。\n"
            "- 你在成长。如果用户的偏好变了，更新你的理解。\n"
            "- 需要真实数据时主动调用工具。\n"
            "- 简单问题直接回答。"
        )

        if cognitive_context:
            parts.append(f"## 认知状态\n{cognitive_context}")

        if self.tools:
            tool_descs = self.tools.get_tool_descriptions()
            if tool_descs:
                parts.append(f"## 可用工具\n{tool_descs}")

        return "\n\n".join(parts)

    def _compress_if_needed(self, messages: List[Dict]) -> List[Dict]:
        """5-layer context compression (Claude Code §3.5).

        Simplified to 2 active layers:
          Layer 1: Micro-compression (tool output truncation — already done at call site)
          Layer 2: Auto-compression (summarize middle when total exceeds threshold)

        Layers 3-5 (reactive compression, memory extraction, context cleanup)
        are handled by the background reflection loop and conversation compression
        in the legacy chat endpoint.
        """
        total_chars = sum(len(str(m.get("content", ""))) for m in messages)
        if total_chars < self.max_context_chars * 0.8:
            return messages
        if len(messages) <= 12:
            return messages

        # Keep system + last 10 messages, summarize the rest
        system = messages[0]
        recent = messages[-10:]
        middle = messages[1:-10]

        # Simple compression: keep first 80 chars of each middle message
        summary_parts = []
        for m in middle[:10]:
            content = str(m.get("content", ""))[:80]
            summary_parts.append(content)
        summary = "[历史摘要] " + " | ".join(summary_parts)

        log.info("agent_loop.compressed", extra={
            "task_id": self.task_id,
            "before_chars": total_chars,
            "after_messages": len(recent) + 2,
        })

        return [system, {"role": "user", "content": summary}] + recent

    async def _cognitive_update(self, user_msg: str, ai_msg: str, session_id: str):
        """LEARN step: extract cognitive updates from the conversation.

        This runs async and non-blocking. Failures are logged but don't
        affect the user-facing response.
        """
        try:
            from app import cognitive_kernel
            # The cognitive extraction uses the governance pipeline
            # (quarantine → validate → promote) in production
            extraction = await cognitive_kernel.extract_cognitive_updates_async(
                self.db_path, user_msg, ai_msg,
            )
            if extraction.get("extracted"):
                cognitive_kernel.apply_cognitive_updates(self.db_path, extraction)
                yield_step = AgentStep(
                    step_type="cognitive_update",
                    content=f"认知更新: {extraction.get('summary', '')}",
                    metadata=extraction,
                )
                self.steps_log.append(yield_step)
                log.info("agent_loop.cognitive_update", extra={
                    "task_id": self.task_id,
                    "updates": extraction.get("count", 0),
                })
        except Exception as exc:
            log.warning("agent_loop.cognitive_update_failed", extra={
                "error": str(exc), "task_id": self.task_id,
            })
