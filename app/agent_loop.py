"""
Agent Loop for Cambium — the core while-loop that makes the AI an agent.

Based on: CoALA (Cognitive Architectures for Language Agents) + Claude Code.

Unlike a simple "send message → get response" flow, the Agent Loop:
1. Builds cognitive context (identity + memory + goals + world)
2. Calls the LLM
3. If LLM requests tool calls → check permissions → execute → feed results back
4. If LLM responds directly → extract cognitive updates → done
5. Repeat until done or max steps reached

Permission modes (inspired by Claude Code's 7-level system):
  plan:         read-only, no writes to memory/identity/files
  reflect:      can write memory, cannot change identity
  grow:         can write memory + growth, identity changes need confirmation
  autonomous:   full auto (trusted mode)

This transforms Cambium from "answers questions" to "takes actions".
"""
from __future__ import annotations
import asyncio
import json
import time
import hashlib
from typing import Dict, List, Optional, Any, AsyncIterator
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class PermissionMode(str, Enum):
    PLAN = "plan"           # read-only
    REFLECT = "reflect"     # can write memory, not identity
    GROW = "grow"           # memory + growth, identity needs confirmation
    AUTONOMOUS = "autonomous"  # full auto


# Agent Task lifecycle states (Plan → Act → Observe → Reflect → Continue → Done)
class TaskState(str, Enum):
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
PERMISSION_MATRIX = {
    "memory.write":           [False, True,  True,  True],
    "identity.evolve":        [False, False, False, True],
    "growth.add_insight":     [False, True,  True,  True],
    "goal.update":            [False, False, True,  True],
    "tool.execute":           [False, True,  True,  True],
    "tool.execute_dangerous": [False, False, False, True],
    "workspace.write":        [False, True,  True,  True],
    "file.write":             [False, True,  True,  True],
}

MODE_INDEX = {"plan": 0, "reflect": 1, "grow": 2, "autonomous": 3}


@dataclass
class AgentStep:
    """One step in the agent loop."""
    step_type: str  # "think" | "tool_call" | "tool_result" | "respond" | "error"
    content: str = ""
    tool_name: str = ""
    tool_args: dict = field(default_factory=dict)
    tool_result: str = ""
    timestamp: float = field(default_factory=time.time)


