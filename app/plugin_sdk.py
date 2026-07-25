"""
Plugin SDK for Cambium — let others extend Cambium without modifying core.

A plugin is a folder containing:
  plugin.yaml       — manifest (name, version, description, permissions)
  tool.py           — tool implementations (functions registered as tools)
  hooks.py          — event handlers (subscribe to event_bus events)
  permission.json   — explicit permission grants
  SKILL.md          — (optional) skill instructions for residents

Example plugin.yaml:
    name: weather
    version: 1.0.0
    description: Weather lookup plugin
    author: example
    permissions:
      - tool.execute
      - network.fetch

Example tool.py:
    def get_weather(location: str) -> dict:
        '''Get current weather for a location.'''
        # implementation
        return {"temp": 22, "condition": "sunny"}

Example hooks.py:
    from app import event_bus

    @event_bus.subscribe("memory.added")
    async def on_memory_added(event):
        print(f"New memory: {event['data'].get('content', '')[:50]}")

Plugins are loaded on startup from the plugins/ directory. Each plugin's
tools are registered with the tool_registry, hooks are wired to event_bus.

Self-contained module. main.py loads plugins on startup.
"""
from __future__ import annotations
import os
import sys
import json
import importlib.util
import asyncio
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class Plugin:
    """A loaded plugin."""
    name: str
    version: str
    description: str
    author: str = ""
    path: Path = None
    manifest: Dict = field(default_factory=dict)
    permissions: List[str] = field(default_factory=list)
    tools: Dict[str, Callable] = field(default_factory=dict)
    hooks_module: Any = None
    loaded: bool = False
    error: str = ""


# Global plugin registry
_plugins: Dict[str, Plugin] = {}


def get_plugins_dir(base_dir: Optional[Path] = None) -> Path:
    """Get the plugins directory."""
    if base_dir is None:
        # Default: <project_root>/plugins/
        base_dir = Path(__file__).resolve().parent.parent.parent
    plugins_dir = base_dir / "plugins"
    plugins_dir.mkdir(exist_ok=True)
    return plugins_dir


def load_plugin(plugin_dir: Path) -> Plugin:
    """Load a single plugin from a directory."""
    manifest_path = plugin_dir / "plugin.yaml"
    if not manifest_path.exists():
        # Try plugin.json as fallback
        manifest_path = plugin_dir / "plugin.json"

    # Parse manifest (simple YAML-like or JSON)
    manifest = {}
    if manifest_path.exists():
        try:
            content = manifest_path.read_text(encoding="utf-8")
            if manifest_path.suffix == ".json":
                manifest = json.loads(content)
            else:
                # Simple YAML parser (key: value)
                for line in content.splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if ":" in line:
                        k, _, v = line.partition(":")
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        manifest[k] = v
        except Exception as e:
            return Plugin(
                name=plugin_dir.name,
                version="",
                description="",
                path=plugin_dir,
                error=f"manifest parse failed: {e}",
            )

    name = manifest.get("name", plugin_dir.name)
    version = manifest.get("version", "0.0.0")
    description = manifest.get("description", "")
    author = manifest.get("author", "")

    # Parse permissions
    permissions = []
    perm_path = plugin_dir / "permission.json"
    if perm_path.exists():
        try:
            permissions = json.loads(perm_path.read_text(encoding="utf-8"))
            if isinstance(permissions, dict):
                permissions = permissions.get("permissions", [])
        except Exception:
            pass
    elif "permissions" in manifest:
        perm_str = manifest["permissions"]
        if isinstance(perm_str, str):
            # Parse "tool.execute, network.fetch"
            permissions = [p.strip() for p in perm_str.split(",") if p.strip()]
        elif isinstance(perm_str, list):
            permissions = perm_str

    plugin = Plugin(
        name=name,
        version=version,
        description=description,
        author=author,
        path=plugin_dir,
        manifest=manifest,
        permissions=permissions,
    )

    # Load tool.py
    tool_path = plugin_dir / "tool.py"
    if tool_path.exists():
        try:
            spec = importlib.util.spec_from_file_location(
                f"plugin_{name}_tools", tool_path
            )
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[f"plugin_{name}_tools"] = module
                spec.loader.exec_module(module)
                # Find all public functions (not starting with _)
                for attr_name in dir(module):
                    if attr_name.startswith("_"):
                        continue
                    attr = getattr(module, attr_name)
                    if callable(attr) and not isinstance(attr, type):
                        plugin.tools[attr_name] = attr
        except Exception as e:
            plugin.error = f"tool.py load failed: {e}"
            return plugin

    # Load hooks.py
    hooks_path = plugin_dir / "hooks.py"
    if hooks_path.exists():
        try:
            spec = importlib.util.spec_from_file_location(
                f"plugin_{name}_hooks", hooks_path
            )
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[f"plugin_{name}_hooks"] = module
                spec.loader.exec_module(module)
                plugin.hooks_module = module
        except Exception as e:
            if not plugin.error:
                plugin.error = f"hooks.py load failed: {e}"

    plugin.loaded = True
    return plugin


