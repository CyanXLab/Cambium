"""
Context Cache for Cambium — cache cognitive context to avoid rebuilding every message.

The cognitive context (identity + timeline + narratives + growth + goals + world + self)
changes slowly. Rebuilding it every message wastes tokens.

Cache invalidation: rebuild only when a cognitive write happens (memory add,
identity update, etc.). TTL: 5 minutes as safety net.

Saves ~90% of context tokens in multi-turn conversations.
"""
from __future__ import annotations
import time
from typing import Dict, Optional
from dataclasses import dataclass, field


@dataclass
class CacheEntry:
    context: str
    built_at: float
    version: int


class CognitiveContextCache:
    """Per-user cache of the cognitive context string."""

    def __init__(self, ttl_seconds: int = 300):
        self.ttl = ttl_seconds
        self._cache: Dict[str, CacheEntry] = {}
        self._version: Dict[str, int] = {}  # user_id → version counter (bumped on invalidation)

    def invalidate(self, user_id: str = "default"):
        """Call this after ANY cognitive write (memory add, identity update, etc.)"""
        self._version[user_id] = self._version.get(user_id, 0) + 1
        self._cache.pop(user_id, None)

    def get(self, user_id: str = "default") -> Optional[str]:
        """Get cached context if still valid."""
        entry = self._cache.get(user_id)
        if not entry:
            return None
        if time.time() - entry.built_at > self.ttl:
            return None
        if entry.version != self._version.get(user_id, 0):
            return None
        return entry.context

    def set(self, user_id: str, context: str):
        """Store a context in the cache."""
        self._cache[user_id] = CacheEntry(
            context=context,
            built_at=time.time(),
            version=self._version.get(user_id, 0),
        )

    def get_stats(self) -> Dict:
        """Get cache statistics."""
        return {
            "cached_users": len(self._cache),
            "versions": dict(self._version),
            "ttl_seconds": self.ttl,
        }

    def clear(self):
        self._cache.clear()
        self._version.clear()


# Global instance
_cache: Optional[CognitiveContextCache] = None


def get_context_cache() -> CognitiveContextCache:
    global _cache
    if _cache is None:
        _cache = CognitiveContextCache()
    return _cache


def invalidate_context(user_id: str = "default"):
    """Invalidate the cached context for a user.
    Call after any cognitive write."""
    get_context_cache().invalidate(user_id)
    # Also publish an event
    try:
        from app.event_bus import publish
        import asyncio
        asyncio.create_task(publish("workspace.changed", {"user_id": user_id}))
    except Exception:
        pass