class AgentLoop:
    """The core agent loop. Calls LLM, handles tools, respects permissions.

    Usage:
        loop = AgentLoop(adapter, tool_registry, db_path, permission_mode="grow")
        async for step in loop.run("帮我读取 test.py 文件", "session-1"):
            if step.step_type == "respond":
                print(step.content)
            elif step.step_type == "tool_call":
                print(f"调用工具: {step.tool_name}")
    """

    def __init__(self, adapter, tool_registry, db_path: Path,
                 permission_mode: str = "grow",
                 max_steps: int = 25,
                 max_context_tokens: int = 100_000,
                 task_id: str = "",
                 task_title: str = ""):
        self.adapter = adapter
        self.tools = tool_registry
        self.db_path = db_path
        self.permission_mode = permission_mode
        self.max_steps = max_steps
        self.max_context_tokens = max_context_tokens
        self._pending_confirmations: list = []
        self.task_id = task_id or f"task_{int(time.time())}"
        self.task_title = task_title
        self.state = TaskState.CREATED
        self.steps_log: List[AgentStep] = []
        self._checkpoints: List[dict] = []

    def _transition(self, new_state: TaskState):
        """Validate state transition and persist to timeline."""
        old = self.state.value
        allowed = _VALID_TRANSITIONS.get(old, set())
        if new_state.value not in allowed:
            raise ValueError(f"invalid transition: {old} → {new_state.value}")
        self.state = new_state
        # Persist state change to runtime_tasks table if available
        try:
            from app import agent_runtime
            if self.task_id and self.db_path:
                agent_runtime.add_event(
                    self.db_path, self.task_id,
                    event_type="state_change",
                    message=f"{old} → {new_state.value}",
                )
        except Exception:
            pass  # best-effort

    def _checkpoint(self, messages: list, step_num: int, label: str = ""):
        """Save a checkpoint for resume-after-restart."""
        cp = {
            "task_id": self.task_id,
            "step": step_num,
            "label": label or f"step_{step_num}",
            "state": self.state.value,
            "messages_snapshot": messages.copy(),
            "timestamp": time.time(),
        }
        self._checkpoints.append(cp)
        try:
            from app import agent_runtime
            if self.task_id:
                agent_runtime.add_event(
                    self.db_path, self.task_id,
                    event_type="checkpoint",
                    message=f"checkpoint at step {step_num}: {label}",
                )
        except Exception:
            pass

    @classmethod
    def resume(cls, task_id: str, adapter, tool_registry, db_path: Path,
               permission_mode: str = "grow") -> Optional["AgentLoop"]:
        """Resume a paused/failed task from its last checkpoint.
        Reads task state from runtime_tasks + runtime_events."""
        try:
            from app import agent_runtime
            task = agent_runtime.get_task(db_path, task_id)
            if not task:
                return None
            if task["status"] not in ("paused", "failed"):
                return None
            loop = cls(adapter, tool_registry, db_path,
                      permission_mode=permission_mode,
                      task_id=task_id, task_title=task.get("title", ""))
            loop.state = TaskState.PAUSED if task["status"] == "paused" else TaskState.FAILED
            return loop
        except Exception as e:
            print(f"[agent_loop] resume failed: {e}")
            return None

    def _needs_confirmation(self, operation: str) -> bool:
        idx = MODE_INDEX.get(self.permission_mode, 2)
        allowed = PERMISSION_MATRIX.get(operation, [False, False, False, True])
        return not allowed[idx]

    def _build_system_prompt(self, cognitive_context: str = "") -> str:
        """Build system prompt with cognitive context + tool descriptions."""
        parts = []
        if cognitive_context:
            parts.append(cognitive_context)
        # Tool descriptions
        tool_descs = self.tools.get_tool_descriptions()
        if tool_descs:
            parts.append(f"【工具能力】你可以调用以下工具：\n{tool_descs}")
        parts.append(
            "【agent 行为准则】\n"
            "1. 需要真实数据时主动调用工具\n"
            "2. 可以连续调用多个工具完成复杂任务\n"
            "3. 简单问题直接回答\n"
            "4. 工具失败时分析错误、继续调整\n"
            "5. 像朋友一样交流，根据用户情绪调整回应"
        )
        return "\n\n".join(parts)

    async def run(self, user_message: str, session_id: str = "",
                  history: list = None,
                  cognitive_context: str = "") -> AsyncIterator[AgentStep]:
        """Main loop. Yields each step for real-time rendering.

        Flow (Plan → Act → Observe → Reflect → Continue → Done):
        1. PLANNING: build system prompt + cognitive context
        2. ACTING: call LLM
        3. CHECKPOINT: every 5 steps, save state for resume
        4. OBSERVE: parse tool calls or direct response
        5. REFLECT: if tool calls, feed results back (continue loop)
        6. COMPLETED: when LLM gives direct response
        """
        # PLANNING phase
        self._transition(TaskState.PLANNING)
        system_prompt = self._build_system_prompt(cognitive_context)
        messages = [{"role": "system", "content": system_prompt}]
        if history:
            messages.extend(history[-20:])  # keep last 20 turns
        messages.append({"role": "user", "content": user_message})

        tool_schemas = self.tools.get_openai_schemas()

        # ACTING phase
        self._transition(TaskState.ACTING)

        for step_num in range(self.max_steps):
            try:
                # Periodic checkpoint every 5 steps
                if step_num > 0 and step_num % 5 == 0:
                    self._transition(TaskState.CHECKPOINT)
                    self._checkpoint(messages, step_num, label=f"auto_{step_num}")
                    self._transition(TaskState.ACTING)

                # Call model
                response = await self.adapter.chat(
                    messages,
                    temperature=0.7,
                    max_tokens=4096,
                    stream=False,
                    tools=tool_schemas if tool_schemas else None,
                    enable_thinking=False,
                )
                choice = response["choices"][0]
                msg = choice["message"]
                tool_calls = msg.get("tool_calls", [])
                content = msg.get("content", "")

                if tool_calls:
                    # REFLECTING phase: process tool calls, feed back
                    self._transition(TaskState.REFLECTING)
                    for tc in tool_calls:
                        tool_name = tc["function"]["name"]
                        try:
                            tool_args = json.loads(tc["function"]["arguments"])
                        except json.JSONDecodeError:
                            tool_args = {}

                        step = AgentStep(
                            step_type="tool_call",
                            tool_name=tool_name,
                            tool_args=tool_args,
                        )
                        self.steps_log.append(step)
                        yield step

                        # Permission check
                        danger = self.tools.get_danger_level(tool_name)
                        op = "tool.execute_dangerous" if danger == "high" else "tool.execute"
                        if self._needs_confirmation(op):
                            result_text = f"[需要确认] 工具 {tool_name} 需要授权。"
                        else:
                            result = await self.tools.execute(tool_name, tool_args)
                            result_text = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)

                        result_step = AgentStep(
                            step_type="tool_result",
                            tool_name=tool_name,
                            tool_result=result_text[:2000],
                        )
                        self.steps_log.append(result_step)
                        yield result_step

                        # Feed back to model
                        messages.append({
                            "role": "assistant",
                            "content": content,
                            "tool_calls": [tc],
                        })
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.get("id", f"call_{step_num}"),
                            "content": result_text[:2000],
                        })
                    # Back to ACTING for next iteration
                    self._transition(TaskState.ACTING)
                else:
                    # COMPLETED: direct response → done
                    self._transition(TaskState.COMPLETED)
                    final = AgentStep(step_type="respond", content=content)
                    self.steps_log.append(final)
                    yield final
                    return

            except Exception as e:
                self._transition(TaskState.FAILED)
                err = AgentStep(step_type="error", content=str(e))
                self.steps_log.append(err)
                yield err
                return

        # Max steps reached
        self._transition(TaskState.COMPLETED)
        yield AgentStep(step_type="respond", content="(已达最大步数)")
