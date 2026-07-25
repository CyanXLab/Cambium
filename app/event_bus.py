"""
Event Bus for Cambium — decouple modules with event-driven architecture.

Instead of direct function calls (Memory → Identity → Reflection → Goal),
modules publish events and subscribe to events they care about.

Events:
  memory.added        → triggered when a new memory is stored
  memory.decayed      → triggered when a memory's weight drops
  identity.shift      → triggered when identity evolution is recorded
  timeline.event      → triggered when a timeline event is added
  narrative.created   → triggered when a narrative memory is created
  growth.insight      → triggered when a growth insight is added
  correction.recorded → triggered when a user correction is recorded
  goal.updated        → triggered when a goal's progress changes
  episode.created     → triggered when an episodic memory is created
  conversation.ended  → triggered when a conversation turn completes
  reflection.complete → triggered when a reflection cycle finishes
  workspace.changed   → triggered when workspace items change
  task.transition     → triggered when a runtime task changes status

Subscribers auto-register via @event_bus.subscribe decorator.
Events are processed asynchronously (asyncio.create_task).

This makes the system extensible: add a new module, subscribe to events,
no need to modify existing code.
"""
from __future__ import annotations
import asyncio
import time
import json
import hashlib
import sqlite3
from typing import Dict, List, Callable, Any, Optional, Set
from collections import defaultdict
from pathlib import Path
from app.db_utils import safe_connect


# Event types
EVENT_TYPES = {
    "memory.added", "memory.decayed", "memory.promoted", "memory.deleted",
    "identity.shift", "identity.phase_changed",
    "timeline.event", "narrative.created",
    "growth.insight", "growth.insight_validated", "growth.correction",
    "goal.updated", "goal.completed", "commitment.fulfilled",
    "episode.created", "episode.linked",
    "conversation.ended", "conversation.compressed",
    "conversation.started", "conversation.message_received",
    "reflection.complete", "reflection.failed",
    "workspace.changed", "task.transition",
    "emotion.detected", "profile.updated",
    "kg.triple_added", "concept.formed",
    "world.entity_added", "world.relation_added",
    "extraction.failed", "extraction.success",
    # New event types for Residents/Artifacts/Philosophy/Mornings/Discoveries
    "resident.created", "resident.updated", "resident.run_started", "resident.run_completed", "resident.run_failed",
    "artifact.created", "artifact.updated", "artifact.new_version", "artifact.archived",
    "philosophy.added", "philosophy.retired", "philosophy.superseded",
    "morning.generated", "morning.read",
    "discovery.created", "discovery.seen", "discovery.acted", "discovery.dismissed",
    "evolution.event", "evolution.confirmed", "evolution.disputed",
    "co_experience.surfaced", "co_experience.created", "co_experience.harvested",
    "inbox.item_added", "inbox.item_processed", "inbox.item_archived",
    "journal.written", "journal.ai_drafted",
    "pushback.triggered", "pushback.memory_surfaced",
    "plugin.loaded", "plugin.unloaded",
    "model.routed", "model.fallback",
}


class EventBus:
    """In-memory async event bus with optional persistence."""

    def __init__(self, db_path: Optional[Path] = None, persist: bool = True):
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._db_path = db_path
        self._persist = persist
        self._event_log: List[Dict] = []
        self._max_log = 1000  # keep last 1000 events in memory

    def subscribe(self, event_type: str, handler: Callable):
        """Subscribe a handler to an event type.
        Handler can be sync or async. It receives the event dict."""
        self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: Callable):
        """Unsubscribe a handler."""
        if handler in self._subscribers.get(event_type, []):
            self._subscribers[event_type].remove(handler)

    async def publish(self, event_type: str, data: Dict[str, Any]):
        """Publish an event. All subscribers are called asynchronously.
        Errors in subscribers don't block other subscribers."""
        if event_type not in EVENT_TYPES:
            # Allow custom events but log a warning
            pass

        event = {
            "type": event_type,
            "data": data,
            "timestamp": time.time(),
            "id": hashlib.sha1(f"{event_type}:{time.time()}".encode()).hexdigest()[:16],
        }

        # Log to memory
        self._event_log.append(event)
        if len(self._event_log) > self._max_log:
            self._event_log = self._event_log[-self._max_log:]

        # Persist to DB
        if self._persist and self._db_path:
            self._persist_event(event)

        # Call subscribers
        handlers = self._subscribers.get(event_type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    asyncio.create_task(handler(event))
                else:
                    handler(event)
            except Exception as e:
                print(f"[event_bus] handler error for {event_type}: {e}")

    def _persist_event(self, event: Dict):
        """Persist event to DB for audit log."""
        try:
            conn = safe_connect(self._db_path)
            conn.execute(
                "CREATE TABLE IF NOT EXISTS event_log ("
                "id TEXT PRIMARY KEY, event_type TEXT, data TEXT, timestamp REAL)"
            )
            conn.execute(
                "INSERT OR IGNORE INTO event_log (id, event_type, data, timestamp) VALUES (?,?,?,?)",
                (event["id"], event["type"],
                 json.dumps(event["data"], ensure_ascii=False, default=str),
                 event["timestamp"])
            )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[event_bus] persist failed: {e}")

    def get_recent_events(self, limit: int = 50, event_type: Optional[str] = None) -> List[Dict]:
        """Get recent events from memory log."""
        events = self._event_log
        if event_type:
            events = [e for e in events if e["type"] == event_type]
        return list(reversed(events[-limit:]))

    def get_subscribers(self) -> Dict[str, int]:
        """Get subscriber counts per event type."""
        return {k: len(v) for k, v in self._subscribers.items() if v}

    def clear_log(self):
        self._event_log.clear()


# Global instance (set by main.py on startup)
_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get the global event bus instance."""
    global _bus
    if _bus is None:
        _bus = EventBus(persist=False)  # fallback: no persistence
    return _bus


def set_event_bus(bus: EventBus):
    """Set the global event bus instance."""
    global _bus
    _bus = bus


def subscribe(event_type: str):
    """Decorator: subscribe a function to an event type.
    Usage:
        @subscribe("memory.added")
        async def on_memory_added(event):
            ...
    """
    def decorator(func: Callable):
        get_event_bus().subscribe(event_type, func)
        return func
    return decorator


async def publish(event_type: str, data: Dict[str, Any]):
    """Publish an event to the global bus."""
    await get_event_bus().publish(event_type, data)
