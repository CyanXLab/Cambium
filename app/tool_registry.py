"""
Tool Registry for Cambium — unified registry for all tools.

Combines:
- Built-in tools (from tools_ext.py — 39 tools)
- MCP server tools (from configured MCP servers)
- Custom user tools (from custom_tools/ directory)
- Skills (from .skills/ directory — read-only reference)

Provides a unified interface for the Agent Loop:
- get_openai_schemas(): returns OpenAI function-calling format
- get_tool_descriptions(): returns human-readable descriptions
- execute(name, args): runs a tool by name
- get_danger_level(name): returns 'low'/'medium'/'high'

This is the "body" that lets Cambium act, not just think.
"""
from __future__ import annotations
import json
import os
import importlib.util
import time
from typing import Dict, List, Optional, Any
from pathlib import Path
from app import tools_ext


# Danger levels per tool
DANGER_LEVELS = {
    "run_python": "medium",
    "run_shell": "medium",
    "install_package": "medium",
    "delete_file": "high",
    "delete_lines": "low",
    "file_move": "medium",
    "web_search": "low",
    "web_fetch": "low",
    "read_file": "low",
    "write_file": "medium",
    "str_replace": "low",
    "regex_replace": "low",
    "multi_edit": "low",
    "apply_patch": "low",
    "file_append": "low",
    "file_prepend": "low",
    "insert_lines": "low",
    "file_copy": "low",
    "make_directory": "low",
    "file_stat": "low",
    "file_tree": "low",
    "list_directory": "low",
    "grep": "low",
    "glob": "low",
    "get_current_time": "low",
    "todo_write": "low",
    "plan_write": "low",
    "skill_create": "low",
    "skill_update": "low",
    "skill_read": "low",
    "skill_list": "low",
    "save_custom_tool": "medium",
    "run_custom_tool": "medium",
    "list_custom_tools": "low",
    "sessions_list": "low",
    "session_status": "low",
    "sessions_history": "low",
    "sessions_spawn": "medium",
    "sessions_send": "low",
    "memory_search": "low",
    "memory_add": "low",
}


class ToolRegistry:
    """Unified tool registry. Combines built-in + MCP + custom tools."""

    def __init__(self, workspace: Path, skills_dir: Path, custom_tools_dir: Path,
                 db_path: Path = None, memory_search_fn=None, memory_add_fn=None,
                 web_search_fn=None, sessions_spawn_fn=None):
        self.workspace = workspace
        self.skills_dir = skills_dir
        self.custom_tools_dir = custom_tools_dir
        self.db_path = db_path
        # Build the dispatcher from tools_ext
        self._dispatcher = tools_ext.make_dispatcher(
            workspace=workspace,
            skills_dir=skills_dir,
            custom_tools_dir=custom_tools_dir,
            memory_search_fn=memory_search_fn,
            memory_add_fn=memory_add_fn,
            web_search_fn=web_search_fn,
            sessions_spawn_fn=sessions_spawn_fn,
        )
        self._definitions = tools_ext.build_tool_definitions()

    def get_openai_schemas(self) -> List[Dict]:
        """Return tool definitions in OpenAI function-calling format."""
        return self._definitions

    def get_tool_descriptions(self) -> str:
        """Return human-readable tool list for system prompt."""
        lines = []
        seen = set()
        for t in self._definitions:
            name = t["function"]["name"]
            if name in seen:
                continue
            seen.add(name)
            desc = t["function"]["description"][:80]
            lines.append(f"- {name}: {desc}")
        return "\n".join(lines[:30])  # cap at 30 to avoid prompt bloat

    def get_danger_level(self, tool_name: str) -> str:
        """Return danger level: low/medium/high."""
        return DANGER_LEVELS.get(tool_name, "medium")

    def execute(self, name: str, args: Dict) -> Any:
        """Execute a tool by name. Returns result dict."""
        return self._dispatcher(name, args)

    def list_all_tools(self) -> List[Dict]:
        """List all registered tools with metadata."""
        out = []
        for t in self._definitions:
            f = t["function"]
            out.append({
                "name": f["name"],
                "description": f["description"][:100],
                "danger": self.get_danger_level(f["name"]),
            })
        return out

    def list_custom_tools(self) -> List[Dict]:
        """List user-created custom Python tools."""
        if not self.custom_tools_dir.exists():
            return []
        out = []
        for f in sorted(self.custom_tools_dir.glob("*.py")):
            meta_file = self.custom_tools_dir / f"{f.stem}.meta.json"
            desc = ""
            if meta_file.exists():
                try:
                    desc = json.loads(meta_file.read_text()).get("description", "")
                except Exception:
                    pass
            out.append({"name": f.stem, "description": desc, "size": f.stat().st_size})
        return out