def load_all_plugins(plugins_dir: Optional[Path] = None) -> Dict[str, Plugin]:
    """Load all plugins from the plugins directory."""
    if plugins_dir is None:
        plugins_dir = get_plugins_dir()
    global _plugins
    _plugins.clear()

    if not plugins_dir.exists():
        return _plugins

    for plugin_dir in sorted(plugins_dir.iterdir()):
        if not plugin_dir.is_dir():
            continue
        if plugin_dir.name.startswith(".") or plugin_dir.name.startswith("_"):
            continue
        plugin = load_plugin(plugin_dir)
        _plugins[plugin.name] = plugin
        if plugin.loaded:
            print(f"[plugins] loaded: {plugin.name} v{plugin.version} ({len(plugin.tools)} tools)")
            # Publish plugin.loaded event (best-effort, non-blocking)
            try:
                from app import event_bus
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.create_task(event_bus.publish("plugin.loaded", {
                            "name": plugin.name,
                            "version": plugin.version,
                            "tools": list(plugin.tools.keys()),
                        }))
                except RuntimeError:
                    pass  # no event loop running
            except Exception:
                pass
        else:
            print(f"[plugins] failed to load {plugin.name}: {plugin.error}")

    return _plugins


def get_plugin(name: str) -> Optional[Plugin]:
    """Get a loaded plugin by name."""
    return _plugins.get(name)


def list_plugins() -> List[Plugin]:
    """List all loaded plugins."""
    return list(_plugins.values())


def get_all_tools() -> Dict[str, Callable]:
    """Get all tools from all plugins. Returns {tool_name: function}."""
    tools = {}
    for plugin in _plugins.values():
        if not plugin.loaded:
            continue
        for tool_name, func in plugin.tools.items():
            # Prefix with plugin name to avoid collisions
            full_name = f"{plugin.name}.{tool_name}"
            tools[full_name] = func
    return tools


def get_plugin_stats() -> Dict:
    """Get stats for all plugins."""
    return {
        "total": len(_plugins),
        "loaded": sum(1 for p in _plugins.values() if p.loaded),
        "failed": sum(1 for p in _plugins.values() if not p.loaded),
        "plugins": [
            {
                "name": p.name,
                "version": p.version,
                "description": p.description,
                "author": p.author,
                "loaded": p.loaded,
                "error": p.error,
                "tools": list(p.tools.keys()),
                "permissions": p.permissions,
            }
            for p in _plugins.values()
        ],
    }


def create_example_plugin(plugins_dir: Optional[Path] = None):
    """Create an example plugin to show the SDK structure."""
    if plugins_dir is None:
        plugins_dir = get_plugins_dir()
    example_dir = plugins_dir / "example"
    example_dir.mkdir(exist_ok=True)

    # plugin.yaml
    (example_dir / "plugin.yaml").write_text("""\
name: example
version: 1.0.0
description: An example plugin showing the SDK structure
author: Cambium
permissions:
  - tool.execute
""", encoding="utf-8")

    # tool.py
    (example_dir / "tool.py").write_text('''\
"""Example plugin tools."""


def hello(name: str = "world") -> str:
    """Say hello to someone.

    Args:
        name: The name to greet. Defaults to "world".

    Returns:
        A greeting string.
    """
    return f"Hello, {name}! This is from the example plugin."


def add(a: float, b: float) -> float:
    """Add two numbers.

    Args:
        a: First number.
        b: Second number.

    Returns:
        The sum.
    """
    return a + b
''', encoding="utf-8")

    # hooks.py
    (example_dir / "hooks.py").write_text('''\
"""Example plugin event hooks."""
from app import event_bus


@event_bus.subscribe("memory.added")
async def on_memory_added(event):
    """Called when a new memory is added."""
    data = event.get("data", {})
    content = data.get("content", "")[:50]
    print(f"[example plugin] saw new memory: {content}")


@event_bus.subscribe("conversation.ended")
async def on_conversation_ended(event):
    """Called when a conversation ends."""
    print(f"[example plugin] conversation ended: {event.get('data', {})}")
''', encoding="utf-8")

    # permission.json
    (example_dir / "permission.json").write_text("""\
{
  "permissions": ["tool.execute", "event.subscribe"]
}
""", encoding="utf-8")

    # SKILL.md (optional)
    (example_dir / "SKILL.md").write_text("""\
---
name: example
description: Example skill for residents
version: 1.0.0
---

# Example Skill

This is an example skill that residents can use. It provides:
- `hello(name)`: Say hello
- `add(a, b)`: Add two numbers

Use these tools when the user asks for a greeting or simple math.
""", encoding="utf-8")

    print(f"[plugins] created example plugin at {example_dir}")
    return example_dir
